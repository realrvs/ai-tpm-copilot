"""Unit tests for OpenTelemetry instrumentation (TC-OTEL-001..005).

Tests:
  TC-OTEL-001: OTelInstrumentation creates spans with correct names
  TC-OTEL-002: Spans include pipeline stage attributes
  TC-OTEL-003: Spans include numeric attributes (issue counts, etc.)
  TC-OTEL-004: Disabled OTel doesn't raise
  TC-OTEL-005: Pipeline integrates OTel spans
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.observability import (
    SPAN_GITHUB_FETCH,
    SPAN_LLM_GENERATE,
    SPAN_PII_REDACT,
    SPAN_PROMPT_BUILD,
    SPAN_REPORT_DELIVER,
    SPAN_REPORT_GENERATE,
    SPAN_REPORT_VALIDATE,
    OTelInstrumentation,
)


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for testing."""
    return Settings(
        github={"token": "ghp_test", "repos": ["t/t"]},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        pii={"enabled": False},
        **overrides,
    )


# ─── TC-OTEL-001: Span creation ───────────────────────────────────


def test_tc_otel_001_span_creation():
    """TC-OTEL-001: OTelInstrumentation creates spans with correct names."""
    settings = _make_settings(otel={"enabled": True})
    otel = OTelInstrumentation(settings)
    otel.setup()

    # Verify span context managers exist and are callable
    assert hasattr(otel, "github_fetch_span")
    assert hasattr(otel, "pii_redact_span")
    assert hasattr(otel, "prompt_build_span")
    assert hasattr(otel, "llm_generate_span")
    assert hasattr(otel, "report_validate_span")
    assert hasattr(otel, "report_generate_span")
    assert hasattr(otel, "report_deliver_span")


# ─── TC-OTEL-002: Span attributes ─────────────────────────────────


@patch("opentelemetry.trace.get_tracer")
def test_tc_otel_002_span_attributes(mock_get_tracer):
    """TC-OTEL-002: Spans include pipeline stage attributes."""
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_tracer.return_value = mock_tracer

    settings = _make_settings(otel={"enabled": True})
    otel = OTelInstrumentation(settings)
    otel._tracer = mock_tracer

    # Test github_fetch_span attributes
    with otel.github_fetch_span(repo_count=3, issue_count=15):
        pass

    # Verify set_attribute was called with stage and counts
    calls = [c for c in mock_span.set_attribute.call_args_list]
    stage_attrs = [c[0][0] for c in calls]
    assert "pipeline.stage" in stage_attrs
    assert "github.repo_count" in stage_attrs
    assert "github.issue_count" in stage_attrs


# ─── TC-OTEL-003: Numeric attributes ──────────────────────────────


@patch("opentelemetry.trace.get_tracer")
def test_tc_otel_003_numeric_attributes(mock_get_tracer):
    """TC-OTEL-003: Spans include numeric attributes (counts, lengths)."""
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_tracer.return_value = mock_tracer

    settings = _make_settings(otel={"enabled": True})
    otel = OTelInstrumentation(settings)
    otel._tracer = mock_tracer

    # Test pii_redact_span
    with otel.pii_redact_span(pii_count=5):
        pass

    # Test llm_generate_span
    with otel.llm_generate_span(prompt_length=2048):
        pass

    # Test report_validate_span
    with otel.report_validate_span(verified=10, unverified=2):
        pass

    # Test report_generate_span
    with otel.report_generate_span(since_days=14):
        pass

    # Test report_deliver_span
    with otel.report_deliver_span(method="telegram"):
        pass

    # Verify all numeric attributes were set
    calls = [c for c in mock_span.set_attribute.call_args_list]
    keys = [c[0][0] for c in calls]

    assert "pii.redacted_count" in keys
    assert "prompt.length" in keys
    assert "validation.verified" in keys
    assert "validation.unverified" in keys
    assert "report.since_days" in keys
    assert "delivery.method" in keys


# ─── TC-OTEL-004: Disabled OTel ───────────────────────────────────


def test_tc_otel_004_disabled_otel():
    """TC-OTEL-004: Disabled OTel doesn't raise on setup."""
    settings = _make_settings(otel={"enabled": False})
    otel = OTelInstrumentation(settings)

    # Should not raise
    otel.setup()

    # tracer should return a no-op
    tracer = otel.tracer
    assert tracer is not None


# ─── TC-OTEL-005: Pipeline integration ────────────────────────────


def test_tc_otel_005_pipeline_integration():
    """TC-OTEL-005: Pipeline integrates OTel spans."""
    from ai_tpm_copilot.pipeline.orchestrator import Pipeline

    settings = _make_settings(otel={"enabled": True})
    pipeline = Pipeline(settings)

    # Verify OTel instrumentation is attached
    assert pipeline._otel is not None
    assert isinstance(pipeline._otel, OTelInstrumentation)

    # Verify span methods exist
    assert hasattr(pipeline._otel, "github_fetch_span")
    assert hasattr(pipeline._otel, "pii_redact_span")
    assert hasattr(pipeline._otel, "prompt_build_span")
    assert hasattr(pipeline._otel, "llm_generate_span")
    assert hasattr(pipeline._otel, "report_validate_span")
    assert hasattr(pipeline._otel, "report_generate_span")
    assert hasattr(pipeline._otel, "report_deliver_span")


# ─── Additional: Span name constants ──────────────────────────────


def test_span_name_constants():
    """All span name constants are defined and non-empty."""
    assert SPAN_GITHUB_FETCH == "github.fetch"
    assert SPAN_PII_REDACT == "pii.redact"
    assert SPAN_PROMPT_BUILD == "prompt.build"
    assert SPAN_LLM_GENERATE == "llm.generate"
    assert SPAN_REPORT_VALIDATE == "report.validate"
    assert SPAN_REPORT_GENERATE == "report.generate"
    assert SPAN_REPORT_DELIVER == "report.deliver"
