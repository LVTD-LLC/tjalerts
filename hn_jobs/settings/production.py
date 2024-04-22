# ruff: noqa: F403, F405

from .base import *

LOGGING["loggers"]["django.server"]["level"] = "WARNING"
LOGGING["loggers"]["hnjobs"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")
LOGGING["loggers"]["hnjobs"]["handlers"].append("json_console")
LOGGING["loggers"]["django_structlog"]["handlers"].append("json_console")
