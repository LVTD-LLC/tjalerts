from django import forms
from django.core.validators import EMPTY_VALUES
from django_filters import BooleanFilter, CharFilter, Filter, FilterSet, ModelMultipleChoiceFilter, OrderingFilter
from pgvector.django import L2Distance

from hn_jobs.utils import get_tjalerts_logger

from .models import Post, TechnologyMapping
from .queries import get_most_popular_technologies
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
        queryset=get_most_popular_technologies(), widget=forms.CheckboxSelectMultiple()
    )
    compensation_summary__isempty = EmptyStringFilter(field_name="compensation_summary")
    emails__isempty = EmptyStringFilter(field_name="emails")

    o = OrderingFilter(
        choices=(
            ("-submitted_datetime", "Date"),
            ("-max_salary", "Max Salary"),
        )
    )

    class Meta:
        model = Post
        fields = [
            "is_remote",
            "is_onsite",
            "technologies",
            "locations",
        ]

    @property
    def qs(self):
        queryset = super().qs.exclude(description__exact="")

        selected_technologies_id = self.request.GET.getlist("technologies")
        if selected_technologies_id:
            all_related_ids = []
            child_technology_ids = list(
                TechnologyMapping.objects.filter(parent_id__in=selected_technologies_id).values_list(
                    "child_id", flat=True
                )
            )
            all_related_ids.extend(child_technology_ids)

            logger.info(
                "Filtering by all techologies",
                count_of_selected_technologies=len(selected_technologies_id),
                count_of_all_related_techologies=len(all_related_ids),
            )

            queryset = queryset.filter(technologies__id__in=all_related_ids).distinct()

        return queryset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.data.get("vector"):
            self.filters["o"] = OrderingFilter(
                choices=(("-submitted_datetime", "Date"), ("-max_salary", "Max Salary"), ("-distance", "Relevance")),
            )
