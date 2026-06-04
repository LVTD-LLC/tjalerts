from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0037_post_job_details"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["created"], name="index_post_created"),
        ),
    ]
