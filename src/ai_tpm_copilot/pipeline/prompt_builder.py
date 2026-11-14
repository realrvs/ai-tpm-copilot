"""Prompt builder — assembles LLM prompt with XML isolation (ADR-002)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_tpm_copilot.config.settings import Settings
    from ai_tpm_copilot.models.domain import GitHubIssue, RedactionResult

logger = logging.getLogger(__name__)

# ─── System prompt template ─────────────────────────────────────

_SYSTEM_PROMPT = """\
Ты — помощ TPM (Technical Program Manager). Твоя задача — анализировать статус проекта
на основе данных из GitHub Issues и генерировать структурированный отчёт.

## Правила
1. Используй ТОЛЬКО информацию из раздела <user-data>.
2. Категоризируй каждый Issue в одну из секций:
   - completed: Issue закрыт (state=closed), работа завершена.
   - in_progress: Issue открыт, есть комментарии о прогрессе, нет блокеров.
   - blocked: Issue открыт и заблокирован (упоминается "blocked by", "ждём", "зависит от").
   - risks: Issue открыт >5 дней без изменений или содержит слова "риск", "проблема", "задержка".
3. Каждый пункт отчёта должен содержать issue_id, title и reason.
4. Если Issue не попадает ни в одну категорию — не включай в отчёт.
5. Отвечай на русском языке.
6. Не выдумывай факты. Если информации недостаточно — укажи "недостаточно данных".
"""

# ─── Prompt template ────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
<system-instructions>
{system_prompt}
</system-instructions>

<user-data>
Данные из GitHub за последние {days} дней:

{issues_text}
</user-data>

Сгенерируй отчёт в формате Markdown с секциями: Выполнено, В работе, Заблокировано, Риски.
Каждый пункт должен содержать Issue ID (#N), название и краткое обоснование.
"""


class PromptBuilder:
    """Builds LLM prompts with XML-isolated user data (ADR-002)."""

    def __init__(self, settings: Settings):
        self._system_prompt = _SYSTEM_PROMPT
        self._days = settings.github.since_days

    def build(
        self,
        issues: list[GitHubIssue],
        redaction_results: list[RedactionResult],
    ) -> str:
        """Assemble the full LLM prompt.

        Args:
            issues: List of GitHub issues (already fetched).
            redaction_results: Corresponding PII redaction results.

        Returns:
            Full prompt string with XML isolation.
        """
        # Build per-issue text from sanitized content
        issue_texts: list[str] = []
        for issue, result in zip(issues, redaction_results, strict=True):
            issue_texts.append(f"--- Issue #{issue.number} ({issue.state}) ---")
            issue_texts.append(f"Title: {issue.title}")
            if result.sanitized:
                issue_texts.append(f"Content (sanitized): {result.sanitized}")
            if result.redacted_count > 0:
                issue_texts.append(
                    f"[PII: {result.redacted_count} items redacted: {', '.join(result.pii_types)}]"
                )
            issue_texts.append("")

        issues_text = "\n".join(issue_texts)

        prompt = _PROMPT_TEMPLATE.format(
            system_prompt=self._system_prompt,
            days=self._days,
            issues_text=issues_text,
        )

        logger.info("Built prompt with %d issues, total length: %d chars", len(issues), len(prompt))
        return prompt

    @property
    def system_prompt(self) -> str:
        """Return the system prompt (for testing / inspection)."""
        return self._system_prompt
