from django import forms
from django.core.validators import EMPTY_VALUES
from django_filters import BooleanFilter, CharFilter, FilterSet, ModelMultipleChoiceFilter

from .models import Post
from .queries import get_most_popular_technologies


class EmptyStringFilter(BooleanFilter):
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        exclude = self.exclude ^ (value is True)
        method = qs.exclude if exclude else qs.filter

        return method(**{self.field_name: ""})


class PostFilter(FilterSet):
    description = CharFilter(lookup_expr="icontains")
    locations = CharFilter(lookup_expr="icontains")
    technologies = ModelMultipleChoiceFilter(
        queryset=get_most_popular_technologies(), widget=forms.CheckboxSelectMultiple(), conjoined=True
    )
    compensation_summary__isempty = EmptyStringFilter(field_name="compensation_summary")

    class Meta:
        model = Post
        fields = [
            "description",
            "is_remote",
            "is_onsite",
            "technologies",
            "locations",
        ]
