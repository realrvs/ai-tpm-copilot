"""Pipeline orchestrator — connects all components into a single run."""

from __future__ import annotations

import logging
import time

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.models.domain import PipelineMetrics
from ai_tpm_copilot.pipeline.github_fetcher import GitHubFetcher
from ai_tpm_copilot.pipeline.llm_client import YandexGPTClient
from ai_tpm_copilot.pipeline.observability import OTelInstrumentation
from ai_tpm_copilot.pipeline.pii_redactor import PIIRedactor
from ai_tpm_copilot.pipeline.prompt_builder import PromptBuilder
from ai_tpm_copilot.pipeline.report_generator import ReportGenerator
from ai_tpm_copilot.pipeline.report_validator import ReportValidator

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the full status-report pipeline:

    GitHub Fetcher → PII Redactor → Prompt Builder → LLM Client →
    Report Validator → Report Generator

    Each stage is wrapped in an OpenTelemetry span for observability.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._fetcher = GitHubFetcher(settings)
        self._redactor = PIIRedactor(settings)
        self._prompt_builder = PromptBuilder(settings)
        self._llm_client = YandexGPTClient(settings)
        self._validator = None  # set after fetch
        self._report_generator = ReportGenerator()
        self._otel = OTelInstrumentation(settings)
        self._otel.setup()

    def run(self, since_days: int | None = None) -> str:
        """Execute the full pipeline and return the Markdown report.

        Each stage is instrumented with an OpenTelemetry span.

        Args:
            since_days: Override default history window.

        Returns:
            Generated Markdown report string.
        """
        start = time.monotonic()
        metrics = PipelineMetrics()
        logger.info("Pipeline started (since_days=%s)", since_days)

        # Step 1: Fetch
        with self._otel.github_fetch_span():
            issues = self._fetcher.fetch(since_days=since_days)
            metrics.issues_fetched = len(issues)
            if not issues:
                logger.warning("No issues found — pipeline will produce empty report")

        # Step 2: PII Redact
        redaction_results = []
        total_pii = 0
        with self._otel.pii_redact_span():
            for issue in issues:
                result = self._redactor.redact(issue.text_content)
                redaction_results.append(result)
                total_pii += result.redacted_count
        metrics.pii_redacted_count = total_pii
        if total_pii > 0:
            logger.info("PII redaction complete: %d items redacted", total_pii)

        # Step 3: Build prompt
        with self._otel.prompt_build_span(issue_count=len(issues)):
            prompt = self._prompt_builder.build(issues, redaction_results)

        # Step 4: LLM generation
        with self._otel.llm_generate_span(prompt_length=len(prompt)):
            raw_text = self._llm_client.generate(prompt)
            report = self._llm_client.parse_report(raw_text)

        # Step 5: Validate
        valid_ids = {issue.number for issue in issues}
        with self._otel.report_validate_span():
            self._validator = ReportValidator(self._settings, valid_ids)
            report = self._validator.validate(report)

        # Step 6: Generate Markdown
        since = since_days or self._settings.github.since_days
        with self._otel.report_generate_span(since_days=since):
            markdown = self._report_generator.generate(report, since_days=since)

        # Metrics
        metrics.pipeline_duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Pipeline completed in %.1fms: %d issues, %d PII redacted, %d unverified",
            metrics.pipeline_duration_ms,
            metrics.issues_fetched,
            metrics.pii_redacted_count,
            len(report.unverified_items),
        )

        return markdown
