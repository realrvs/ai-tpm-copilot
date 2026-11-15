"""Report generator — produces Markdown from structured report data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ai_tpm_copilot.models.domain import LLMReport

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates Markdown reports from validated LLMReport data."""

    SECTION_TITLES: ClassVar[dict[str, str]] = {
        "completed": "## Выполнено",
        "in_progress": "## В работе",
        "blocked": "## Заблокировано",
        "risks": "## Риски",
    }

    def generate(self, report: LLMReport, since_days: int = 7) -> str:
        """Generate a Markdown status report.

        Args:
            report: Validated LLMReport.
            since_days: Number of days the report covers.

        Returns:
            Markdown-formatted report string.
        """
        lines: list[str] = []
        now = datetime.now(UTC)

        lines.append(f"# Статус проекта ({since_days} дней)")
        lines.append(f"**Дата формирования:** {now.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")

        for section_key, title in self.SECTION_TITLES.items():
            items = getattr(report, section_key)
            lines.append(title)
            lines.append("")

            if not items:
                lines.append("_Нет элементов._")
                lines.append("")
                continue

            for item in items:
                lines.append(f"- #{item.issue_id} **{item.title}**")
                if item.reason:
                    lines.append(f"  _{item.reason}_")

            lines.append("")

        # Unverified items section (at the end, as a note)
        if report.unverified_items:
            lines.append("---")
            lines.append("")
            lines.append(f"> **⚠️ Исключено непроверенных пунктов:** {len(report.unverified_items)}")
            for item in report.unverified_items:
                lines.append(f"> - #{item.issue_id} {item.title}")

        lines.append("")
        return "\n".join(lines)

    def to_markdown(self, report: LLMReport, since_days: int = 7) -> str:
        """Alias for :meth:`generate`."""
        return self.generate(report, since_days)
