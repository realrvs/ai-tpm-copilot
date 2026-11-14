"""Unit tests for YandexGPT Client (TC-LLM-001..005).

Tests:
  TC-LLM-001: parse_report extracts items from all 4 sections
  TC-LLM-002: parse_report handles empty sections
  TC-LLM-003: parse_report handles missing reason
  TC-LLM-004: parse_report handles alternative response structure
  TC-LLM-005: parse_report handles malformed response
"""

from __future__ import annotations

import pytest

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.llm_client import YandexGPTClient


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for testing."""
    return Settings(
        github={"token": "ghp_test", "repos": ["t/t"]},
        yandexgpt={"folder_id": "test-folder", "iam_token": "test-token"},
        pii={"enabled": False},
        otel={"enabled": False},
        **overrides,
    )


# ─── TC-LLM-001: Parse all 4 sections ─────────────────────────────


def test_tc_llm_001_parse_all_sections():
    """TC-LLM-001: parse_report extracts items from completed, in_progress, blocked, risks."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = """\
## Выполнено
- #10 **Fixed login bug** — _resolved after code review_
- #12 **Updated docs** — _merged_

## В работе
- #11 **Working on API** — _in progress_
- #14 **Database migration** — _testing_

## Заблокировано
- #15 **Blocked by external API** — _waiting for partner_

## Риски
- #17 **Open >5 days** — _no activity since Nov 7_
"""

    report = client.parse_report(raw_text)

    assert len(report.completed) == 2
    assert report.completed[0].issue_id == 10
    assert report.completed[0].title == "**Fixed login bug**"
    assert report.completed[0].reason == "_resolved after code review_"
    assert report.completed[1].issue_id == 12

    assert len(report.in_progress) == 2
    assert report.in_progress[0].issue_id == 11
    assert report.in_progress[1].issue_id == 14

    assert len(report.blocked) == 1
    assert report.blocked[0].issue_id == 15
    assert "blocked" in report.blocked[0].reason.lower() or "waiting" in report.blocked[0].reason.lower()

    assert len(report.risks) == 1
    assert report.risks[0].issue_id == 17


# ─── TC-LLM-002: Empty sections ──────────────────────────────────


def test_tc_llm_002_empty_sections():
    """TC-LLM-002: parse_report handles empty sections gracefully."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = """\
## Выполнено
- #10 **Done**

## В работе

## Заблокировано

## Риски
- #20 **Risk item**
"""

    report = client.parse_report(raw_text)

    assert len(report.completed) == 1
    assert len(report.in_progress) == 0
    assert len(report.blocked) == 0
    assert len(report.risks) == 1


# ─── TC-LLM-003: Missing reason ──────────────────────────────────


def test_tc_llm_003_missing_reason():
    """TC-LLM-003: parse_report handles items without reason (empty string)."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = """\
## Выполнено
- #10 **Fixed bug**
- #12 **Updated code** — _minor fix_
"""

    report = client.parse_report(raw_text)

    assert report.completed[0].issue_id == 10
    assert report.completed[0].reason == ""
    assert report.completed[1].issue_id == 12
    assert report.completed[1].reason == "_minor fix_"


# ─── TC-LLM-004: Alternative response structure ──────────────────


def test_tc_llm_004_alternative_response_structure():
    """TC-LLM-004: _extract_text handles alternative YandexGPT response format."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    # Alternative structure with "result" key
    alt_response = {
        "result": {
            "text": "## Выполнено\n- #10 **Done**",
        },
    }

    text = client._extract_text(alt_response)
    assert text == "## Выполнено\n- #10 **Done**"


# ─── TC-LLM-005: Malformed response ──────────────────────────────


def test_tc_llm_005_malformed_response():
    """TC-LLM-005: _extract_text returns empty string for unparseable response."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    # Completely malformed response
    malformed = {"unexpected": {"key": {"nested": "data"}}}

    text = client._extract_text(malformed)
    assert text == ""


# ─── Additional edge cases ────────────────────────────────────────


def test_parse_report_with_dash_section_header():
    """parse_report handles '- section:' style headers."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = """\
- выполнено:
- #10 **Item** — _reason_
"""

    report = client.parse_report(raw_text)
    assert len(report.completed) == 1
    assert report.completed[0].issue_id == 10


def test_parse_report_no_sections():
    """parse_report returns empty report when no sections found."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = "This is just some text without any sections."

    report = client.parse_report(raw_text)

    assert len(report.completed) == 0
    assert len(report.in_progress) == 0
    assert len(report.blocked) == 0
    assert len(report.risks) == 0


def test_parse_report_mixed_case_sections():
    """parse_report handles mixed-case section headers."""
    settings = _make_settings()
    client = YandexGPTClient(settings)

    raw_text = """\
## ВЫПОЛНЕНО
- #10 **Done**

## В РАБОТЕ
- #11 **In progress**

## ЗАБЛОКИРОВАНО
- #12 **Blocked**

## РИСКИ
- #13 **Risk**
"""

    report = client.parse_report(raw_text)

    assert len(report.completed) == 1
    assert len(report.in_progress) == 1
    assert len(report.blocked) == 1
    assert len(report.risks) == 1
