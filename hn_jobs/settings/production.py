# ruff: noqa: F403, F405

from .base import *

LOGGING["loggers"]["django.server"]["level"] = "WARNING"
LOGGING["loggers"]["django_structlog"]["handlers"].append("json_console")
LOGGING["loggers"]["tjalerts"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")
LOGGING["loggers"]["tjalerts"]["handlers"].append("json_console")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}
