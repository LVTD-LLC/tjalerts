import time

from django import forms
from django.core.validators import EMPTY_VALUES
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django_filters import BooleanFilter, CharFilter, Filter, FilterSet, ModelMultipleChoiceFilter, OrderingFilter
from pgvector.django import L2Distance

from hn_jobs.utils import get_tjalerts_logger

from .models import Post, TechnologyMapping
from .queries import get_most_popular_technologies, get_most_popular_titles
from .utils import get_embedding

logger = get_tjalerts_logger(__name__)


class VectorEmbeddingFilter(Filter):
    def filter(self, qs, value):
        if not value:
            return qs

        return qs.annotate(distance=L2Distance("vector", get_embedding(value))).filter(distance__lt=1.25)


class EmptyStringFilter(BooleanFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        exclude = self.exclude ^ (value is True)
        method = qs.exclude if exclude else qs.filter

        return method(**{self.field_name: ""})


class PostFilter(FilterSet):
    vector = VectorEmbeddingFilter(field_name="vector")
    locations = CharFilter(lookup_expr="icontains")
    remove_duplicate_employers = BooleanFilter(
        label="Employers",
        method="noop_filter",
        widget=forms.Select(
            choices=(
                ("", "Show all"),
                ("true", "Remove duplicates"),
            )
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

    o = OrderingFilter(
        choices=(
            ("-submitted_datetime", "Date"),
            ("-max_salary", "Max Salary"),
        )
    )

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
            order_expression = F(field_name).desc(nulls_last=True) if descending else F(field_name).asc(nulls_last=True)
            order_expressions.append(order_expression)

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

        if self.form.is_valid() and self.form.cleaned_data.get("remove_duplicate_employers"):
            return self.remove_duplicate_employers_from_queryset(queryset)

        return queryset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.data.get("vector"):
            self.filters["o"] = OrderingFilter(
                choices=(
                    ("-submitted_datetime", "Date"),
                    ("-max_salary", "Max Salary"),
                    ("-distance", "Relevance"),
                ),
            )
