from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0036_add_we_work_remotely_post_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="job_details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
