"""Cron scheduler — periodic pipeline execution via APScheduler.

Usage:
    ai-tpm schedule --interval 3600   # every hour
    ai-tpm schedule --cron "0 9 * * 1"  # every Monday at 9:00
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import TYPE_CHECKING

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ai_tpm_copilot.pipeline.observability import OTelInstrumentation
from ai_tpm_copilot.pipeline.orchestrator import Pipeline
from ai_tpm_copilot.pipeline.output import FileWriter, TelegramSender

if TYPE_CHECKING:
    from pathlib import Path

    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger("ai_tpm_copilot.scheduler")

# Global flag for graceful shutdown
_running = True


def _signal_handler(signum: int, frame) -> None:
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    global _running
    logger.info("Received signal %d — shutting down gracefully...", signum)
    _running = False


def _run_pipeline(
    settings: Settings,
    days: int = 7,
    deliver: str = "file",
    output_dir: Path | None = None,
) -> dict:
    """Execute a single pipeline run and return metrics."""
    start = time.monotonic()
    try:
        pipeline = Pipeline(settings)
        markdown = pipeline.run(since_days=days)

        # Deliver
        if deliver in ("file", "both"):
            fw = FileWriter(output_dir or settings.report.output_dir)
            fw.write(markdown)

        if deliver in ("telegram", "both") and settings.enable_telegram_delivery:
            import asyncio

            tg = TelegramSender(settings)
            success = asyncio.run(tg.send(markdown))
            if not success:
                logger.warning("Telegram delivery failed — report saved to file only")

        duration_ms = (time.monotonic() - start) * 1000
        logger.info("Pipeline run completed in %.1fms", duration_ms)
        return {"status": "success", "duration_ms": duration_ms}

    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("Pipeline run failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc), "duration_ms": duration_ms}


def schedule(
    settings: Settings,
    interval: int | None = None,
    cron_expression: str | None = None,
    days: int = 7,
    deliver: str = "file",
) -> None:
    """Start the cron scheduler.

    Args:
        settings: Application settings.
        interval: Run every N seconds (mutually exclusive with cron).
        cron_expression: Cron expression (e.g. "0 9 * * 1").
        days: Days of history to fetch.
        deliver: Delivery method (file, telegram, both).
    """
    if not interval and not cron_expression:
        logger.error("Must specify either --interval or --cron")
        sys.exit(1)

    if interval and cron_expression:
        logger.error("Cannot specify both --interval and --cron")
        sys.exit(1)

    # Setup signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Setup OTel
    otel = OTelInstrumentation(settings)
    otel.setup()

    scheduler = BlockingScheduler()

    if cron_expression:
        trigger = CronTrigger.from_crontab(cron_expression)
        logger.info("Scheduling pipeline with cron: %s", cron_expression)
    else:
        trigger = IntervalTrigger(seconds=interval)
        logger.info("Scheduling pipeline every %d seconds", interval)

    scheduler.add_job(
        _run_pipeline,
        trigger=trigger,
        args=[settings, days, deliver, settings.report.output_dir],
        id="tpm_pipeline",
        name="AI TPM Copilot Status Report",
        max_instances=1,  # prevent overlapping runs
        replace_existing=True,
    )

    logger.info(
        "Scheduler started. Output dir: %s, Deliver: %s",
        settings.report.output_dir,
        deliver,
    )
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
