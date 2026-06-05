import hashlib
import json
import logging
import time
from contextlib import contextmanager
from threading import RLock
from urllib.parse import unquote

import posthog
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from opentelemetry import trace


logger = logging.getLogger(__name__)

SYSTEM_DISTINCT_ID = "system:tjalerts"
SYSTEM_FLAG_DISTINCT_ID = "system:feature-flags"
MODEL_FLAG_CACHE_SECONDS = 300
_model_flag_cache = {}
_model_flag_cache_lock = RLock()


def posthog_enabled():
    return bool(getattr(settings, "POSTHOG_ENABLED", False) and getattr(settings, "POSTHOG_API_KEY", ""))


def distinct_id_for_user(user):
    if not user or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None

    return str(user.pk)


def distinct_id_for_email(email):
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return SYSTEM_DISTINCT_ID

    digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:24]
    return f"email:{digest}"


def distinct_id_for_request(request):
    user_distinct_id = distinct_id_for_user(getattr(request, "user", None))
    if user_distinct_id:
        return user_distinct_id

    browser_distinct_id = browser_distinct_id_from_request(request)
    if browser_distinct_id:
        return browser_distinct_id

    return SYSTEM_DISTINCT_ID


def browser_distinct_id_from_request(request):
    if not request:
        return None

    api_key = getattr(settings, "POSTHOG_API_KEY", "")
    if not api_key:
        return None

    cookie_name = f"ph_{api_key}_posthog"
    raw_cookie = getattr(request, "COOKIES", {}).get(cookie_name)
    if not raw_cookie:
        return None

    try:
        cookie_payload = json.loads(unquote(raw_cookie))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    distinct_id = cookie_payload.get("distinct_id")
    return str(distinct_id) if distinct_id else None


def alias_request_user(request):
    user_distinct_id = distinct_id_for_user(getattr(request, "user", None))
    browser_distinct_id = browser_distinct_id_from_request(request)

    if not user_distinct_id or not browser_distinct_id or browser_distinct_id == user_distinct_id:
        return None

    return safe_posthog_call(posthog.alias, previous_id=browser_distinct_id, distinct_id=user_distinct_id)


def capture_event(event, *, distinct_id=None, properties=None, groups=None, send_feature_flags=False):
    event_properties = {
        "environment": getattr(settings, "ENVIRONMENT", ""),
        **(properties or {}),
    }
    resolved_distinct_id = distinct_id or SYSTEM_DISTINCT_ID

    if resolved_distinct_id == SYSTEM_DISTINCT_ID:
        event_properties.setdefault("$process_person_profile", False)

    return safe_posthog_call(
        posthog.capture,
        distinct_id=resolved_distinct_id,
        event=event,
        properties=event_properties,
        groups=groups,
        send_feature_flags=send_feature_flags,
    )


def capture_request_event(request, event, *, properties=None, groups=None):
    return capture_event(
        event,
        distinct_id=distinct_id_for_request(request),
        properties=properties,
        groups=groups,
        send_feature_flags=True,
    )


def capture_user_event(user, event, *, properties=None):
    user_properties = properties or {}
    if getattr(user, "email", ""):
        user_properties = {
            "$set": {
                "email": user.email,
                "name": getattr(user, "name", ""),
                "is_staff": bool(getattr(user, "is_staff", False)),
                "is_superuser": bool(getattr(user, "is_superuser", False)),
                "paid": bool(getattr(user, "paid", False)),
            },
            **user_properties,
        }

    return capture_event(
        event,
        distinct_id=distinct_id_for_user(user),
        properties=user_properties,
        send_feature_flags=True,
    )


def group_identify(group_type, group_key, *, properties=None):
    return safe_posthog_call(posthog.group_identify, group_type, group_key, properties=properties or {})


def company_group(company):
    if not company:
        return None

    return {"company": str(company.id)}


def identify_company(company):
    if not company:
        return None

    return group_identify(
        "company",
        str(company.id),
        properties={
            "name": company.name,
            "slug": company.slug,
            "homepage": company.company_homepage_link,
        },
    )


def evaluate_flags(*, distinct_id=SYSTEM_FLAG_DISTINCT_ID, groups=None, person_properties=None, flag_keys=None):
    return safe_posthog_call(
        posthog.evaluate_flags,
        distinct_id=distinct_id,
        groups=groups,
        person_properties=person_properties,
        flag_keys=flag_keys,
    )


def model_from_feature_flag(flag_key, default_model):
    with _model_flag_cache_lock:
        cached_value = _model_flag_cache.get(flag_key)
        if cached_value and cached_value["expires_at"] > time.monotonic():
            return cached_value["model"]

        evaluations = evaluate_flags(flag_keys=[flag_key])
        if not evaluations:
            return cache_model_flag(flag_key, default_model)

        try:
            payload = evaluations.get_flag_payload(flag_key)
        except AttributeError:
            payload = None

        if isinstance(payload, dict) and payload.get("model"):
            return cache_model_flag(flag_key, payload["model"])

        if isinstance(payload, str) and payload.strip():
            return cache_model_flag(flag_key, payload.strip())

        try:
            flag_value = evaluations.get_flag(flag_key)
        except AttributeError:
            return cache_model_flag(flag_key, default_model)

        if isinstance(flag_value, str) and flag_value.strip() and flag_value not in ["true", "false"]:
            return cache_model_flag(flag_key, flag_value.strip())

        return cache_model_flag(flag_key, default_model)


def cache_model_flag(flag_key, model):
    with _model_flag_cache_lock:
        _model_flag_cache[flag_key] = {
            "model": model,
            "expires_at": time.monotonic() + MODEL_FLAG_CACHE_SECONDS,
        }
    return model


@contextmanager
def ai_span(name, *, attributes=None):
    tracer = trace.get_tracer("tjalerts.ai")
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def safe_posthog_call(fn, *args, **kwargs):
    if not posthog_enabled():
        return None

    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("PostHog call failed", extra={"error": str(e)})
        return None
