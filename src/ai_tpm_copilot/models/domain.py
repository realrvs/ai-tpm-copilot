"""Data models for the TPM Copilot pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GitHubIssue:
    """Represents a single GitHub Issue with its metadata."""

    id: int
    number: int
    title: str
    body: str | None = None
    state: str = "open"  # open | closed
    assignees: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    comments: list[IssueComment] = field(default_factory=list)

    @property
    def text_content(self) -> str:
        """Return combined text for PII redaction."""
        parts = [f"#{self.number} {self.title}"]
        if self.body:
            parts.append(self.body)
        for c in self.comments:
            parts.append(c.body)
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class IssueComment:
    """Represents a comment on a GitHub Issue."""

    id: int
    body: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    author: str = ""


@dataclass
class RedactionResult:
    """Result of PII redaction."""

    original: str
    sanitized: str
    redacted_count: int = 0
    pii_types: list[str] = field(default_factory=list)


@dataclass
class LLMReport:
    """Structured LLM-generated report."""

    completed: list[ReportItem] = field(default_factory=list)
    in_progress: list[ReportItem] = field(default_factory=list)
    blocked: list[ReportItem] = field(default_factory=list)
    risks: list[ReportItem] = field(default_factory=list)
    unverified_items: list[ReportItem] = field(default_factory=list)
    token_usage: int = 0


@dataclass(frozen=True, slots=True)
class ReportItem:
    """Single item within a report section."""

    issue_id: int
    title: str
    reason: str = ""


@dataclass
class PipelineMetrics:
    """Metrics collected during pipeline execution."""

    issues_fetched: int = 0
    pii_redacted_count: int = 0
    llm_tokens_used: int = 0
    pipeline_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
