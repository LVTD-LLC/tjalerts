from django.db import migrations


ALERT_DELIVERY_TASKS = (
    "jobs.tasks.find_users_to_alert",
    "jobs.tasks.send_alerts",
    "jobs.tasks.send_confirmation_email",
    "users.tasks.find_subs_to_alert",
    "users.tasks.send_alert",
    "users.tasks.send_confirmation_email",
)


def remove_alert_delivery_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(func__in=ALERT_DELIVERY_TASKS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("django_q", "0018_task_success_index"),
        ("jobs", "0039_technologyalias"),
    ]

    operations = [
        migrations.RunPython(remove_alert_delivery_schedules, migrations.RunPython.noop),
    ]
