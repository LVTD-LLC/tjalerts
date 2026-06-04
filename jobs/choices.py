from django.db import models


class PostSource(models.TextChoices):
    HACKER_NEWS = "Hacker News", "Hacker News"
    REMOTE_OK = "Remote OK", "Remote OK"
    WE_WORK_REMOTELY = "We Work Remotely", "We Work Remotely"
