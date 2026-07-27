from django.db.models import QuerySet
from pgvector.django import L2Distance

from jobs.utils import get_embedding

MAX_SEMANTIC_DISTANCE = 1.25


class SemanticSearchUnavailableError(RuntimeError):
    """Raised when the embedding provider cannot serve a semantic query."""


def apply_semantic_search(queryset: QuerySet, query: str) -> QuerySet:
    try:
        embedding = get_embedding(query)
    except Exception as exc:
        raise SemanticSearchUnavailableError("Semantic search is temporarily unavailable") from exc

    return (
        queryset.annotate(distance=L2Distance("vector", embedding))
        .filter(distance__lt=MAX_SEMANTIC_DISTANCE)
        .order_by("distance")
    )
