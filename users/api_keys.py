import hashlib
import secrets

from django.db import transaction

from .api_key_constants import API_KEY_PREFIX, API_KEY_VISIBLE_PREFIX_LENGTH
from .models import CustomUser, UserAPIKey


def parse_bearer_api_key(authorization_header):
    if not authorization_header:
        return None

    scheme, separator, token = authorization_header.strip().partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None

    token = token.strip()
    if not token.startswith(API_KEY_PREFIX):
        return None

    return token


def hash_api_key(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def rotate_user_api_key(user):
    api_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(api_key)

    with transaction.atomic():
        locked_user = CustomUser.objects.select_for_update().only("pk").get(pk=user.pk)
        key_record, _ = UserAPIKey.objects.update_or_create(
            user=locked_user,
            defaults={
                "key_hash": key_hash,
                "key_prefix": api_key[:API_KEY_VISIBLE_PREFIX_LENGTH],
            },
        )

    return key_record, api_key


def authenticate_api_key(api_key):
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return None

    try:
        return CustomUser.objects.only("pk", "is_active").get(
            api_key__key_hash=hash_api_key(api_key),
            is_active=True,
        )
    except CustomUser.DoesNotExist:
        return None
