"""Output module — delivers reports via Telegram or file."""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone

from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)


class FileWriter:
    """Saves reports to local filesystem."""

    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    def write(self, report: str) -> Path:
        """Write report to `reports/status_YYYY-MM-DD.md`.

        Args:
            report: Markdown report string.

        Returns:
            Path to the written file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = self._output_dir / f"status_{date_str}.md"
        filepath.write_text(report, encoding="utf-8")
        logger.info("Report written to %s (%d chars)", filepath, len(report))
        return filepath


class TelegramSender:
    """Sends reports to Telegram via aiogram."""

    def __init__(self, settings: Settings):
        self._bot_token = settings.telegram_bot_token
        self._chat_id = settings.telegram.chat_id if settings.telegram else None
        self._parse_mode = (
            settings.telegram.parse_mode if settings.telegram else "Markdown"
        )

    async def send(self, report: str) -> bool:
        """Send report to Telegram.

        Args:
            report: Markdown report string.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._bot_token or not self._chat_id:
            logger.warning("Telegram not configured — skipping delivery")
            return False

        try:
            import aiogram
            from aiogram import Bot

            bot = Bot(token=self._bot_token)
            # Telegram has a 4096 char limit per message; split if needed
            chunks = self._split_report(report)
            for chunk in chunks:
                await bot.send_message(
                    chat_id=self._chat_id,
                    text=chunk,
                    parse_mode=self._parse_mode,
                )
            await bot.close()
            logger.info("Report sent to Telegram chat %s", self._chat_id)
            return True
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return False

    @staticmethod
    def _split_report(report: str, max_len: int = 4000) -> list[str]:
        """Split a report into chunks that fit Telegram's 4096 char limit."""
        if len(report) <= max_len:
            return [report]

        chunks = []
        while report:
            # Find last newline before limit to avoid splitting mid-section
            cut = report[:max_len].rfind("\n\n")
            if cut == -1:
                cut = max_len
            chunks.append(report[:cut])
            report = report[cut:].lstrip("\n")
        return chunks
