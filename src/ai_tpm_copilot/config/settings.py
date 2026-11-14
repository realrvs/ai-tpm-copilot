"""Application configuration — loaded from ENV + config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubConfig(BaseModel):
    """GitHub API settings."""

    token: SecretStr = Field(description="GitHub personal access token (repo scope)")
    repos: list[str] = Field(
        default=["realrvs/ai-tax-assistant"],
        description="List of owner/repo to scrape",
    )
    since_days: int = Field(default=7, ge=1, le=90, description="Days of history to fetch")
    per_page: int = Field(default=100, ge=1, le=100, description="Items per API page")
    max_retries: int = Field(default=3, ge=1, le=10, description="HTTP retry count")


class YandexGPTConfig(BaseModel):
    """YandexGPT (Yandex Cloud) settings."""

    folder_id: str = Field(description="Yandex Cloud folder ID")
    iam_token: SecretStr = Field(description="Yandex IAM token for YandexGPT")
    model_uri: str = Field(
        default="gpt://b1gkq2m1ic840rc2gva8/YandexGPT_Lite",
        description="Full model URI in YC",
    )
    max_tokens: int = Field(default=4096, ge=64, description="Max output tokens")
    temperature: float = Field(default=0.3, ge=0, le=1, description="Sampling temperature")
    max_retries: int = Field(default=3, ge=1, le=10, description="HTTP retry count")


class TelegramConfig(BaseModel):
    """Telegram bot settings."""

    bot_token: SecretStr = Field(description="Telegram bot API token")
    chat_id: str = Field(description="Target chat/channel ID")
    parse_mode: Literal["Markdown", "HTML"] = Field(
        default="Markdown", description="Message parse mode"
    )


class PIIConfig(BaseModel):
    """PII redaction settings."""

    enabled: bool = Field(default=True)
    use_presidio: bool = Field(default=True)
    custom_patterns: dict[str, str] = Field(
        default_factory=lambda: {
            "SNILS": r"\b\d{3}-\d{3}-\d{2}\s\d{2}\b",
            "INN_PERSON": r"\b\d{12}\b",
            "INN_ORG": r"\b\d{10}\b",
            "PASSPORT_RF": r"\b\d{4}\s\d{6}\b",
        },
        description="Custom regex patterns for RU-specific PII",
    )


class ReportConfig(BaseModel):
    """Report generation settings."""

    token_limit: int = Field(default=32000, ge=1024, description="Max tokens per LLM call")
    fact_check_strict: bool = Field(default=True)
    fuzzy_matching: bool = Field(default=True)
    output_dir: Path = Field(
        default=Path("reports"), description="Directory for file-based report output"
    )


class OTelConfig(BaseModel):
    """OpenTelemetry settings."""

    enabled: bool = Field(default=True)
    service_name: str = Field(default="ai-tpm-copilot")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="OTLP gRPC endpoint")


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GitHub
    github: GitHubConfig = Field(default_factory=GitHubConfig)

    # YandexGPT (default LLM provider, per ADR decision)
    yandexgpt: YandexGPTConfig = Field(default_factory=YandexGPTConfig)

    # Telegram (optional, gated by feature flag)
    telegram: TelegramConfig | None = None

    # PII
    pii: PIIConfig = Field(default_factory=PIIConfig)

    # Report
    report: ReportConfig = Field(default_factory=ReportConfig)

    # Observability
    otel: OTelConfig = Field(default_factory=OTelConfig)

    # Feature flags
    enable_telegram_delivery: bool = Field(default=False)
    enable_fact_check_strict: bool = Field(default=True)
    enable_llm_provider_yandexgpt: bool = Field(default=True)
    enable_fuzzy_matching: bool = Field(default=True)
    enable_pii_redaction_presidio: bool = Field(default=True)

    @classmethod
    def load(cls) -> Settings:
        """Load settings from ENV. Raises on missing required fields."""
        return cls()

    @property
    def github_token(self) -> str:
        return self.github.token.get_secret_value()

    @property
    def yandexgpt_iam_token(self) -> str:
        return self.yandexgpt.iam_token.get_secret_value()

    @property
    def telegram_bot_token(self) -> str | None:
        if self.telegram is not None:
            return self.telegram.bot_token.get_secret_value()
        return None
