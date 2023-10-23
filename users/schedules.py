from django_q.models import Schedule

schedules = [
    {
        "name": "Find Subs to Alert",
        "func_path": "users.tasks.find_subs_to_alert",
        "hook": "jobs.hooks.print_result",
        "args": None,
        # "type": Schedule.MINUTES,
        "type": Schedule.DAILY,
    },
    {
        "name": "Find HN Comments to Analyze",
        "func_path": "jobs.tasks.get_hn_pages_to_analyze",
        "hook": "jobs.hooks.print_result",
        # specify args in the admin panel
        "args": "36573871",
        "type": Schedule.DAILY,
    },
    {
        "name": "Create Valid Emails for Marketing",
        "func_path": "jobs.tasks.create_valid_emails",
        "hook": "jobs.hooks.print_result",
        "args": "",
        "type": Schedule.DAILY,
    },
    {
        "name": "Delete Duplicate Comments",
        "func_path": "jobs.tasks.delete_duplicate_jobs_posts",
        "hook": "jobs.hooks.print_result",
        "args": "",
        "type": Schedule.DAILY,
    },
]
