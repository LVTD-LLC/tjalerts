from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from jobs.lookups import (
    get_similar_post_options,
    get_technology_option,
    get_title_option,
    search_technology_options,
    search_title_options,
)
from jobs.models import Post


@require_GET
def technology_search(request):
    return JsonResponse(search_technology_options(request.GET.get("query")), safe=False)


@require_GET
def technology_detail(request, pk):
    technology = get_technology_option(pk)
    if technology is None:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(technology)


@require_GET
def title_search(request):
    return JsonResponse(search_title_options(request.GET.get("query")), safe=False)


@require_GET
def title_detail(request, pk):
    title = get_title_option(pk)
    if title is None:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(title)


@require_GET
def similar_posts(request, pk):
    post = get_object_or_404(Post, pk=pk)
    return JsonResponse({"similar_posts": get_similar_post_options(post)})
