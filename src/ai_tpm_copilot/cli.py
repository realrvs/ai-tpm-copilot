"""CLI entry point for AI TPM Copilot."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.observability import OTelInstrumentation
from ai_tpm_copilot.pipeline.orchestrator import Pipeline
from ai_tpm_copilot.pipeline.output import FileWriter, TelegramSender

if TYPE_CHECKING:
    pass

app = typer.Typer(
    name="ai-tpm",
    help="AI TPM Copilot — automated status reporting from GitHub",
    add_completion=False,
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ai_tpm_copilot")


@app.command()
def run(
    days: int = typer.Option(
        7, "--days", "-d", help="Number of days of history to analyze"
    ),
    deliver: str = typer.Option(
        "file",
        "--deliver",
        "-D",
        help="Delivery method: file, telegram, or both",
    ),
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        help="Path to config.yaml (optional, ENV takes precedence)",
    ),
) -> None:
    """Run the full pipeline: fetch → redact → LLM → validate → report."""
    # Load settings
    try:
        settings = Settings.load()
    except Exception as exc:
        logger.error("Failed to load settings: %s", exc)
        raise typer.Exit(code=1)

    # Setup observability
    otel = OTelInstrumentation(settings)
    otel.setup()

    # Run pipeline
    try:
        pipeline = Pipeline(settings)
        markdown = pipeline.run(since_days=days)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise typer.Exit(code=2)

    # Deliver
    if deliver in ("file", "both"):
        fw = FileWriter(settings.report.output_dir)
        fw.write(markdown)

    if deliver in ("telegram", "both") and settings.enable_telegram_delivery:
        tg = TelegramSender(settings)
        import asyncio

        success = asyncio.run(tg.send(markdown))
        if not success:
            logger.warning("Telegram delivery failed — report saved to file only")
    elif deliver == "telegram" and not settings.enable_telegram_delivery:
        logger.error(
            "Telegram delivery requested but feature flag ENABLE_TELEGRAM_DELIVERY is false"
        )
        raise typer.Exit(code=3)

    typer.echo("Done.")


@app.command()
def validate(
    config: Path = typer.Option(
        None, "--config", "-c", exists=True, dir_okay=False, help="Config file to validate"
    ),
) -> None:
    """Validate configuration without running the pipeline."""
    try:
        settings = Settings.load()
        typer.echo("Configuration is valid.")
        typer.echo(f"  GitHub repos: {settings.github.repos}")
        typer.echo(f"  YandexGPT model: {settings.yandexgpt.model_uri}")
        typer.echo(f"  PII redaction: {settings.pii.enabled}")
        typer.echo(f"  Telegram: {'enabled' if settings.enable_telegram_delivery else 'disabled'}")
    except Exception as exc:
        typer.echo(f"Configuration error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def schedule(
    interval: int = typer.Option(
        None, "--interval", "-i", help="Run every N seconds (e.g. 3600 for hourly)"
    ),
    cron: str = typer.Option(
        None, "--cron", "-cr", help="Cron expression (e.g. '0 9 * * 1' for Mon 9:00)"
    ),
    days: int = typer.Option(
        7, "--days", "-d", help="Number of days of history to analyze"
    ),
    deliver: str = typer.Option(
        "file",
        "--deliver",
        "-D",
        help="Delivery method: file, telegram, or both",
    ),
) -> None:
    """Run the pipeline on a schedule (cron/interval)."""
    try:
        settings = Settings.load()
    except Exception as exc:
        logger.error("Failed to load settings: %s", exc)
        raise typer.Exit(code=1)

    from ai_tpm_copilot.pipeline.scheduler import schedule as run_scheduler

    run_scheduler(
        settings=settings,
        interval=interval,
        cron_expression=cron,
        days=days,
        deliver=deliver,
    )


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
