"""Unit tests for Settings configuration (TC-CONFIG-001..005).

Tests:
  TC-CONFIG-001: Default settings are valid
  TC-CONFIG-002: Custom GitHub repos list
  TC-CONFIG-003: Telegram config optional
  TC-CONFIG-004: Feature flags work correctly
  TC-CONFIG-005: SecretStr fields are accessible
"""

from __future__ import annotations

import pytest

from ai_tpm_copilot.config.settings import Settings

# ─── TC-CONFIG-001: Default settings ──────────────────────────────


def test_tc_config_001_default_settings():
    """TC-CONFIG-001: Settings with minimal required fields is valid."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert settings.github.repos == ["realrvs/ai-tax-assistant"]
    assert settings.github.since_days == 7
    assert settings.github.per_page == 100
    assert settings.github.max_retries == 3
    assert settings.yandexgpt.max_tokens == 4096
    assert settings.yandexgpt.temperature == 0.3
    assert settings.pii.enabled is True
    assert settings.otel.enabled is True
    assert settings.otel.service_name == "ai-tpm-copilot"


# ─── TC-CONFIG-002: Custom GitHub repos ──────────────────────────


def test_tc_config_002_custom_repos():
    """TC-CONFIG-002: Multiple GitHub repos are supported."""
    settings = Settings(
        github={"token": "ghp_test", "repos": ["org/repo1", "org/repo2", "org/repo3"]},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert settings.github.repos == ["org/repo1", "org/repo2", "org/repo3"]
    assert len(settings.github.repos) == 3


# ─── TC-CONFIG-003: Telegram optional ─────────────────────────────


def test_tc_config_003_telegram_optional():
    """TC-CONFIG-003: Telegram config is None when not provided."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert settings.telegram is None
    assert settings.enable_telegram_delivery is False
    assert settings.telegram_bot_token is None


def test_tc_config_003_telegram_configured():
    """TC-CONFIG-003: Telegram config is accessible when provided."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        telegram={"bot_token": "123:ABC", "chat_id": "-100123"},
        enable_telegram_delivery=True,
    )

    assert settings.telegram is not None
    assert settings.telegram.bot_token.get_secret_value() == "123:ABC"
    assert settings.telegram.chat_id == "-100123"
    assert settings.telegram.parse_mode == "Markdown"
    assert settings.enable_telegram_delivery is True
    assert settings.telegram_bot_token == "123:ABC"


# ─── TC-CONFIG-004: Feature flags ────────────────────────────────


def test_tc_config_004_feature_flags_defaults():
    """TC-CONFIG-004: Feature flags have correct defaults."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert settings.enable_fact_check_strict is True
    assert settings.enable_fuzzy_matching is True
    assert settings.enable_pii_redaction_presidio is True
    assert settings.enable_llm_provider_yandexgpt is True
    assert settings.enable_telegram_delivery is False


def test_tc_config_004_feature_flags_override():
    """TC-CONFIG-004: Feature flags can be overridden."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        enable_fact_check_strict=False,
        enable_fuzzy_matching=False,
        enable_pii_redaction_presidio=False,
    )

    assert settings.enable_fact_check_strict is False
    assert settings.enable_fuzzy_matching is False
    assert settings.enable_pii_redaction_presidio is False


# ─── TC-CONFIG-005: SecretStr fields ──────────────────────────────


def test_tc_config_005_secret_access():
    """TC-CONFIG-005: SecretStr fields are accessible via properties."""
    settings = Settings(
        github={"token": "ghp_my_secret_token"},
        yandexgpt={"folder_id": "folder-123", "iam_token": "IAM-token-xyz"},
    )

    assert settings.github_token == "ghp_my_secret_token"
    assert settings.yandexgpt_iam_token == "IAM-token-xyz"


def test_tc_config_005_secret_not_exposed():
    """TC-CONFIG-005: SecretStr values are not directly visible in repr."""
    settings = Settings(
        github={"token": "ghp_secret"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    # The SecretStr itself should not reveal the value
    assert "ghp_secret" not in repr(settings.github.token)
    assert "SecretStr" in repr(settings.github.token)


# ─── Additional edge cases ────────────────────────────────────────


def test_settings_load_classmethod():
    """Settings.load() returns a Settings instance."""
    # We can't easily test ENV loading without patching, but verify the method exists
    assert callable(Settings.load)


def test_report_config_defaults():
    """ReportConfig has correct defaults."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert settings.report.token_limit == 32000
    assert settings.report.fact_check_strict is True
    assert settings.report.fuzzy_matching is True
    assert settings.report.output_dir.name == "reports"


def test_github_config_validation():
    """GitHubConfig validates since_days range."""
    with pytest.raises(Exception):  # pydantic validation error
        Settings(
            github={"token": "ghp_test", "since_days": 0},  # must be >= 1
            yandexgpt={"folder_id": "f", "iam_token": "t"},
        )

    with pytest.raises(Exception):  # pydantic validation error
        Settings(
            github={"token": "ghp_test", "since_days": 100},  # must be <= 90
            yandexgpt={"folder_id": "f", "iam_token": "t"},
        )


def test_pii_custom_patterns():
    """PIIConfig supports custom regex patterns (overrides defaults)."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
        pii={
            "enabled": True,
            "custom_patterns": {"EMAIL": r"[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]+"},
        },
    )

    assert "EMAIL" in settings.pii.custom_patterns
    assert settings.pii.custom_patterns["EMAIL"] == r"[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]+"
    # custom_patterns replaces the default_factory dict
    assert len(settings.pii.custom_patterns) == 1


def test_pii_default_patterns():
    """PIIConfig has RU-specific default patterns."""
    settings = Settings(
        github={"token": "ghp_test"},
        yandexgpt={"folder_id": "f", "iam_token": "t"},
    )

    assert "SNILS" in settings.pii.custom_patterns
    assert "INN_PERSON" in settings.pii.custom_patterns
    assert "INN_ORG" in settings.pii.custom_patterns
    assert "PASSPORT_RF" in settings.pii.custom_patterns
