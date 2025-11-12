from django.db import models


class PostSource(models.TextChoices):
    HACKER_NEWS = "Hacker News"


class EmailType(models.TextChoices):
    SPONSORSHIP_OUTREACH = "Sponsorship Outreach"
    ALERT_CONFIRMATION = "Alert Confirmation"
