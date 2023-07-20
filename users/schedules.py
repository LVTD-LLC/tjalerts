from django_q.models import Schedule

schedules = [
    {
        "name": "Find Subs to Alert",
        "func_path": "users.tasks.find_subs_to_alert",
        "hook": "jobs.hooks.print_result",
        "args": None,
        "type": Schedule.MINUTES,
    },
]
