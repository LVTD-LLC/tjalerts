from django import forms
from django.core.validators import EMPTY_VALUES
from django_filters import BooleanFilter, CharFilter, Filter, FilterSet, ModelMultipleChoiceFilter, OrderingFilter
from pgvector.django import L2Distance

from .models import Post
from .queries import get_most_popular_technologies
from .utils import get_embedding


class VectorEmbeddingFilter(Filter):
    def filter(self, qs, value):
        if not value:
            return qs

        return qs.annotate(distance=L2Distance("vector", get_embedding(value))).filter(distance__lt=0.7)


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
        queryset=get_most_popular_technologies(), widget=forms.CheckboxSelectMultiple(), conjoined=True
    )
    compensation_summary__isempty = EmptyStringFilter(field_name="compensation_summary")

    o = OrderingFilter(
        choices=(
            ("-submitted_datetime", "Date"),
            ("-distance", "Relevance"),
        ),
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
        return super().qs.exclude(description__exact="")
