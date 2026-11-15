"""OpenTelemetry instrumentation for the pipeline.

Creates spans for each pipeline stage:
  - github.fetch
  - pii.redact
  - prompt.build
  - llm.generate
  - report.validate
  - report.generate
  - report.deliver
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

if TYPE_CHECKING:
    from collections.abc import Generator

    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)

# ─── Span names ────────────────────────────────────────────────────

SPAN_GITHUB_FETCH = "github.fetch"
SPAN_PII_REDACT = "pii.redact"
SPAN_PROMPT_BUILD = "prompt.build"
SPAN_LLM_GENERATE = "llm.generate"
SPAN_REPORT_VALIDATE = "report.validate"
SPAN_REPORT_GENERATE = "report.generate"
SPAN_REPORT_DELIVER = "report.deliver"


class OTelInstrumentation:
    """Sets up OpenTelemetry tracing for the pipeline.

    Creates spans for each pipeline stage and provides
    context managers for instrumenting custom code blocks.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._tracer = None

    def setup(self) -> None:
        """Initialize the OTel tracer provider."""
        if not self._settings.otel.enabled:
            logger.debug("OpenTelemetry disabled")
            return

        resource = Resource.create({"service.name": self._settings.otel.service_name})
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

    @contextmanager
    def span(
        self, name: str, attributes: dict[str, str | int] | None = None
    ) -> Generator[trace.Span, None, None]:
        """Context manager that creates and yields a span.

        Usage:
            with otel.span(SPAN_GITHUB_FETCH, {"repos": 2}):
                issues = fetcher.fetch()
        """
        tracer = self._tracer or trace.get_tracer(__name__)
        if tracer is None:
            # Fallback: no-op context manager
            from contextlib import nullcontext

            with nullcontext() as span:
                yield span
            return

        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield span

    @contextmanager
    def github_fetch_span(
        self, repo_count: int = 0, issue_count: int = 0
    ) -> Generator[trace.Span, None, None]:
        """Span for GitHub fetch stage."""
        attrs = {
            "pipeline.stage": SPAN_GITHUB_FETCH,
            "github.repo_count": repo_count,
            "github.issue_count": issue_count,
        }
        with self.span(SPAN_GITHUB_FETCH, attrs) as span:
            yield span

    @contextmanager
    def pii_redact_span(self, pii_count: int = 0) -> Generator[trace.Span, None, None]:
        """Span for PII redaction stage."""
        attrs = {
            "pipeline.stage": SPAN_PII_REDACT,
            "pii.redacted_count": pii_count,
        }
        with self.span(SPAN_PII_REDACT, attrs) as span:
            yield span

    @contextmanager
    def prompt_build_span(self, issue_count: int = 0) -> Generator[trace.Span, None, None]:
        """Span for prompt building stage."""
        attrs = {
            "pipeline.stage": SPAN_PROMPT_BUILD,
            "prompt.issue_count": issue_count,
        }
        with self.span(SPAN_PROMPT_BUILD, attrs) as span:
            yield span

    @contextmanager
    def llm_generate_span(self, prompt_length: int = 0) -> Generator[trace.Span, None, None]:
        """Span for LLM generation stage."""
        attrs = {
            "pipeline.stage": SPAN_LLM_GENERATE,
            "prompt.length": prompt_length,
        }
        with self.span(SPAN_LLM_GENERATE, attrs) as span:
            yield span

    @contextmanager
    def report_validate_span(
        self, verified: int = 0, unverified: int = 0
    ) -> Generator[trace.Span, None, None]:
        """Span for report validation stage."""
        attrs = {
            "pipeline.stage": SPAN_REPORT_VALIDATE,
            "validation.verified": verified,
            "validation.unverified": unverified,
        }
        with self.span(SPAN_REPORT_VALIDATE, attrs) as span:
            yield span

    @contextmanager
    def report_generate_span(self, since_days: int = 7) -> Generator[trace.Span, None, None]:
        """Span for report generation stage."""
        attrs = {
            "pipeline.stage": SPAN_REPORT_GENERATE,
            "report.since_days": since_days,
        }
        with self.span(SPAN_REPORT_GENERATE, attrs) as span:
            yield span

    @contextmanager
    def report_deliver_span(self, method: str = "file") -> Generator[trace.Span, None, None]:
        """Span for report delivery stage."""
        attrs = {
            "pipeline.stage": SPAN_REPORT_DELIVER,
            "delivery.method": method,
        }
        with self.span(SPAN_REPORT_DELIVER, attrs) as span:
            yield span
