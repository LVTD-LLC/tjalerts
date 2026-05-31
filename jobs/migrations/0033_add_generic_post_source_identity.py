# Generated manually to introduce a source-neutral post identity.

from django.db import migrations, models


def backfill_hacker_news_source_identity(apps, schema_editor):
    Post = apps.get_model("jobs", "Post")

    posts_to_update = []
    for post in (
        Post.objects.filter(source="Hacker News", who_is_hiring_comment_id__isnull=False)
        .only("id", "who_is_hiring_comment_id", "source_external_id", "source_url")
        .iterator()
    ):
        post.source_external_id = str(post.who_is_hiring_comment_id)
        post.source_url = f"https://news.ycombinator.com/item?id={post.who_is_hiring_comment_id}"
        posts_to_update.append(post)

        if len(posts_to_update) >= 500:
            Post.objects.bulk_update(posts_to_update, ["source_external_id", "source_url"])
            posts_to_update = []

    if posts_to_update:
        Post.objects.bulk_update(posts_to_update, ["source_external_id", "source_url"])


def clear_hacker_news_source_identity(apps, schema_editor):
    Post = apps.get_model("jobs", "Post")
    Post.objects.filter(source="Hacker News").update(source_external_id="", source_url="")


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0032_remove_company_emails_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="source",
            field=models.CharField(
                choices=[("Hacker News", "Hacker News"), ("Remote OK", "Remote OK")],
                default="Hacker News",
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="who_is_hiring_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="post",
            name="who_is_hiring_title",
            field=models.CharField(blank=True, max_length=25),
        ),
        migrations.AlterField(
            model_name="post",
            name="who_is_hiring_comment_id",
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="post",
            name="source_external_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="post",
            name="source_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="post",
            name="source_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_hacker_news_source_identity, clear_hacker_news_source_identity),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["source", "source_external_id"], name="index_post_source_ext_id"),
        ),
        migrations.AddConstraint(
            model_name="post",
            constraint=models.UniqueConstraint(
                condition=~models.Q(source_external_id=""),
                fields=("source", "source_external_id"),
                name="unique_post_source_external_id",
            ),
        ),
    ]
