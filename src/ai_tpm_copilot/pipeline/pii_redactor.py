"""PII redaction module — cleans PII from text using Presidio + custom regex."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from ai_tpm_copilot.models.domain import RedactionResult

if TYPE_CHECKING:
    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)

# ─── Presidio imports (lazy to avoid startup cost if disabled) ──

_presidio_analyzer: Any = None
_presidio_pattern_registry: Any = None


def _load_presidio() -> tuple[Any, Any] | tuple[None, None]:
    """Lazy-load Presidio components."""
    try:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

        return AnalyzerEngine(), PatternRecognizer
    except ImportError:
        logger.warning("presidio-analyzer not installed; PII redaction will use regex-only mode")
        return None, None


# ─── RU-specific regex patterns ─────────────────────────────────

_DEFAULT_CUSTOM_PATTERNS: dict[str, str] = {
    "SNILS": r"\b\d{3}-\d{3}-\d{2}\s\d{2}\b",
    "INN_PERSON": r"\b\d{12}\b",
    "INN_ORG": r"\b\d{10}\b",
    "PASSPORT_RF": r"\b\d{4}\s\d{6}\b",
}


class PIIRedactor:
    """Redacts PII from text using Presidio Analyzer + custom regex.

    Presidio runs first, then custom regex patterns fill gaps for
    Russian-specific formats (СНИЛС, ИНН, паспорт).
    """

    def __init__(self, settings: Settings):
        self._enabled = settings.pii.enabled
        self._use_presidio = settings.pii.use_presidio and settings.enable_pii_redaction_presidio
        self._custom_patterns: dict[str, str] = {
            **_DEFAULT_CUSTOM_PATTERNS,
            **settings.pii.custom_patterns,
        }

        if self._use_presidio:
            analyzer, _ = _load_presidio()
            if analyzer is None:
                self._use_presidio = False
                logger.warning("Presidio unavailable — falling back to regex-only PII redaction")
            else:
                self._analyzer = analyzer
        else:
            self._use_presidio = False

    def redact(self, text: str) -> RedactionResult:
        """Redact all PII from *text*.

        Args:
            text: Raw text (Issue body, comment, etc.).

        Returns:
            RedactionResult with sanitized text and statistics.
        """
        if not self._enabled or not text:
            return RedactionResult(original=text, sanitized=text)

        sanitized = text
        total_redacted = 0
        pii_types: set[str] = set()

        # Step 1: Presidio (if available)
        if self._use_presidio:
            results = self._analyzer.analyze(text=text, language="ru")
            # Process in reverse order to preserve positions
            for entity in sorted(results, key=lambda r: r.start, reverse=True):
                placeholder = f"[{entity.entity_type.upper()}_REDACTED]"
                sanitized = sanitized[: entity.start] + placeholder + sanitized[entity.end :]
                total_redacted += 1
                pii_types.add(entity.entity_type)
                logger.debug(
                    "Presidio redacted %s at pos %d-%d",
                    entity.entity_type,
                    entity.start,
                    entity.end,
                )

        # Step 2: Custom regex patterns
        for pii_type, pattern in self._custom_patterns.items():
            matches = list(re.finditer(pattern, sanitized))
            if matches:
                placeholder = f"[{pii_type}_REDACTED]"
                sanitized = re.sub(pattern, placeholder, sanitized)
                total_redacted += len(matches)
                pii_types.add(pii_type)

        return RedactionResult(
            original=text,
            sanitized=sanitized,
            redacted_count=total_redacted,
            pii_types=sorted(pii_types),
        )
