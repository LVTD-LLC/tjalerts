from django import forms
from django_filters import CharFilter, FilterSet, ModelMultipleChoiceFilter

from .models import Post
from .queries import get_most_popular_technologies


class PostFilter(FilterSet):
    description = CharFilter(lookup_expr="icontains")

    locations = CharFilter(lookup_expr="icontains")

    technologies = ModelMultipleChoiceFilter(
        queryset=get_most_popular_technologies(), widget=forms.CheckboxSelectMultiple(), conjoined=True
    )

    class Meta:
        model = Post
        fields = [
            "description",
            "is_remote",
            "is_onsite",
            "technologies",
            "locations",
        ]
