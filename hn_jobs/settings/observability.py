import logging
import os

import posthog
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from posthog.ai.otel import PostHogSpanProcessor

from hn_jobs.settings.logging_utils import normalize_telemetry_attributes


logger = logging.getLogger(__name__)


class SanitizingOTelLoggingHandler(LoggingHandler):
    @staticmethod
    def _get_attributes(record):
        return normalize_telemetry_attributes(LoggingHandler._get_attributes(record))


def normalize_api_key(api_key):
    return str(api_key or "").strip()


def configure_posthog_client(*, api_key, host, enabled, debug):
    api_key = normalize_api_key(api_key)
    enabled = bool(enabled and api_key)

    posthog.project_api_key = api_key
    posthog.host = host
    posthog.disabled = not enabled
    posthog.debug = debug

    if enabled:
        posthog.enable_keep_alive()


def build_posthog_resource(*, environment):
    return Resource.create(
        {
            SERVICE_NAME: "tjalerts",
            DEPLOYMENT_ENVIRONMENT: environment,
        }
    )


def build_posthog_span_processor(*, api_key, ingest_host):
    api_key = normalize_api_key(api_key)
    if not api_key:
        return None

    return PostHogSpanProcessor(api_key=api_key, host=ingest_host)


def configure_posthog_ai_observability(*, api_key, ingest_host, environment, enabled):
    if not enabled or not api_key:
        return None

    span_processor = build_posthog_span_processor(api_key=api_key, ingest_host=ingest_host)
    provider = TracerProvider(resource=build_posthog_resource(environment=environment))
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)
    instrument_openai()

    return span_processor


def instrument_openai():
    try:
        OpenAIInstrumentor().instrument()
    except Exception as e:
        logger.warning("PostHog OpenAI instrumentation failed: %s", e)


def configure_posthog_logs(*, api_key, ingest_host, environment, enabled, timeout_seconds=10):
    api_key = normalize_api_key(api_key)
    if not enabled or not api_key:
        return False

    try:
        logger_provider = get_logger_provider()
        if not hasattr(logger_provider, "add_log_record_processor"):
            logger_provider = LoggerProvider(resource=build_posthog_resource(environment=environment))
            set_logger_provider(logger_provider)

        exporter = OTLPLogExporter(
            endpoint=f"{ingest_host.rstrip('/')}/i/v1/logs",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    except Exception as e:
        logger.warning("PostHog logs configuration failed: %s", e)
        return False

    return True


def configure_ai_capture_content(enabled):
    if enabled:
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "span_only"
