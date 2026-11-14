"""Unit tests for Report Generator (TC-REPORT-001..004).

Tests:
  TC-REPORT-001: Generate Markdown with all 4 sections
  TC-REPORT-002: Empty sections show "Нет элементов."
  TC-REPORT-003: Unverified items section at end
  TC-REPORT-004: Custom since_days value
"""

from __future__ import annotations

import pytest

from ai_tpm_copilot.models.domain import LLMReport, ReportItem
from ai_tpm_copilot.pipeline.report_generator import ReportGenerator


def _make_report(
    completed: list[ReportItem] | None = None,
    in_progress: list[ReportItem] | None = None,
    blocked: list[ReportItem] | None = None,
    risks: list[ReportItem] | None = None,
    unverified: list[ReportItem] | None = None,
) -> LLMReport:
    """Create an LLMReport with given items."""
    return LLMReport(
        completed=completed or [],
        in_progress=in_progress or [],
        blocked=blocked or [],
        risks=risks or [],
        unverified_items=unverified or [],
    )


# ─── TC-REPORT-001: All 4 sections ────────────────────────────────


def test_tc_report_001_all_sections():
    """TC-REPORT-001: Generated Markdown contains all 4 section headers."""
    generator = ReportGenerator()
    report = _make_report(
        completed=[ReportItem(issue_id=10, title="Fixed bug", reason="PR merged")],
        in_progress=[ReportItem(issue_id=11, title="API work", reason="In review")],
        blocked=[ReportItem(issue_id=12, title="Waiting for API", reason="External")],
        risks=[ReportItem(issue_id=13, title="Stale issue", reason="No updates")],
    )

    markdown = generator.generate(report, since_days=7)

    assert "# Статус проекта (7 дней)" in markdown
    assert "## Выполнено" in markdown
    assert "## В работе" in markdown
    assert "## Заблокировано" in markdown
    assert "## Риски" in markdown
    assert "#10" in markdown
    assert "#11" in markdown
    assert "#12" in markdown
    assert "#13" in markdown


# ─── TC-REPORT-002: Empty sections ────────────────────────────────


def test_tc_report_002_empty_sections():
    """TC-REPORT-002: Empty sections display 'Нет элементов.'."""
    generator = ReportGenerator()
    report = _make_report()

    markdown = generator.generate(report, since_days=7)

    assert "## Выполнено" in markdown
    assert "## В работе" in markdown
    assert "## Заблокировано" in markdown
    assert "## Риски" in markdown
    assert "_Нет элементов._" in markdown
    # Count occurrences — should appear 4 times (once per section)
    assert markdown.count("_Нет элементов._") == 4


# ─── TC-REPORT-003: Unverified items ──────────────────────────────


def test_tc_report_003_unverified_items():
    """TC-REPORT-003: Unverified items appear in a warning section at the end."""
    generator = ReportGenerator()
    report = _make_report(
        completed=[ReportItem(issue_id=10, title="Valid item")],
        unverified=[
            ReportItem(issue_id=999, title="Fake item"),
            ReportItem(issue_id=888, title="Another fake"),
        ],
    )

    markdown = generator.generate(report, since_days=7)

    assert "## Выполнено" in markdown
    assert "#10" in markdown
    assert "---" in markdown
    # Check for the warning line using the emoji marker
    assert "⚠️" in markdown
    assert "непроверенных" in markdown
    assert "#999" in markdown
    assert "#888" in markdown


# ─── TC-REPORT-004: Custom since_days ─────────────────────────────


def test_tc_report_004_custom_since_days():
    """TC-REPORT-004: Report header reflects custom since_days value."""
    generator = ReportGenerator()
    report = _make_report(completed=[ReportItem(issue_id=1, title="Test")])

    markdown = generator.generate(report, since_days=30)

    assert "# Статус проекта (30 дней)" in markdown

    # Default should be 7
    markdown_default = generator.generate(report)
    assert "# Статус проекта (7 дней)" in markdown_default


# ─── Additional edge cases ────────────────────────────────────────


def test_report_includes_date():
    """Report includes a date line."""
    generator = ReportGenerator()
    report = _make_report()

    markdown = generator.generate(report)

    assert "**Дата формирования:**" in markdown
    assert "UTC" in markdown


def test_report_item_format():
    """Report items are formatted as '- #N **title**' with optional reason."""
    generator = ReportGenerator()
    report = _make_report(
        completed=[
            ReportItem(issue_id=10, title="Fixed bug", reason="PR merged"),
            ReportItem(issue_id=11, title="No reason item"),
        ],
    )

    markdown = generator.generate(report)

    assert "- #10 **Fixed bug**" in markdown
    assert "_PR merged_" in markdown
    assert "- #11 **No reason item**" in markdown
    # Item without reason should not have an indented reason line
    lines = markdown.splitlines()
    no_reason_idx = next(i for i, line in enumerate(lines) if "#11" in line)
    if no_reason_idx + 1 < len(lines):
        next_line = lines[no_reason_idx + 1]
        assert not next_line.startswith("  _") or "PR merged" in next_line


def test_to_markdown_alias():
    """to_markdown is an alias for generate."""
    generator = ReportGenerator()
    report = _make_report(completed=[ReportItem(issue_id=1, title="Test")])

    assert generator.to_markdown(report) == generator.generate(report)


def test_report_only_risks():
    """Report with only risks section."""
    generator = ReportGenerator()
    report = _make_report(risks=[ReportItem(issue_id=5, title="Potential delay")])

    markdown = generator.generate(report)

    assert "## Выполнено" in markdown
    assert "_Нет элементов._" in markdown  # first 3 sections
    assert "## Риски" in markdown
    assert "#5" in markdown
    assert "Potential delay" in markdown
