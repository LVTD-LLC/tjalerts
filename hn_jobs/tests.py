import logging
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import posthog
from django.test import SimpleTestCase, override_settings

from hn_jobs.middleware import SentryMetricsMiddleware
from hn_jobs.settings.logging_utils import (
    enrich_sentry_log,
    enrich_sentry_metric,
    normalize_telemetry_attribute,
    normalize_telemetry_body,
)
from hn_jobs.settings.observability import (
    SanitizingOTelLoggingHandler,
    configure_posthog_ai_observability,
    configure_posthog_client,
)
from hn_jobs.sitemaps import HighestPaidJobsListicleSitemap


class SitemapTests(SimpleTestCase):
    def test_highest_paid_jobs_lastmod_returns_none_without_posts(self):
        technology = object()

        with patch("hn_jobs.sitemaps.Post.objects.filter") as filter_mock:
            filter_mock.return_value.aggregate.return_value = {"latest_date": None}

            assert HighestPaidJobsListicleSitemap().lastmod(technology) is None

        filter_mock.assert_called_once_with(technologies=technology)


class ObservabilityTests(SimpleTestCase):
    def test_normalize_telemetry_attribute_handles_exporter_unsafe_values(self):
        error = ValueError("broken")
        request_id = UUID("946539af-c999-421e-9ecb-65d47934c45c")

        assert normalize_telemetry_attribute({0.02}) == "[0.02]"
        assert normalize_telemetry_attribute({"beta", "alpha"}) == '["alpha", "beta"]'
        assert normalize_telemetry_attribute(error) == "ValueError: broken"
        assert normalize_telemetry_attribute(request_id) == "946539af-c999-421e-9ecb-65d47934c45c"
        assert normalize_telemetry_body([request_id]) == '["946539af-c999-421e-9ecb-65d47934c45c"]'
        assert (
            normalize_telemetry_attribute({"request_id": request_id})
            == '{"request_id": "946539af-c999-421e-9ecb-65d47934c45c"}'
        )

    def test_sentry_log_and_metric_attributes_are_normalized(self):
        error = ValueError("broken")

        log = enrich_sentry_log({"attributes": {"ratio": {0.02}, "error": error}}, None)
        metric = enrich_sentry_metric({"attributes": {"ratio": {0.02}, "error": error}}, None)

        assert log["attributes"]["ratio"] == "[0.02]"
        assert log["attributes"]["error"] == "ValueError: broken"
        assert metric["attributes"]["ratio"] == "[0.02]"
        assert metric["attributes"]["error"] == "ValueError: broken"

    def test_posthog_client_treats_whitespace_api_key_as_disabled(self):
        original_api_key = posthog.project_api_key
        original_disabled = posthog.disabled
        original_host = posthog.host
        original_debug = posthog.debug

        try:
            configure_posthog_client(api_key="   ", host="https://us.i.posthog.com", enabled=True, debug=False)

            assert posthog.project_api_key == ""
            assert posthog.disabled is True
        finally:
            posthog.project_api_key = original_api_key
            posthog.disabled = original_disabled
            posthog.host = original_host
            posthog.debug = original_debug

    def test_posthog_ai_observability_treats_whitespace_api_key_as_disabled(self):
        with patch("hn_jobs.settings.observability.build_posthog_span_processor") as build_processor_mock:
            result = configure_posthog_ai_observability(
                api_key="   ",
                ingest_host="https://us.i.posthog.com",
                environment="test",
                enabled=True,
            )

        assert result is None
        build_processor_mock.assert_not_called()

    def test_otel_log_handler_normalizes_record_extra_attributes(self):
        record = logging.LogRecord(
            name="tjalerts.test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="message",
            args=(),
            exc_info=None,
        )
        record.ratio = {0.02}
        record.error = ValueError("broken")

        attributes = SanitizingOTelLoggingHandler._get_attributes(record)

        assert attributes["ratio"] == "[0.02]"
        assert attributes["error"] == "ValueError: broken"

    def test_otel_log_handler_normalizes_structured_record_body(self):
        record = logging.LogRecord(
            name="tjalerts.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg={"request_id": UUID("946539af-c999-421e-9ecb-65d47934c45c")},
            args=(),
            exc_info=None,
        )

        translated = SanitizingOTelLoggingHandler()._translate(record)

        assert translated.body == '{"request_id": "946539af-c999-421e-9ecb-65d47934c45c"}'

        record.msg = [UUID("946539af-c999-421e-9ecb-65d47934c45c")]
        translated = SanitizingOTelLoggingHandler()._translate(record)

        assert translated.body == '["946539af-c999-421e-9ecb-65d47934c45c"]'

    @override_settings(SENTRY_DSN="https://public@example.com/1", SENTRY_ENABLE_METRICS=True, SENTRY_ENABLE_LOGS=True)
    def test_sentry_metrics_middleware_emits_metrics_and_structured_log(self):
        request = SimpleNamespace(method="GET", resolver_match=SimpleNamespace(view_name="jobs:list"))
        response = SimpleNamespace(status_code=200)
        middleware = SentryMetricsMiddleware(lambda _request: response)

        with (
            patch("hn_jobs.middleware.sentry_sdk.metrics.count") as count_mock,
            patch("hn_jobs.middleware.sentry_sdk.metrics.distribution") as distribution_mock,
            patch("hn_jobs.middleware.sentry_sdk.logger.info") as logger_mock,
        ):
            result = middleware(request)

        assert result is response
        count_mock.assert_called_once()
        distribution_mock.assert_called_once()
        logger_mock.assert_called_once()
        assert logger_mock.call_args.kwargs["attributes"]["http.route"] == "jobs:list"
        assert logger_mock.call_args.kwargs["attributes"]["http.response.status_code"] == 200

    @override_settings(SENTRY_DSN="https://public@example.com/1", SENTRY_ENABLE_METRICS=False, SENTRY_ENABLE_LOGS=True)
    def test_sentry_metrics_middleware_logs_when_metrics_are_disabled(self):
        request = SimpleNamespace(method="GET", resolver_match=SimpleNamespace(view_name="jobs:list"))
        response = SimpleNamespace(status_code=200)
        middleware = SentryMetricsMiddleware(lambda _request: response)

        with (
            patch("hn_jobs.middleware.sentry_sdk.metrics.count") as count_mock,
            patch("hn_jobs.middleware.sentry_sdk.metrics.distribution") as distribution_mock,
            patch("hn_jobs.middleware.sentry_sdk.logger.info") as logger_mock,
        ):
            result = middleware(request)

        assert result is response
        count_mock.assert_not_called()
        distribution_mock.assert_not_called()
        logger_mock.assert_called_once()

    @override_settings(SENTRY_DSN="https://public@example.com/1", SENTRY_ENABLE_METRICS=True, SENTRY_ENABLE_LOGS=True)
    def test_sentry_metrics_middleware_emits_exception_metric(self):
        request = SimpleNamespace(method="GET", resolver_match=SimpleNamespace(view_name="jobs:list"))

        def raise_error(_request):
            raise ValueError("broken")

        middleware = SentryMetricsMiddleware(raise_error)

        with (
            patch("hn_jobs.middleware.sentry_sdk.metrics.count") as count_mock,
            patch("hn_jobs.middleware.sentry_sdk.metrics.distribution") as distribution_mock,
            patch("hn_jobs.middleware.sentry_sdk.logger.info") as logger_mock,
        ):
            with self.assertRaises(ValueError):
                middleware(request)

        count_mock.assert_called_once()
        distribution_mock.assert_called_once()
        logger_mock.assert_called_once()
        assert logger_mock.call_args.kwargs["attributes"]["error.type"] == "ValueError"
        assert logger_mock.call_args.kwargs["attributes"]["http.response.status_code"] == 500
        assert logger_mock.call_args.kwargs["attributes"]["http.response.status_class"] == "5xx"
