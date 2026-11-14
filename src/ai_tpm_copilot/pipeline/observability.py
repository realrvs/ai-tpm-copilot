"""OpenTelemetry instrumentation for the pipeline."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)


class OTelInstrumentation:
    """Sets up OpenTelemetry tracing for the pipeline.

    Creates spans for each pipeline stage:
    github.fetch, pii.redact, llm.generate, report.deliver
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._tracer = None

    def setup(self) -> None:
        """Initialize the OTel tracer provider."""
        if not self._settings.otel.enabled:
            logger.debug("OpenTelemetry disabled")
            return

        resource = Resource.create(
            {"service.name": self._settings.otel.service_name}
        )
        provider = TracerProvider(resource=resource)

        # Export to console (for development)
        # In production, replace with OTLP exporter
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(__name__)
        logger.info(
            "OpenTelemetry initialized (service=%s)",
            self._settings.otel.service_name,
        )

    @property
    def tracer(self):
        """Return the tracer instance, or a no-op if not initialized."""
        if self._tracer is None:
            return trace.get_tracer(__name__)
        return self._tracer
