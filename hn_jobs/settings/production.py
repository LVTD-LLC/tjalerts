# ruff: noqa: F403, F405

from .base import *

LOGGING["loggers"]["hn_jobs"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")
LOGGING["loggers"]["hn_jobs"]["handlers"] = ["json_console"]
LOGGING["loggers"]["django_structlog"]["handlers"] = ["json_console"]
