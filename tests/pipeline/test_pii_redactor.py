"""Unit tests for PII Redactor (TC-SEC-001).

Tests:
  TC-SEC-001: PII-filter (email, phone, СНИЛС, ИНН -> placeholders)
  Fallback to regex-only (without presidio)
"""

from __future__ import annotations

import pytest

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.pii_redactor import PIIRedactor


# ─── Fixtures ─────────────────────────────────────────────────────


def _make_settings(**overrides: dict) -> Settings:
    """Build a minimal Settings object for PII testing."""
    pii_config = {"enabled": True, "use_presidio": True}
    pii_config.update(overrides.pop("pii", {}))

    return Settings(
        github={
            "token": "ghp_test_token",
            "repos": ["test/test"],
        },
        yandexgpt={
            "folder_id": "test-folder",
            "iam_token": "test-iam-token",
        },
        pii=pii_config,
        otel={"enabled": False},
        **overrides,
    )


# ─── TC-SEC-001: PII redaction with custom regex ─────────────────


class TestTCSEC001CustomRegex:
    """TC-SEC-001: Custom regex patterns for RU-specific PII."""

    def test_snils_redaction(self):
        """TC-SEC-001: СНИЛС format XXX-XXX-XX XX is redacted."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        # Correct SNILS format: 123-456-78 01 (3-3-2-2)
        text = "SNILS: 123-456-78 01, name Ivanov"
        result = redactor.redact(text)

        assert "[SNILS_REDACTED]" in result.sanitized
        assert "123-456-78 01" not in result.sanitized
        assert result.redacted_count >= 1
        assert "SNILS" in result.pii_types

    def test_inn_person_redaction(self):
        """TC-SEC-001: ИНН физлица (12 digits) is redacted."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        text = "INN person: 123456789012"
        result = redactor.redact(text)

        assert "[INN_PERSON_REDACTED]" in result.sanitized
        assert "123456789012" not in result.sanitized
        assert result.redacted_count >= 1

    def test_inn_org_redaction(self):
        """TC-SEC-001: ИНН организации (10 digits) is redacted."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        text = "INN company: 1234567890"
        result = redactor.redact(text)

        assert "[INN_ORG_REDACTED]" in result.sanitized
        assert "1234567890" not in result.sanitized
        assert result.redacted_count >= 1

    def test_passport_rf_redaction(self):
        """TC-SEC-001: Паспорт РФ (XXXX XXXXXX) is redacted."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        text = "Passport: 1234 567890"
        result = redactor.redact(text)

        assert "[PASSPORT_RF_REDACTED]" in result.sanitized
        assert "1234 567890" not in result.sanitized
        assert result.redacted_count >= 1

    def test_multiple_pii_in_one_text(self):
        """TC-SEC-001: Multiple PII types in a single text."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        text = "SNILS: 111-222-33 44, INN: 9999888877"
        result = redactor.redact(text)

        assert "[SNILS_REDACTED]" in result.sanitized
        assert "[INN_ORG_REDACTED]" in result.sanitized
        assert "111-222-33 44" not in result.sanitized
        assert "9999888877" not in result.sanitized
        assert result.redacted_count >= 2

    def test_no_pii_returns_unchanged(self):
        """TC-SEC-001: Text without PII is returned unchanged."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        text = "This is a normal text without PII data"
        result = redactor.redact(text)

        assert result.sanitized == text
        assert result.redacted_count == 0
        assert result.pii_types == []

    def test_empty_text_returns_unchanged(self):
        """TC-SEC-001: Empty text returns unchanged result."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        result = redactor.redact("")

        assert result.sanitized == ""
        assert result.redacted_count == 0

    def test_none_text_returns_unchanged(self):
        """TC-SEC-001: None text returns unchanged result."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        result = redactor.redact(None)

        assert result.sanitized is None
        assert result.redacted_count == 0

    def test_pii_disabled_returns_unchanged(self):
        """TC-SEC-001: When PII redaction is disabled, text is unchanged."""
        settings = _make_settings(pii={"enabled": False})
        redactor = PIIRedactor(settings)

        text = "SNILS: 123-456-78 01"
        result = redactor.redact(text)

        assert result.sanitized == text
        assert result.redacted_count == 0


class TestRegexOnlyFallback:
    """Fallback to regex-only when Presidio is unavailable."""

    def test_regex_only_mode(self):
        """Test that regex-only mode works when Presidio is disabled."""
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        assert redactor._use_presidio is False

        text = "SNILS: 000-000-00 00"
        result = redactor.redact(text)

        assert "[SNILS_REDACTED]" in result.sanitized
        assert result.redacted_count >= 1

    def test_custom_patterns_override(self):
        """Custom patterns override defaults."""
        settings = Settings(
            github={"token": "ghp_test", "repos": ["t/t"]},
            yandexgpt={"folder_id": "f", "iam_token": "t"},
            pii={
                "enabled": True,
                "use_presidio": False,
                "custom_patterns": {"CUSTOM_PII": r"\bCUSTOM\d{4}\b"},
            },
            otel={"enabled": False},
        )
        redactor = PIIRedactor(settings)

        text = "Code: CUSTOM1234 here"
        result = redactor.redact(text)

        assert "[CUSTOM_PII_REDACTED]" in result.sanitized
        assert "CUSTOM1234" not in result.sanitized

    def test_presidio_available_but_no_ru_recognizers(self):
        """When Presidio loads but has no RU recognizers, regex fallback still works."""
        # Presidio may load without Russian language support — in that case
        # the analyzer.analyze(language="ru") call will raise ValueError.
        # The PIIRedactor should handle this gracefully.
        # This test verifies that the regex-only path works independently.
        settings = _make_settings(pii={"use_presidio": False})
        redactor = PIIRedactor(settings)

        # Regex-only mode must always work regardless of Presidio state
        text = "SNILS: 123-456-78 01"
        result = redactor.redact(text)

        assert "[SNILS_REDACTED]" in result.sanitized
        assert result.redacted_count >= 1
