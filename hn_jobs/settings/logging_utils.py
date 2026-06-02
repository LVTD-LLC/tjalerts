import json
import logging
from collections.abc import Mapping
from uuid import UUID

import logfire
import sentry_sdk


SENTRY_LOG_METHOD_NAMES = {
    "debug": "debug",
    "info": "info",
    "warning": "warning",
    "warn": "warning",
    "error": "error",
    "critical": "fatal",
    "fatal": "fatal",
}


def get_sentry_log_method(level):
    logger = getattr(sentry_sdk, "logger", None)
    if logger is None:
        return None

    method_name = SENTRY_LOG_METHOD_NAMES.get(level, "info")
    return getattr(logger, method_name, None)


SENTRY_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
}

SENTRY_STRUCTLOG_RESERVED_KEYS = {
    "event",
    "level",
    "logger",
    "timestamp",
    "exc_info",
    "stack_info",
    "_record",
}


def scrubbing_callback(m: logfire.ScrubMatch):
    if m.path == ("attributes", "cookies"):
        return m.value


def stable_json_sort_key(value):
    return json.dumps(value, sort_keys=True, default=str)


def normalize_telemetry_attribute(value):
    if value is None:
        return ""

    if isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"

    if isinstance(value, (list, tuple)):
        return [normalize_telemetry_attribute(item) for item in value]

    if isinstance(value, (set, frozenset)):
        normalized = [normalize_telemetry_attribute(item) for item in value]
        return json.dumps(sorted(normalized, key=stable_json_sort_key), sort_keys=True, default=str)

    if isinstance(value, Mapping):
        normalized = {str(key): normalize_telemetry_attribute(item) for key, item in value.items()}
        return json.dumps(normalized, sort_keys=True, default=str)

    return str(value)


def normalize_telemetry_body(value):
    normalized = normalize_telemetry_attribute(value)
    if isinstance(normalized, str):
        return normalized

    return json.dumps(normalized, sort_keys=True, default=str)


def normalize_telemetry_attributes(attributes):
    return {str(key): normalize_telemetry_attribute(value) for key, value in (attributes or {}).items()}


def normalize_structlog_event(_logger, _method_name, event_dict):
    return {
        key: value if key in SENTRY_STRUCTLOG_RESERVED_KEYS else normalize_telemetry_attribute(value)
        for key, value in event_dict.items()
    }


def enrich_sentry_log(log, _hint):
    log["attributes"] = normalize_telemetry_attributes(log.get("attributes"))
    log["attributes"]["service.name"] = "tjalerts"
    return log


def enrich_sentry_metric(metric, _hint):
    metric["attributes"] = normalize_telemetry_attributes(metric.get("attributes"))
    metric["attributes"]["service.name"] = "tjalerts"
    return metric


def send_structlog_to_sentry(_logger, _method_name, event_dict, *, min_level=logging.INFO):
    try:
        level = str(event_dict.get("level") or _method_name or "info").lower()
        if SENTRY_LOG_LEVELS.get(level, logging.INFO) < min_level:
            return event_dict

        log_method = get_sentry_log_method(level)
        if log_method is None:
            return event_dict

        message = str(event_dict.get("event", ""))

        attributes = {
            "sentry.origin": "auto.log.structlog",
            "logger.name": normalize_telemetry_attribute(event_dict.get("logger")),
        }

        record = event_dict.get("_record")
        if isinstance(record, logging.LogRecord):
            attributes.update(
                {
                    "code.file.path": record.pathname,
                    "code.function.name": record.funcName,
                    "code.line.number": record.lineno,
                    "process.pid": record.process,
                    "thread.id": record.thread,
                    "thread.name": record.threadName,
                }
            )

        for key, value in event_dict.items():
            if key not in SENTRY_STRUCTLOG_RESERVED_KEYS:
                attributes[key] = normalize_telemetry_attribute(value)

        log_method(message, attributes=attributes)
    except Exception:
        return event_dict

    return event_dict
