import time

import sentry_sdk
from django.conf import settings


class SentryMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.SENTRY_DSN or not settings.SENTRY_ENABLE_METRICS:
            return self.get_response(request)

        start_time = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        route = "unknown"
        if getattr(request, "resolver_match", None) and request.resolver_match.view_name:
            route = request.resolver_match.view_name

        attributes = {
            "http.request.method": request.method,
            "http.response.status_code": response.status_code,
            "http.response.status_class": f"{response.status_code // 100}xx",
            "http.route": route,
        }

        sentry_sdk.metrics.count("tjalerts.http.server.requests", 1, attributes=attributes)
        sentry_sdk.metrics.distribution(
            "tjalerts.http.server.duration",
            duration_ms,
            unit="millisecond",
            attributes=attributes,
        )

        return response
