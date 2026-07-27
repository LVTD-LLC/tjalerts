import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from model_utils.models import TimeStampedModel

from users.api_key_constants import API_KEY_VISIBLE_PREFIX_LENGTH
from utils.models import BaseModel


class CustomUser(AbstractUser):
    name = models.CharField(max_length=100, blank=True)
    paid = models.BooleanField(default=False)

    class Meta:
        db_table = "auth_user"


class UserAPIKey(TimeStampedModel):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="api_key")
    key_hash = models.CharField(max_length=64, unique=True)
    key_prefix = models.CharField(max_length=API_KEY_VISIBLE_PREFIX_LENGTH)

    class Meta:
        db_table = "users_api_key"


class Subscriber(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)

    email = models.EmailField()
    confirmed = models.BooleanField(default=False)
    unsubscribed = models.BooleanField(default=False)

    technology_selected = models.CharField(max_length=256)


class Alert(BaseModel):
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE)
