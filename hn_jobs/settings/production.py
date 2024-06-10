# ruff: noqa: F403, F405

from .base import *

LOGGING["loggers"]["tjalerts"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")
LOGGING["loggers"]["tjalerts"]["handlers"] = ["json_console"]
LOGGING["loggers"]["django_structlog"]["handlers"] = ["json_console"]

# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": env("REDIS_URL"),
#     }
# }
