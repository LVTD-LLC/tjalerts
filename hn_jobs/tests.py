import logging
from unittest.mock import patch

import posthog
from django.test import SimpleTestCase

from hn_jobs.settings.logging_utils import enrich_sentry_log, enrich_sentry_metric, normalize_telemetry_attribute
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

        assert normalize_telemetry_attribute({0.02}) == "{0.02}"
        assert normalize_telemetry_attribute(error) == "ValueError: broken"

    def test_sentry_log_and_metric_attributes_are_normalized(self):
        error = ValueError("broken")

        log = enrich_sentry_log({"attributes": {"ratio": {0.02}, "error": error}}, None)
        metric = enrich_sentry_metric({"attributes": {"ratio": {0.02}, "error": error}}, None)

        assert log["attributes"]["ratio"] == "{0.02}"
        assert log["attributes"]["error"] == "ValueError: broken"
        assert metric["attributes"]["ratio"] == "{0.02}"
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

        assert attributes["ratio"] == "{0.02}"
        assert attributes["error"] == "ValueError: broken"
