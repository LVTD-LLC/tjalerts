from django.db import transaction
from django.utils import timezone
from tqdm import tqdm

from jobs.choices import PostSource
from jobs.models import Post
from jobs.utils import is_probably_non_hiring_hn_comment, normalize_hn_comment_text


valid_actions = {"dry_run", "mark", "delete"}
action = (input("Action [dry_run/mark/delete]: ").strip() or "dry_run").lower()

if action not in valid_actions:
    raise ValueError(f"Action must be one of: {', '.join(sorted(valid_actions))}")

if action == "delete":
    confirmation = input("Type DELETE_NON_HIRING_HN_POSTS to hard-delete matching posts: ").strip()
    if confirmation != "DELETE_NON_HIRING_HN_POSTS":
        raise ValueError("Delete confirmation did not match.")

queryset = (
    Post.objects.filter(source=PostSource.HACKER_NEWS)
    .select_related("company")
    .only(
        "id",
        "company",
        "company__name",
        "source_external_id",
        "source_payload",
        "source_url",
        "original_text",
        "who_is_hiring_comment_id",
    )
)

matched_count = 0
marked_count = 0
deleted_count = 0
empty_text_count = 0
already_marked_count = 0
processed_count = 0
detected_at = timezone.now().isoformat()

with tqdm(total=queryset.count(), desc="Reviewing HN posts") as progress:
    for post in queryset.iterator(chunk_size=500):
        processed_count += 1
        payload = post.source_payload if isinstance(post.source_payload, dict) else {}
        original_text = post.original_text or payload.get("text", "")

        if not normalize_hn_comment_text(original_text):
            empty_text_count += 1
            progress.update(1)
            continue

        if not is_probably_non_hiring_hn_comment(original_text):
            progress.update(1)
            continue

        matched_count += 1
        comment_id = post.source_external_id or post.who_is_hiring_comment_id or post.id
        company_name = post.company.name if post.company_id else ""
        tqdm.write(f"Matched post={post.id} comment={comment_id} company={company_name} url={post.source_url}")

        if action == "mark":
            review = payload.get("non_hiring_review", {})
            if review.get("detected") is True:
                already_marked_count += 1
                progress.update(1)
                continue

            payload["non_hiring_review"] = {
                "detected": True,
                "detected_at": detected_at,
                "detector": "jobs.utils.is_probably_non_hiring_hn_comment",
                "action": "mark",
            }
            post.source_payload = payload
            post.save(update_fields=["source_payload"])
            marked_count += 1

        if action == "delete":
            with transaction.atomic():
                post.delete()
            deleted_count += 1

        progress.update(1)

print(
    {
        "action": action,
        "processed": processed_count,
        "matched": matched_count,
        "marked": marked_count,
        "already_marked": already_marked_count,
        "deleted": deleted_count,
        "empty_text_skipped": empty_text_count,
    }
)
