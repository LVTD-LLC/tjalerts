from django.db import transaction
from tqdm import tqdm

from jobs.models import Alert, PostTechnology, Technology, TechnologyMapping
from jobs.technology_names import extract_technology_names, normalize_technology_key
from jobs.technology_normalization import (
    get_or_create_canonical_technologies,
    seed_default_technology_aliases,
    upsert_technology_alias,
)

DRY_RUN = True
DELETE_EMPTY_ALIAS_TECHNOLOGIES = False


def technology_ids_for_alert(filter_value):
    if not isinstance(filter_value, dict):
        return []
    technology_ids = filter_value.get("technologies", [])
    if not isinstance(technology_ids, list):
        return []
    return [str(technology_id) for technology_id in technology_ids]


def replace_alert_technology_ids(old_technology, new_technologies):
    updated_count = 0
    new_ids = [str(technology.id) for technology in new_technologies]

    for alert in Alert.objects.all().iterator():
        technology_ids = technology_ids_for_alert(alert.filter)
        if str(old_technology.id) not in technology_ids:
            continue

        next_ids = []
        for technology_id in technology_ids:
            if technology_id == str(old_technology.id):
                next_ids.extend(new_ids)
            else:
                next_ids.append(technology_id)

        deduped_ids = list(dict.fromkeys(next_ids))
        alert.filter["technologies"] = deduped_ids
        alert.save(update_fields=["filter", "modified"])
        updated_count += 1

    return updated_count


def add_post_technology(post_id, technology):
    if PostTechnology.objects.filter(post_id=post_id, technology=technology).exists():
        return False

    PostTechnology.objects.create(post_id=post_id, technology=technology)
    return True


def merge_technology(technology, canonical_technologies):
    post_ids = list(PostTechnology.objects.filter(technology=technology).values_list("post_id", flat=True))
    created_post_links = 0

    for post_id in post_ids:
        for canonical_technology in canonical_technologies:
            if canonical_technology.id != technology.id:
                created_post_links += int(add_post_technology(post_id, canonical_technology))

        if any(canonical_technology.id != technology.id for canonical_technology in canonical_technologies):
            PostTechnology.objects.filter(post_id=post_id, technology=technology).delete()

    updated_alerts = replace_alert_technology_ids(technology, canonical_technologies)

    if len(canonical_technologies) == 1 and canonical_technologies[0].id != technology.id:
        TechnologyMapping.objects.get_or_create(parent=canonical_technologies[0], child=technology)
        upsert_technology_alias(canonical_technologies[0], technology.name, source="backfill")

    if (
        DELETE_EMPTY_ALIAS_TECHNOLOGIES
        and all(canonical_technology.id != technology.id for canonical_technology in canonical_technologies)
        and not PostTechnology.objects.filter(technology=technology).exists()
    ):
        technology.delete()

    return created_post_links, updated_alerts


if DRY_RUN:
    print("DRY_RUN=True. No data will be changed.")
else:
    seeded_count = seed_default_technology_aliases(source="backfill")
    print(f"Seeded or refreshed {seeded_count} default aliases.")

technologies = Technology.objects.order_by("name", "created")
planned_changes = []

for technology in technologies.iterator():
    canonical_names = extract_technology_names(technology.name)
    canonical_keys = [normalize_technology_key(name) for name in canonical_names]
    current_key = normalize_technology_key(technology.name)

    if not canonical_names:
        continue

    if canonical_keys == [current_key] and canonical_names[0] == technology.name:
        continue

    planned_changes.append((technology.id, technology.name, canonical_names))

print(f"Found {len(planned_changes)} technology rows to normalize.")

for _, old_name, canonical_names in planned_changes[:100]:
    print(f"{old_name!r} -> {', '.join(canonical_names)}")

if len(planned_changes) > 100:
    print(f"...and {len(planned_changes) - 100} more.")

if not DRY_RUN:
    moved_links = 0
    updated_alerts = 0

    with tqdm(total=len(planned_changes), desc="Normalizing technologies") as pbar:
        for technology_id, old_name, _ in planned_changes:
            with transaction.atomic():
                technology = Technology.objects.get(id=technology_id)
                canonical_technologies = get_or_create_canonical_technologies(old_name, alias_source="backfill")
                link_count, alert_count = merge_technology(technology, canonical_technologies)
                moved_links += link_count
                updated_alerts += alert_count
            pbar.update(1)

    print(f"Created {moved_links} canonical post links.")
    print(f"Updated {updated_alerts} alert filters.")
