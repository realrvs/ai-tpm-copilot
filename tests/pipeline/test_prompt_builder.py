"""Unit tests for Prompt Builder (T-004, TC-PROMPT-001..004).

Tests:
  TC-PROMPT-001: Prompt contains XML isolation tags
  TC-PROMPT-002: Sanitized content used in prompt
  TC-PROMPT-003: PII redaction metadata included
  TC-PROMPT-004: System prompt is constant
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.models.domain import GitHubIssue, IssueComment, RedactionResult
from ai_tpm_copilot.pipeline.prompt_builder import PromptBuilder


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for testing."""
    return Settings(
        github={"token": "ghp_test", "repos": ["t/t"], "since_days": 7},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        pii={"enabled": False},
        otel={"enabled": False},
        **overrides,
    )


def _make_issue(number: int, title: str, body: str = "", state: str = "open") -> GitHubIssue:
    """Create a minimal GitHubIssue."""
    return GitHubIssue(
        id=1000 + number,
        number=number,
        title=title,
        body=body,
        state=state,
        comments=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_redaction(sanitized: str, redacted_count: int = 0, pii_types: list[str] | None = None) -> RedactionResult:
    """Create a RedactionResult."""
    return RedactionResult(
        original=sanitized,
        sanitized=sanitized,
        redacted_count=redacted_count,
        pii_types=pii_types or [],
    )


# ─── TC-PROMPT-001: XML isolation ─────────────────────────────────


def test_tc_prompt_001_xml_isolation():
    """TC-PROMPT-001: Prompt contains <system-instructions> and <user-data> tags."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    issues = [_make_issue(1, "Test issue", "Test body")]
    results = [_make_redaction("Test body")]
    prompt = builder.build(issues, results)

    assert "<system-instructions>" in prompt
    assert "</system-instructions>" in prompt
    assert "<user-data>" in prompt
    assert "</user-data>" in prompt
    assert prompt.index("<system-instructions>") < prompt.index("<user-data>")


# ─── TC-PROMPT-002: Sanitized content ─────────────────────────────


def test_tc_prompt_002_sanitized_content():
    """TC-PROMPT-002: Prompt uses sanitized (redacted) text, not original."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    original_text = "Contact: ivan@example.com, SNILS: 123-456-789-00"
    sanitized_text = "Contact: [EMAIL_REDACTED], SNILS: [SNILS_REDACTED]"

    issue = _make_issue(5, "Bug report", original_text)
    result = RedactionResult(original=original_text, sanitized=sanitized_text, redacted_count=2, pii_types=["EMAIL", "SNILS"])

    prompt = builder.build([issue], [result])

    # Sanitized text should be in prompt
    assert "[EMAIL_REDACTED]" in prompt
    assert "[SNILS_REDACTED]" in prompt
    # Original PII should NOT be in prompt
    assert "123-456-789-00" not in prompt
    assert "ivan@example.com" not in prompt


# ─── TC-PROMPT-003: PII redaction metadata ────────────────────────


def test_tc_prompt_003_pii_metadata_included():
    """TC-PROMPT-003: PII redaction count and types are included in prompt."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    issue = _make_issue(10, "Contains PII", "Personal data: 123-456-789-00")
    result = RedactionResult(
        original="Personal data: 123-456-789-00",
        sanitized="Personal data: [SNILS_REDACTED]",
        redacted_count=1,
        pii_types=["SNILS"],
    )

    prompt = builder.build([issue], [result])

    assert "[PII: 1 items redacted: SNILS]" in prompt


# ─── TC-PROMPT-004: System prompt constant ────────────────────────


def test_tc_prompt_004_system_prompt_constant():
    """TC-PROMPT-004: System prompt is a stable constant."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    system_prompt = builder.system_prompt

    assert "Ты — помощ TPM" in system_prompt
    assert "Используй ТОЛЬКО информацию из раздела <user-data>" in system_prompt
    assert "## Правила" in system_prompt
    assert "completed" in system_prompt
    assert "blocked" in system_prompt
    assert "risks" in system_prompt

    # Multiple builds return same system prompt
    assert builder.system_prompt == system_prompt


# ─── Additional edge cases ────────────────────────────────────────


def test_prompt_empty_issues():
    """Prompt builder handles empty issue list."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    prompt = builder.build([], [])
    assert "<user-data>" in prompt
    assert "Данные из GitHub" in prompt


def test_prompt_multiple_issues():
    """Prompt builder includes all issues with separators."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    issues = [
        _make_issue(1, "First issue", "Body 1"),
        _make_issue(2, "Second issue", "Body 2"),
        _make_issue(3, "Third issue", "Body 3"),
    ]
    results = [
        _make_redaction("Body 1"),
        _make_redaction("Body 2"),
        _make_redaction("Body 3"),
    ]

    prompt = builder.build(issues, results)

    assert "#1" in prompt
    assert "#2" in prompt
    assert "#3" in prompt
    assert "First issue" in prompt
    assert "Second issue" in prompt
    assert "Third issue" in prompt


def test_prompt_with_comments():
    """Prompt builder includes issue comments in text content."""
    settings = _make_settings()
    builder = PromptBuilder(settings)

    issue = _make_issue(
        1,
        "Issue with comments",
        "Main body",
    )
    # GitHubIssue is frozen, create with comments directly
    issue = GitHubIssue(
        id=1001,
        number=1,
        title="Issue with comments",
        body="Main body",
        state="open",
        comments=[
            IssueComment(id=1, body="First comment", author="user1"),
            IssueComment(id=2, body="Second comment", author="user2"),
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    results = [_make_redaction("Main body\nFirst comment\nSecond comment")]
    prompt = builder.build([issue], results)

    assert "Main body" in prompt
    assert "First comment" in prompt
    assert "Second comment" in prompt


def test_prompt_days_placeholder():
    """Prompt includes the correct days value."""
    settings = _make_settings()
    settings.github.since_days = 30
    builder = PromptBuilder(settings)

    prompt = builder.build([], [])
    assert "30 дней" in prompt
