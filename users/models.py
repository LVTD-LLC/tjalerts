import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from model_utils.models import TimeStampedModel

from utils.models import BaseModel


class CustomUser(AbstractUser):
    name = models.CharField(max_length=100, blank=True)
    paid = models.BooleanField(default=False)

    class Meta:
        db_table = "auth_user"


class Subscriber(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField()
    confirmed = models.BooleanField(default=False)
    unsubscribed = models.BooleanField(default=False)

    technology_selected = models.CharField(max_length=256)


class Alert(BaseModel):
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE)
