# Generated manually to add We Work Remotely as an import source.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0035_schedule_remote_ok_import"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="source",
            field=models.CharField(
                choices=[
                    ("Hacker News", "Hacker News"),
                    ("Remote OK", "Remote OK"),
                    ("We Work Remotely", "We Work Remotely"),
                ],
                default="Hacker News",
                max_length=200,
            ),
        ),
    ]
