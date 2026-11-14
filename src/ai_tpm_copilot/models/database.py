"""SQLAlchemy models for the reports database."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class Report(Base):
    """Represents a generated status report stored in the database.

    Columns:
        report_id: Unique identifier (UUID string).
        repo: GitHub repository name (owner/repo).
        generated_at: UTC timestamp when the report was generated.
        token_usage: Number of LLM tokens consumed.
        pii_redacted_count: Number of PII items redacted.
        markdown: The full Markdown report content.
        status: Generation status (pending, completed, failed).
        error: Error message if status == "failed".
    """

    __tablename__ = "reports"

    report_id = Column(String(36), primary_key=True, index=True)
    repo = Column(String(255), nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    token_usage = Column(Integer, nullable=False, default=0)
    pii_redacted_count = Column(Integer, nullable=False, default=0)
    markdown = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | completed | failed
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_reports_generated_at", "generated_at"),
    )

    def __repr__(self) -> str:
        return f"<Report(report_id={self.report_id!r}, status={self.status!r})>"
