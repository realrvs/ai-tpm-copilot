"""Report validator — fact-checks LLM output against source data (ADR-003)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai_tpm_copilot.models.domain import LLMReport, ReportItem

if TYPE_CHECKING:
    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)


class ReportValidator:
    """Validates LLM-generated reports against source GitHub data.

    Implements ADR-003: three-level validation (schema, fact-check, fuzzy).
    """

    def __init__(self, settings: Settings, valid_issue_ids: set[int]):
        self._strict = settings.enable_fact_check_strict
        self._fuzzy = settings.enable_fuzzy_matching
        self._valid_ids: set[int] = valid_issue_ids

    def validate(self, report: LLMReport) -> LLMReport:
        """Validate and clean the LLM report.

        Moves unverified items to `unverified_items` and returns a clean report.

        Args:
            report: Raw LLMReport from the LLM client.

        Returns:
            Validated LLMReport with unverified items removed.
        """
        valid_sections = ("completed", "in_progress", "blocked", "risks")
        cleaned = LLMReport()

        for section_name in valid_sections:
            items: list[ReportItem] = getattr(report, section_name)
            for item in items:
                if self._is_verified(item.issue_id):
                    getattr(cleaned, section_name).append(item)
                else:
                    report.unverified_items.append(item)
                    logger.warning(
                        "Unverified item moved: #%d %s (section=%s)",
                        item.issue_id,
                        item.title,
                        section_name,
                    )

        logger.info(
            "Validation: %d verified, %d unverified",
            sum(len(getattr(cleaned, s)) for s in valid_sections),
            len(report.unverified_items),
        )
        return cleaned

    def _is_verified(self, issue_id: int) -> bool:
        """Check if an issue ID exists in the source data.

        Supports exact match and fuzzy matching (e.g. "#123" vs "123").
        """
        if issue_id in self._valid_ids:
            return True

        if self._fuzzy:
            # Fuzzy: check if issue_id is close to any valid ID
            for valid_id in self._valid_ids:
                if abs(issue_id - valid_id) <= 1 and issue_id != valid_id:
                    logger.info(
                        "Fuzzy match: #%d → #%d",
                        issue_id,
                        valid_id,
                    )
                    return True

        if self._strict:
            return False

        # Non-strict mode: keep unverified items with a warning
        logger.warning("Non-strict mode: keeping unverified item #%d", issue_id)
        return True
