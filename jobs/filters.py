import time
from datetime import timedelta

from django import forms
from django.core.validators import EMPTY_VALUES
from django.db.models import Case, When
from django.utils import timezone
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
        ),
        empty_label="Date",
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

        one_month_ago = timezone.now() - timedelta(days=30)
        queryset = queryset.annotate(
            is_recently_sponsored=Case(When(sponsored=True, sponsored_at__gte=one_month_ago, then=True), default=False)
        )

        ordering = self.data.get("o")
        if ordering:
            queryset = queryset.order_by("-is_recently_sponsored", ordering)
        else:
            queryset = queryset.order_by("-is_recently_sponsored", "-submitted_datetime")

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
                empty_label="Date",
            )
