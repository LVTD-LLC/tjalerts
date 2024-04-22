import structlog
from django.core.management.base import BaseCommand
from django_q.models import Schedule

from users.schedules import schedules

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Create django_q schedules"

    def handle(self, *args, **options):
        for schedule in schedules:
            if not Schedule.objects.filter(name=schedule["name"]).exists():
                Schedule.objects.create(
                    func=schedule["func_path"],
                    name=schedule["name"],
                    hook=schedule["hook"],
                    args=schedule["args"],
                    schedule_type=schedule["type"],
                )
            else:
                logger.info("Schedule already exists.", name=schedule["name"])
