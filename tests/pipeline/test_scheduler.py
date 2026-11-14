"""Unit tests for Cron scheduler (TC-SCHED-001..004).

Tests:
  TC-SCHED-001: _run_pipeline returns success metrics
  TC-SCHED-002: _run_pipeline returns error metrics on failure
  TC-SCHED-003: schedule rejects both interval and cron
  TC-SCHED-004: schedule rejects neither interval nor cron
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.scheduler import _run_pipeline


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for testing."""
    return Settings(
        github={"token": "ghp_test", "repos": ["t/t"], "since_days": 7},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        pii={"enabled": False},
        otel={"enabled": False},
        report={"output_dir": Path("/tmp/test_reports")},
        **overrides,
    )


# ─── TC-SCHED-001: Success metrics ────────────────────────────────


@respx.mock
def test_tc_sched_001_success_metrics():
    """TC-SCHED-001: _run_pipeline returns success metrics on successful run."""
    settings = _make_settings()

    # Mock GitHub API
    issues = [{
        "id": 1000,
        "number": 10,
        "title": "Test issue",
        "body": "Test body",
        "state": "closed",
        "assignees": [],
        "labels": [],
        "created_at": "2026-11-14T00:00:00Z",
        "updated_at": "2026-11-14T00:00:00Z",
    }]
    respx.get(
        url__startswith="https://api.github.com/repos/t/t/issues"
    ).mock(return_value=httpx.Response(200, json=issues))
    respx.get(
        url="https://api.github.com/repos/t/t/issues/10/comments"
    ).mock(return_value=httpx.Response(200, json=[]))

    # Mock YandexGPT
    llm_response = {
        "completion": {
            "candidates": [{
                "text": """\
## Выполнено
- #10 **Test issue** — _closed_
""",
            }],
        },
    }
    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    result = _run_pipeline(settings, days=7, deliver="file")

    assert result["status"] == "success"
    assert "duration_ms" in result
    assert result["duration_ms"] >= 0


# ─── TC-SCHED-002: Error metrics ──────────────────────────────────


def test_tc_sched_002_error_metrics():
    """TC-SCHED-002: _run_pipeline returns error metrics on failure."""
    _make_settings()

    # Provide invalid settings that will cause pipeline to fail
    settings_with_bad_token = Settings(
        github={"token": "ghp_invalid", "repos": ["t/t"], "since_days": 7},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        pii={"enabled": False},
        otel={"enabled": False},
        report={"output_dir": Path("/tmp/test_reports")},
    )

    # Mock GitHub API to return 401
    with respx.mock:
        respx.get(
            url__startswith="https://api.github.com/repos/t/t/issues"
        ).mock(return_value=httpx.Response(401, json={"message": "Unauthorized"}))

        result = _run_pipeline(settings_with_bad_token, days=7, deliver="file")

        assert result["status"] == "error"
        assert "error" in result
        assert "duration_ms" in result


# ─── TC-SCHED-003: Reject both interval and cron ──────────────────


def test_tc_sched_003_reject_both():
    """TC-SCHED-003: schedule rejects specifying both interval and cron."""
    from ai_tpm_copilot.pipeline.scheduler import schedule

    settings = _make_settings()

    # Patch sys.exit to raise SystemExit so we can catch it
    def fake_exit(code=0):
        raise SystemExit(code)

    with patch("ai_tpm_copilot.pipeline.scheduler.sys.exit", fake_exit):
        with patch("ai_tpm_copilot.pipeline.scheduler.OTelInstrumentation"):
            with patch("ai_tpm_copilot.pipeline.scheduler.BlockingScheduler"):
                with patch("signal.signal"):
                    with pytest.raises(SystemExit):
                        schedule(settings, interval=3600, cron_expression="0 9 * * 1")


# ─── TC-SCHED-004: Reject neither interval nor cron ───────────────


def test_tc_sched_004_reject_neither():
    """TC-SCHED-004: schedule rejects specifying neither interval nor cron."""
    from ai_tpm_copilot.pipeline.scheduler import schedule

    settings = _make_settings()

    # Patch sys.exit to raise SystemExit so we can catch it
    def fake_exit(code=0):
        raise SystemExit(code)

    with patch("ai_tpm_copilot.pipeline.scheduler.sys.exit", fake_exit):
        with patch("ai_tpm_copilot.pipeline.scheduler.OTelInstrumentation"):
            with patch("ai_tpm_copilot.pipeline.scheduler.BlockingScheduler"):
                with patch("signal.signal"):
                    with pytest.raises(SystemExit):
                        schedule(settings)


# ─── Additional: Schedule with only interval ──────────────────────


def test_sched_with_only_interval():
    """Scheduler accepts interval-only configuration."""
    from ai_tpm_copilot.pipeline.scheduler import schedule

    settings = _make_settings()

    with patch("ai_tpm_copilot.pipeline.scheduler.BlockingScheduler") as mock_sched:
        mock_instance = MagicMock()
        mock_sched.return_value = mock_instance
        # Mock start() to raise KeyboardInterrupt immediately
        mock_instance.start.side_effect = KeyboardInterrupt()

        with patch("signal.signal"), contextlib.suppress(KeyboardInterrupt):
            schedule(settings, interval=3600)

        # Verify scheduler was started
        mock_instance.start.assert_called_once()


# ─── Additional: Schedule with only cron ──────────────────────────


def test_sched_with_only_cron():
    """Scheduler accepts cron-only configuration."""
    from ai_tpm_copilot.pipeline.scheduler import schedule

    settings = _make_settings()

    with patch("ai_tpm_copilot.pipeline.scheduler.BlockingScheduler") as mock_sched:
        mock_instance = MagicMock()
        mock_sched.return_value = mock_instance
        # Mock start() to raise KeyboardInterrupt immediately
        mock_instance.start.side_effect = KeyboardInterrupt()

        with patch("signal.signal"), contextlib.suppress(KeyboardInterrupt):
            schedule(settings, cron_expression="0 9 * * 1")

        # Verify scheduler was started
        mock_instance.start.assert_called_once()
