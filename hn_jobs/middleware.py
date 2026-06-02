import logging
import time

import sentry_sdk
from django.conf import settings


logger = logging.getLogger(__name__)


def route_name_from_request(request):
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match and resolver_match.view_name:
        return resolver_match.view_name

    return "unknown"


def capture_http_server_metrics(request, *, duration_ms, status_code, error=None):
    attributes = {
        "http.request.method": request.method,
        "http.response.status_code": status_code,
        "http.response.status_class": f"{status_code // 100}xx",
        "http.route": route_name_from_request(request),
    }
    if error is not None:
        attributes["error.type"] = type(error).__name__

    if settings.SENTRY_ENABLE_METRICS:
        try:
            sentry_sdk.metrics.count("tjalerts.http.server.requests", 1, attributes=attributes)
            sentry_sdk.metrics.distribution(
                "tjalerts.http.server.duration",
                duration_ms,
                unit="millisecond",
                attributes=attributes,
            )
        except Exception:
            logger.debug("Failed to emit Sentry request metrics", exc_info=True)

    if settings.SENTRY_ENABLE_LOGS:
        try:
            sentry_sdk.logger.info(
                "tjalerts.http.server.request",
                attributes={
                    **attributes,
                    "metric.name": "tjalerts.http.server.duration",
                    "metric.value": duration_ms,
                    "metric.unit": "millisecond",
                    "service.name": "tjalerts",
                },
            )
        except Exception:
            logger.debug("Failed to emit Sentry request log", exc_info=True)


class SentryMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.SENTRY_DSN or not (settings.SENTRY_ENABLE_METRICS or settings.SENTRY_ENABLE_LOGS):
            return self.get_response(request)

        start_time = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception as error:
            duration_ms = (time.perf_counter() - start_time) * 1000
            capture_http_server_metrics(request, duration_ms=duration_ms, status_code=500, error=error)
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        capture_http_server_metrics(request, duration_ms=duration_ms, status_code=response.status_code)

        return response
