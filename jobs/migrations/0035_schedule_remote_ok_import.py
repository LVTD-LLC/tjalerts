from django.db import migrations
from django.utils import timezone


SCHEDULE_NAME = "import-remote-ok-jobs"
SCHEDULE_FUNC = "jobs.tasks.import_remote_ok_jobs"


def create_remote_ok_import_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")

    Schedule.objects.get_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": SCHEDULE_FUNC,
            "hook": "jobs.hooks.print_result",
            "schedule_type": "H",
            "repeats": -1,
            "next_run": timezone.now(),
        },
    )


def delete_remote_ok_import_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")

    Schedule.objects.filter(name=SCHEDULE_NAME, func=SCHEDULE_FUNC).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("django_q", "0018_task_success_index"),
        ("jobs", "0034_add_generic_post_source_identity"),
    ]

    operations = [
        migrations.RunPython(create_remote_ok_import_schedule, delete_remote_ok_import_schedule),
    ]
