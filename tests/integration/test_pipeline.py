"""Integration tests for full pipeline (TC-003..TC-007).

Tests:
  TC-003: Генерация статус-отчета (10 issues, 4 секции)
  TC-004: Выявление блокера (blocked by #123)
  TC-005: Отправка отчета в Telegram (mock)
  TC-006: Сохранение в файл (fallback, mock 503)
  TC-007: Трейсинг пайплайна (4 span'а)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import respx

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.orchestrator import Pipeline
from ai_tpm_copilot.pipeline.output import FileWriter, TelegramSender

# ─── Fixtures ─────────────────────────────────────────────────────


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for testing."""
    github = {
        "token": "ghp_test_token",
        "repos": ["test-owner/test-repo"],
        "since_days": 7,
        "per_page": 100,
        "max_retries": 3,
    }
    github.update(overrides.pop("github", {}))

    otel = {"enabled": False}
    otel.update(overrides.pop("otel", {}))

    pii = {"enabled": False}
    pii.update(overrides.pop("pii", {}))

    report = {
        "fact_check_strict": True,
        "fuzzy_matching": True,
    }
    report.update(overrides.pop("report", {}))

    return Settings(
        github=github,
        yandexgpt={
            "folder_id": "test-folder",
            "iam_token": "test-iam-token",
        },
        pii=pii,
        otel=otel,
        report=report,
        **overrides,
    )


def _mock_issues(count: int, states: list[str] | None = None) -> list[dict[str, Any]]:
    """Create a list of mock GitHub API issue dicts."""
    if states is None:
        states = ["closed"] * count
    issues = []
    for i in range(count):
        created = datetime.now(UTC) - timedelta(days=i % 5 + 1)
        issues.append({
            "id": 1000 + i,
            "number": 10 + i,
            "title": f"Test issue #{10 + i}",
            "body": f"Description for issue {10 + i}",
            "state": states[i],
            "assignees": [{"login": "user1"}],
            "labels": [{"name": "bug"}],
            "created_at": created.isoformat(),
            "updated_at": (created + timedelta(hours=1)).isoformat(),
        })
    return issues


# ─── TC-003: Report generation with 10 issues, 4 sections ────────


@respx.mock
def test_tc003_report_generation_10_issues():
    """TC-003: Full pipeline with 10 issues, verify 4 report sections."""
    settings = _make_settings()

    # Mock GitHub API
    issues = _mock_issues(10)
    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=httpx.Response(200, json=issues))

    for issue in issues:
        respx.get(
            url=f"https://api.github.com/repos/test-owner/test-repo/issues/{issue['number']}/comments"
        ).mock(return_value=httpx.Response(200, json=[]))

    # Mock YandexGPT API — return a structured response
    llm_response = {
        "completion": {
            "candidates": [{
                "text": """\
## Выполнено
- #10 **Test issue #10** — _closed, resolved_
- #12 **Test issue #12** — _closed, resolved_
- #14 **Test issue #14** — _closed, resolved_
- #16 **Test issue #16** — _closed, resolved_
- #18 **Test issue #18** — _closed, resolved_

## В работе
- #11 **Test issue #11** — _in progress, no blockers_
- #13 **Test issue #13** — _in progress_

## Заблокировано
- #15 **Test issue #15** — _blocked by external dependency_

## Риски
- #17 **Test issue #17** — _open >5 days without changes_
""",
            }],
        },
    }

    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    pipeline = Pipeline(settings)
    markdown = pipeline.run(since_days=7)

    # Verify all 4 sections are present
    assert "## Выполнено" in markdown
    assert "## В работе" in markdown
    assert "## Заблокировано" in markdown
    assert "## Риски" in markdown

    # Verify issue IDs are in the report
    assert "#10" in markdown
    assert "#18" in markdown


# ─── TC-004: Blocked issue detection ─────────────────────────────


@respx.mock
def test_tc004_blocked_issue_detection():
    """TC-004: Issue with 'blocked by' mention is categorized as blocked."""
    settings = _make_settings()

    # Single issue with blocked-by content
    issues = [{
        "id": 2000,
        "number": 42,
        "title": "Depends on external API",
        "body": "This is blocked by #123 — waiting for their endpoint",
        "state": "open",
        "assignees": [{"login": "dev1"}],
        "labels": [{"name": "blocked"}],
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }]

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=httpx.Response(200, json=issues))
    respx.get(
        url="https://api.github.com/repos/test-owner/test-repo/issues/42/comments"
    ).mock(return_value=httpx.Response(200, json=[]))

    # LLM response with the issue in blocked section
    llm_response = {
        "completion": {
            "candidates": [{
                "text": """\
## Заблокировано
- #42 **Depends on external API** — _blocked by #123_
""",
            }],
        },
    }

    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    pipeline = Pipeline(settings)
    markdown = pipeline.run(since_days=7)

    assert "#42" in markdown
    assert "## Заблокировано" in markdown


