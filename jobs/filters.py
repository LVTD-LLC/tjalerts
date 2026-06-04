import time
from datetime import timedelta

from django import forms
from django.core.validators import EMPTY_VALUES
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone
from django_filters import (
    BooleanFilter,
    CharFilter,
    ChoiceFilter,
    Filter,
    FilterSet,
    ModelMultipleChoiceFilter,
    NumberFilter,
    OrderingFilter,
)
from pgvector.django import L2Distance

from hn_jobs.utils import get_tjalerts_logger

from .choices import PostSource
from .models import Post, TechnologyMapping
from .queries import get_most_popular_technologies, get_most_popular_titles
from .utils import get_embedding, parse_positive_day_count

logger = get_tjalerts_logger(__name__)


class VectorEmbeddingFilter(Filter):
    def filter(self, qs, value):
        if not value:
            return qs

        return (
            qs.annotate(distance=L2Distance("vector", get_embedding(value)))
            .filter(distance__lt=1.25)
            .order_by("distance")
        )


class EmptyStringFilter(BooleanFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        exclude = self.exclude ^ (value is True)
        method = qs.exclude if exclude else qs.filter

        return method(**{self.field_name: ""})


class PostOrderingFilter(OrderingFilter):
    def get_ordering_value(self, param):
        if param == "-max_salary":
            return F("max_salary").desc(nulls_last=True)

        if param == "max_salary":
            return F("max_salary").asc(nulls_last=True)

        return super().get_ordering_value(param)


HAS_FIELD_CHOICES = (
    ("yes", "Yes"),
    ("no", "No"),
)

MAX_KEYWORD_SEARCH_TERMS = 5

POSTED_WITHIN_CHOICES = (
    ("7", "Last 7 days"),
    ("30", "Last 30 days"),
    ("60", "Last 60 days"),
)

WORK_MODE_CHOICES = (
    ("remote", "Remote roles"),
    ("remote_only", "Remote only"),
    ("onsite", "Onsite or hybrid"),
    ("onsite_only", "Onsite only"),
    ("hybrid", "Hybrid"),
)


class PostFilter(FilterSet):
    q = CharFilter(method="filter_keyword_search")
    vector = VectorEmbeddingFilter(field_name="vector")
    locations = CharFilter(lookup_expr="icontains")
    remove_duplicate_employers = ChoiceFilter(
        label="Employers",
        method="noop_filter",
        choices=(
            ("", "Show all"),
            ("true", "Remove duplicates"),
        ),
    )
    technologies = ModelMultipleChoiceFilter(
        queryset=lambda request: get_most_popular_technologies(),
        widget=forms.CheckboxSelectMultiple(),
        method="extend_technology_search",
    )
    titles = ModelMultipleChoiceFilter(
        queryset=lambda request: get_most_popular_titles(),
        widget=forms.CheckboxSelectMultiple(),
    )
    compensation_summary__isempty = EmptyStringFilter(field_name="compensation_summary")
    emails__isempty = EmptyStringFilter(field_name="emails")
    has_compensation = ChoiceFilter(choices=HAS_FIELD_CHOICES, method="filter_has_compensation")
    has_contact = ChoiceFilter(choices=HAS_FIELD_CHOICES, method="filter_has_contact")
    posted_within = ChoiceFilter(choices=POSTED_WITHIN_CHOICES, method="filter_posted_within")
    added_within_days = NumberFilter(method="filter_added_within_days")
    salary_floor = NumberFilter(method="filter_salary_floor")
    source = ChoiceFilter(choices=PostSource.choices)
    work_mode = ChoiceFilter(choices=WORK_MODE_CHOICES, method="filter_work_mode")

    o = PostOrderingFilter(
        choices=(
            ("-submitted_datetime", "Newest first"),
            ("-max_salary", "Highest salary"),
            ("company__name", "Company A-Z"),
        )
    )

    def filter_keyword_search(self, queryset, name, value):
        if not value:
            return queryset

        search_terms = [term.strip() for term in value.split() if term.strip()][:MAX_KEYWORD_SEARCH_TERMS]

        for term in search_terms:
            queryset = queryset.filter(
                Q(company__name__icontains=term)
                | Q(description__icontains=term)
                | Q(titles__name__icontains=term)
                | Q(technologies__name__icontains=term)
                | Q(locations__icontains=term)
                | Q(cities__icontains=term)
                | Q(countries__icontains=term)
                | Q(remote_timezones__icontains=term)
                | Q(compensation_summary__icontains=term)
            )

        return queryset.distinct()

    def filter_has_compensation(self, queryset, name, value):
        missing_compensation = Q(compensation_summary__isnull=True) | Q(compensation_summary__exact="")

        if value == "yes":
            return queryset.exclude(missing_compensation)
        if value == "no":
            return queryset.filter(missing_compensation)

        return queryset

    def filter_has_contact(self, queryset, name, value):
        if value == "yes":
            return queryset.exclude(emails="")
        if value == "no":
            return queryset.filter(emails="")

        return queryset

    def filter_posted_within(self, queryset, name, value):
        if not value:
            return queryset

        try:
            days = int(value)
        except (TypeError, ValueError):
            return queryset

        return queryset.filter(submitted_datetime__gte=timezone.now() - timedelta(days=days))

    def filter_added_within_days(self, queryset, name, value):
        days = parse_positive_day_count(value)
        if days is None:
            return queryset

        return queryset.filter(created__gte=timezone.now() - timedelta(days=days))

    def filter_salary_floor(self, queryset, name, value):
        if value in EMPTY_VALUES or value <= 0:
            return queryset

        return queryset.filter(max_salary__gte=value).exclude(max_salary=0)

    def filter_work_mode(self, queryset, name, value):
        if value == "remote":
            return queryset.filter(is_remote=True)
        if value == "remote_only":
            return queryset.filter(is_remote=True, is_onsite=False)
        if value == "onsite":
            return queryset.filter(is_onsite=True)
        if value == "onsite_only":
            return queryset.filter(is_remote=False, is_onsite=True)
        if value == "hybrid":
            return queryset.filter(is_remote=True, is_onsite=True)

        return queryset

    def extend_technology_search(self, queryset, name, selected_technologies):
        start_time = time.time()

        if selected_technologies:
            selected_technology_ids = [tech.id for tech in selected_technologies]
            child_technology_ids = list(
                TechnologyMapping.objects.filter(parent_id__in=selected_technology_ids).values_list(
                    "child_id", flat=True
                )
            )
            selected_technology_ids.extend(child_technology_ids)

            logger.info(
                "Filtering by all techologies",
                selected_technologies=[t.name for t in selected_technologies],
                count_of_selected_technologies=len(selected_technologies),
                count_of_all_related_techologies=len(selected_technology_ids),
                duration=round(time.time() - start_time, 2),
            )

            return queryset.filter(technologies__id__in=selected_technology_ids).distinct()

        logger.info(
            "No need to extend technology search",
            duration=round(time.time() - start_time, 2),
        )

        return queryset

    def noop_filter(self, queryset, name, value):
        return queryset

    def remove_duplicate_employers_from_queryset(self, queryset):
        return queryset.annotate(
            employer_row_number=Window(
                expression=RowNumber(),
                partition_by=[F("company_id")],
                order_by=self.get_employer_dedupe_ordering(queryset),
            )
        ).filter(employer_row_number=1)

    def get_employer_dedupe_ordering(self, queryset):
        ordering = queryset.query.order_by or queryset.model._meta.ordering or ("-submitted_datetime",)
        order_expressions = []

        for field_name in ordering:
            if hasattr(field_name, "resolve_expression"):
                order_expressions.append(field_name)
                continue

            if field_name == "?":
                continue

            descending = field_name.startswith("-")
            field_name = field_name[1:] if descending else field_name
            order_expression = F(field_name).desc() if descending else F(field_name).asc()
            order_expressions.append(order_expression)

        order_expressions.append(F("submitted_datetime").desc())
        order_expressions.append(F("id").asc())

        return order_expressions

    class Meta:
        model = Post
        fields = [
            "is_remote",
            "is_onsite",
            # "technologies",
            "locations",
        ]

    @property
    def qs(self):
        queryset = super().qs.exclude(description__exact="")

        if self.form.is_valid() and self.form.cleaned_data.get("remove_duplicate_employers") == "true":
            return self.remove_duplicate_employers_from_queryset(queryset)

        return queryset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.data.get("vector"):
            self.filters["o"] = PostOrderingFilter(
                choices=(
                    ("-submitted_datetime", "Newest first"),
                    ("-max_salary", "Highest salary"),
                    ("company__name", "Company A-Z"),
                    ("distance", "Intent match"),
                ),
            )
