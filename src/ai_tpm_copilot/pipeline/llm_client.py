"""YandexGPT client — calls Yandex Cloud YandexGPT API."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, wait_exponential

from ai_tpm_copilot.models.domain import LLMReport, ReportItem

if TYPE_CHECKING:
    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────

YANDEXGPT_API_URL = "https://llm.api.cloud.yandex.net/generativeLlm/completions"


class YandexGPTError(Exception):
    """Raised when YandexGPT API returns an error."""


class YandexGPTClient:
    """Client for YandexGPT (Yandex Cloud Generative LLM API).

    Uses direct HTTP calls with IAM token authentication.
    """

    def __init__(self, settings: Settings):
        self._folder_id = settings.yandexgpt.folder_id
        self._iam_token = settings.yandexgpt.iam_token
        self._model_uri = settings.yandexgpt.model_uri
        self._max_tokens = settings.yandexgpt.max_tokens
        self._temperature = settings.yandexgpt.temperature
        self._max_retries = settings.yandexgpt.max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def generate(self, prompt: str) -> str:
        """Send prompt to YandexGPT and return the generated text.

        Args:
            prompt: Full prompt string (with XML isolation).

        Returns:
            Raw text response from YandexGPT.
        """
        body = {
            "modelUri": f"gpt://{self._folder_id}/{self._model_uri}",
            "completionOptions": {
                "stream": False,
                "maxTokens": self._max_tokens,
                "temperature": self._temperature,
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt,
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._iam_token}",
            "Content-Type": "application/json",
            "x-folder-id": self._folder_id,
        }

        logger.info("Calling YandexGPT (model=%s)", self._model_uri)
        import httpx

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(YANDEXGPT_API_URL, headers=headers, json=body)
            if resp.status_code == 401:
                raise YandexGPTError("YandexGPT auth failed — check IAM token")
            resp.raise_for_status()

        data = resp.json()
        result_text = self._extract_text(data)
        logger.info("YandexGPT returned %d chars", len(result_text))
        return result_text

    def _extract_text(self, response: dict) -> str:
        """Extract generated text from YandexGPT API response."""
        try:
            candidates = response.get("completion", {}).get("candidates", [])
            if candidates:
                return candidates[0].get("text", "")
        except (AttributeError, KeyError):
            pass

        # Fallback: try alternative response structure
        try:
            return response.get("result", {}).get("text", "")
        except (AttributeError, KeyError):
            pass

        logger.warning("Could not extract text from YandexGPT response: %s", json.dumps(response)[:200])
        return ""

    def parse_report(self, raw_text: str) -> LLMReport:
        """Parse raw LLM text into structured LLMReport.

        Extracts Issue IDs from markdown headings like "## Выполнено" and
        lists items with #N references.

        This is a basic parser — in production, use a more robust
        JSON-mode output from YandexGPT.
        """
        report = LLMReport()
        current_section: str | None = None

        section_map = {
            "выполнено": "completed",
            "в работе": "in_progress",
            "заблокировано": "blocked",
            "риски": "risks",
        }

        for line in raw_text.splitlines():
            line_lower = line.strip().lower()

            # Detect section headers
            for ru_key, en_key in section_map.items():
                if line_lower.startswith(f"## {ru_key}") or line_lower.startswith(f"- {ru_key}:"):
                    current_section = en_key
                    break

            if current_section is None:
                continue

            # Extract items from lines like "- #123 Title — reason"
            import re

            match = re.match(r"-\s*#(\d+)\s+(.+?)(?:\s*—\s*(.+))?$", line.strip())
            if match:
                issue_id = int(match.group(1))
                title = match.group(2).strip()
                reason = match.group(3).strip() if match.group(3) else ""
                item = ReportItem(issue_id=issue_id, title=title, reason=reason)
                getattr(report, current_section).append(item)

        logger.info(
            "Parsed report: completed=%d, in_progress=%d, blocked=%d, risks=%d",
            len(report.completed),
            len(report.in_progress),
            len(report.blocked),
            len(report.risks),
        )
        return report