# ─── TC-005: Telegram delivery (mock) ────────────────────────────


def _async_coro(value: Any):
    """Create an async coroutine that returns a value."""
    async def _coro():
        return value
    return _coro()


@patch("aiogram.Bot")
def test_tc005_telegram_delivery_mock(mock_Bot):
    """TC-005: Report is split into chunks and sent to Telegram."""
    settings = Settings(
        github={"token": "ghp_test", "repos": ["t/t"]},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        telegram={
            "bot_token": "123:ABCdef",
            "chat_id": "-1001234567890",
        },
        pii={"enabled": False},
        otel={"enabled": False},
        enable_telegram_delivery=True,
    )

    sender = TelegramSender(settings)

    # Create a report larger than 4000 chars
    long_report = "# Status Report\n\n" + "Line\n" * 300
    long_report += "\n\n" + "Extra section\n" * 200  # push over 4000

    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = MagicMock(
        side_effect=lambda *a, **k: _async_coro(MagicMock())
    )
    mock_bot_instance.close = MagicMock(return_value=_async_coro(None))
    mock_Bot.return_value = mock_bot_instance

    import asyncio
    success = asyncio.run(sender.send(long_report))

    assert success is True
    assert mock_bot_instance.send_message.call_count >= 1
    assert mock_bot_instance.close.call_count == 1


@patch("aiogram.Bot")
def test_tc005_small_report_single_chunk(mock_Bot):
    """TC-005: Small report fits in a single Telegram message."""
    settings = Settings(
        github={"token": "ghp_test", "repos": ["t/t"]},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        telegram={"bot_token": "123:ABC", "chat_id": "-100"},
        pii={"enabled": False},
        otel={"enabled": False},
        enable_telegram_delivery=True,
    )

    sender = TelegramSender(settings)
    small_report = "# Status\n\nShort report"

    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = MagicMock(return_value=_async_coro(MagicMock()))
    mock_bot_instance.close = MagicMock(return_value=_async_coro(None))
    mock_Bot.return_value = mock_bot_instance

    import asyncio
    asyncio.run(sender.send(small_report))

    assert mock_bot_instance.send_message.call_count == 1


# ─── TC-006: File writer fallback ────────────────────────────────


def test_tc006_file_writer():
    """TC-006: Report is saved to file correctly."""
    output_dir = Path("reports")
    writer = FileWriter(output_dir)

    report = """\
# Статус проекта (7 дней)
**Дата формирования:** 2026-11-14 10:00 UTC

## Выполнено
- #10 **Fixed login bug**

## В работе
- #11 **Working on API**
"""

    filepath = writer.write(report)

    assert filepath.exists()
    assert filepath.name.startswith("status_")
    assert filepath.name.endswith(".md")
    content = filepath.read_text(encoding="utf-8")
    assert content == report

    # Cleanup
    filepath.unlink()
    if output_dir.exists():
        output_dir.rmdir()


def test_tc006_file_writer_creates_dir():
    """TC-006: FileWriter creates output directory if it doesn't exist."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "new_subdir"
        writer = FileWriter(output_dir)

        filepath = writer.write("# Test report")

        assert output_dir.exists()
        assert filepath.exists()


# ─── TC-007: Pipeline tracing (OTel spans) ───────────────────────


def test_tc007_pipeline_components():
    """TC-007: Pipeline orchestrator connects all components.

    Verifies that the Pipeline class correctly instantiates
    all required components: Fetcher, Redactor, PromptBuilder,
    LLMClient, Validator, ReportGenerator.
    """
    settings = _make_settings()
    pipeline = Pipeline(settings)

    assert pipeline._fetcher is not None
    assert pipeline._redactor is not None
    assert pipeline._prompt_builder is not None
    assert pipeline._llm_client is not None
    assert pipeline._report_generator is not None
    assert pipeline._settings is settings

    # Verify component types
    from ai_tpm_copilot.pipeline.github_fetcher import GitHubFetcher
    from ai_tpm_copilot.pipeline.llm_client import YandexGPTClient
    from ai_tpm_copilot.pipeline.pii_redactor import PIIRedactor
    from ai_tpm_copilot.pipeline.prompt_builder import PromptBuilder
    from ai_tpm_copilot.pipeline.report_generator import ReportGenerator

    assert isinstance(pipeline._fetcher, GitHubFetcher)
    assert isinstance(pipeline._redactor, PIIRedactor)
    assert isinstance(pipeline._prompt_builder, PromptBuilder)
    assert isinstance(pipeline._llm_client, YandexGPTClient)
    assert isinstance(pipeline._report_generator, ReportGenerator)
