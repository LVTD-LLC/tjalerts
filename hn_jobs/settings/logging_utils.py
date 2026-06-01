import logging

import logfire
import sentry_sdk

SENTRY_LOG_METHODS = {
    "debug": sentry_sdk.logger.debug,
    "info": sentry_sdk.logger.info,
    "warning": sentry_sdk.logger.warning,
    "warn": sentry_sdk.logger.warning,
    "error": sentry_sdk.logger.error,
    "critical": sentry_sdk.logger.fatal,
    "fatal": sentry_sdk.logger.fatal,
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


def normalize_telemetry_attribute(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"

    return str(value)


def enrich_sentry_log(log, _hint):
    log.setdefault("attributes", {})
    log["attributes"]["service.name"] = "tjalerts"
    return log


def enrich_sentry_metric(metric, _hint):
    metric.setdefault("attributes", {})
    metric["attributes"]["service.name"] = "tjalerts"
    return metric


def send_structlog_to_sentry(_logger, _method_name, event_dict):
    level = event_dict.get("level", "info")
    log_method = SENTRY_LOG_METHODS.get(level, sentry_sdk.logger.info)
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

    try:
        log_method(message, attributes=attributes)
    except Exception:
        return event_dict

    return event_dict
