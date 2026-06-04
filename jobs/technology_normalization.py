from django.db import connection, transaction

from jobs.models import Technology, TechnologyAlias, TechnologyMapping
from jobs.technology_names import (
    DEFAULT_TECHNOLOGY_ALIASES,
    DEFAULT_TECHNOLOGY_ALIAS_MAP,
    clean_technology_display_value,
    extract_technology_names,
    normalize_technology_key,
    split_context_technology_values,
)


def get_or_create_canonical_technologies(value, alias_source="import"):
    technologies = []
    seen_ids = set()

    for technology in resolve_technology_values(value, alias_source=alias_source):
        if technology.id not in seen_ids:
            technologies.append(technology)
            seen_ids.add(technology.id)

    return technologies


def resolve_technology_values(value, alias_source="import"):
    technologies = []

    for raw_value in split_context_technology_values(value):
        alias_technology = get_alias_technology(raw_value)
        if alias_technology:
            technologies.append(alias_technology)
            continue

        for technology_name in extract_technology_names(raw_value):
            technologies.append(
                get_or_create_canonical_technology(
                    technology_name,
                    alias_source=alias_source,
                )
            )

    return technologies


def get_or_create_canonical_technology(technology_name, alias_source="import"):
    technology_name = clean_technology_display_value(technology_name)
    builtin_name = DEFAULT_TECHNOLOGY_ALIAS_MAP.get(normalize_technology_key(technology_name))
    canonical_name = builtin_name or technology_name

    if not builtin_name:
        mapped_technology = get_existing_mapped_technology(technology_name)
        if mapped_technology:
            return mapped_technology

    technology = get_or_create_technology_by_name(canonical_name)

    if normalize_technology_key(technology_name) != normalize_technology_key(technology.name):
        upsert_technology_alias(technology, technology_name, source=alias_source)

    return technology


def get_existing_mapped_technology(technology_name):
    technology = Technology.objects.filter(name__iexact=technology_name).order_by("created").first()
    if not technology:
        return None

    parent_id = TechnologyMapping.objects.filter(child=technology).values_list("parent_id", flat=True).first()
    if parent_id:
        return Technology.objects.get(id=parent_id)

    return technology


def get_alias_technology(value):
    normalized_alias = normalize_technology_key(value)
    if not normalized_alias:
        return None

    alias = (
        TechnologyAlias.objects.select_related("technology")
        .filter(normalized_alias=normalized_alias)
        .order_by("created")
        .first()
    )
    if alias:
        return alias.technology

    return None


@transaction.atomic
def get_or_create_technology_by_name(name):
    lock_technology_name_creation(name)

    technology = Technology.objects.filter(name=name).order_by("created").first()
    if technology:
        return technology

    technology = Technology.objects.filter(name__iexact=name).order_by("created").first()
    if technology:
        technology.name = name
        technology.save(update_fields=["name", "modified"])
        return technology

    return Technology.objects.create(name=name)


def lock_technology_name_creation(name):
    if connection.vendor != "postgresql":
        return

    lock_key = normalize_technology_key(name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [lock_key])


def upsert_technology_alias(technology, alias, source="manual", notes=""):
    alias = clean_technology_display_value(alias)
    normalized_alias = normalize_technology_key(alias)
    if not alias or not normalized_alias:
        return None

    technology_alias, created = TechnologyAlias.objects.get_or_create(
        normalized_alias=normalized_alias,
        defaults={
            "technology": technology,
            "alias": alias,
            "source": source,
            "notes": notes,
        },
    )

    if not created and technology_alias.technology_id != technology.id:
        technology_alias.technology = technology
        technology_alias.alias = alias
        technology_alias.source = source
        technology_alias.notes = notes
        technology_alias.save(update_fields=["technology", "alias", "source", "notes", "modified"])

    return technology_alias


@transaction.atomic
def seed_default_technology_aliases(source="default"):
    seeded = 0

    for alias, canonical_name in DEFAULT_TECHNOLOGY_ALIASES:
        technology = get_or_create_technology_by_name(canonical_name)
        if normalize_technology_key(alias) == normalize_technology_key(canonical_name):
            continue
        technology_alias = upsert_technology_alias(technology, alias, source=source)
        seeded += int(bool(technology_alias))

    return seeded


def get_related_technology_ids(technology):
    if not technology:
        return []

    parent_id = TechnologyMapping.objects.filter(child=technology).values_list("parent_id", flat=True).first()
    root_id = parent_id or technology.id
    child_ids = list(TechnologyMapping.objects.filter(parent_id=root_id).values_list("child_id", flat=True))

    return [root_id, *child_ids]
