"""FastAPI wrapper for AI TPM Copilot.

Endpoints:
  POST /api/v1/reports — generate a status report
  GET  /api/v1/reports/{report_id} — retrieve a report by ID
  GET  /health — health check (no auth)
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.observability import OTelInstrumentation
from ai_tpm_copilot.pipeline.orchestrator import Pipeline
from ai_tpm_copilot.pipeline.output import FileWriter

logger = logging.getLogger("ai_tpm_copilot.api")

# ─── Pydantic models ──────────────────────────────────────────────


class ReportRequest(BaseModel):
    """Request body for report generation."""

    days: int = Field(default=7, ge=1, le=90, description="Days of history to analyze")
    repos: list[str] | None = Field(
        default=None,
        description="Override GitHub repos (list of owner/repo)",
    )


class ReportResponse(BaseModel):
    """Response from report generation."""

    report_id: str
    status: str  # pending, completed, failed
    markdown: str | None = None
    error: str | None = None
    generated_at: str
    issues_count: int = 0
    duration_ms: float = 0.0


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime_seconds: float
    timestamp: str


class ReportDetailResponse(BaseModel):
    """Detailed report retrieval response."""

    report_id: str
    status: str
    markdown: str | None = None
    error: str | None = None
    generated_at: str
    repo: str | None = None
    issues_count: int = 0


# ─── Global state ─────────────────────────────────────────────────

# In-memory report store (for MVP; replace with DB in production)
_reports: dict[str, dict[str, Any]] = {}

# Application settings (loaded once at startup)
_app_settings: Settings | None = None

# Start time for uptime calculation
_start_time = time.monotonic()

# ─── FastAPI app ──────────────────────────────────────────────────

app = FastAPI(
    title="AI TPM Copilot",
    description="Automated status reporting from GitHub Issues with LLM analysis",
    version="0.1.0a0",
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize settings and OTel on startup."""
    global _app_settings
    try:
        _app_settings = Settings.load()
        otel = OTelInstrumentation(_app_settings)
        otel.setup()
        logger.info("FastAPI started with settings loaded")
    except Exception as exc:
        logger.error("Failed to load settings at startup: %s", exc)
        _app_settings = None


# ─── GET /health ──────────────────────────────────────────────────


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["system"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint — no authentication required."""
    uptime = time.monotonic() - _start_time
    return HealthResponse(
        status="healthy",
        version="0.1.0a0",
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.now(UTC).isoformat(),
    )


# ─── POST /api/v1/reports ─────────────────────────────────────────


@app.post(
    "/api/v1/reports",
    response_model=ReportResponse,
    summary="Generate a status report",
    tags=["reports"],
)
async def generate_report(request: ReportRequest) -> ReportResponse:
    """Generate a status report from GitHub Issues.

    This endpoint runs the full pipeline:
    GitHub Fetcher → PII Redactor → Prompt Builder → LLM Client →
    Report Validator → Report Generator → File Writer
    """
    global _app_settings

    if _app_settings is None:
        raise HTTPException(status_code=503, detail="Settings not initialized")

    report_id = str(uuid.uuid4())
    start = time.monotonic()

    # Store pending report
    _reports[report_id] = {
        "report_id": report_id,
        "status": "pending",
        "markdown": None,
        "error": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "repo": request.repos[0] if request.repos else None,
        "issues_count": 0,
    }

    try:
        # Override settings if repos provided
        settings = _app_settings
        if request.repos:
            from pydantic import BaseModel

            class OverrideSettings(BaseModel):
                github: dict[str, Any]

            OverrideSettings(github={"repos": request.repos})
            settings = Settings(
                github={
                    "token": _app_settings.github.token.get_secret_value(),
                    "repos": request.repos,
                },
                yandexgpt={
                    "folder_id": _app_settings.yandexgpt.folder_id,
                    "iam_token": _app_settings.yandexgpt.iam_token.get_secret_value(),
                },
                pii={"enabled": False},
                otel={"enabled": False},
            )

        # Run pipeline
        pipeline = Pipeline(settings)
        markdown = pipeline.run(since_days=request.days)

        # Save to file
        fw = FileWriter(settings.report.output_dir)
        fw.write(markdown)

        # Count issues (approximate from markdown)
        issues_count = markdown.count("#") - markdown.count("##")

        _reports[report_id].update(
            {
                "status": "completed",
                "markdown": markdown,
                "issues_count": issues_count,
            }
        )

    except Exception as exc:
        logger.error("Report generation failed: %s", exc, exc_info=True)
        _reports[report_id].update(
            {
                "status": "failed",
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=500, detail=str(exc))

    duration_ms = (time.monotonic() - start) * 1000
    _reports[report_id]["duration_ms"] = duration_ms

    return ReportResponse(
        report_id=report_id,
        status="completed",
        markdown=_reports[report_id].get("markdown"),
        error=_reports[report_id].get("error"),
        generated_at=_reports[report_id]["generated_at"],
        issues_count=_reports[report_id].get("issues_count", 0),
        duration_ms=duration_ms,
    )


# ─── GET /api/v1/reports/{report_id} ──────────────────────────────


@app.get(
    "/api/v1/reports/{report_id}",
    response_model=ReportDetailResponse,
    summary="Retrieve a report by ID",
    tags=["reports"],
)
async def get_report(report_id: str) -> ReportDetailResponse:
    """Retrieve a previously generated report by its ID."""
    if report_id not in _reports:
        raise HTTPException(
            status_code=404,
            detail=f"Report {report_id} not found",
        )

    report = _reports[report_id]
    return ReportDetailResponse(
        report_id=report["report_id"],
        status=report["status"],
        markdown=report.get("markdown"),
        error=report.get("error"),
        generated_at=report["generated_at"],
        repo=report.get("repo"),
        issues_count=report.get("issues_count", 0),
    )


# ─── CLI entry point ──────────────────────────────────────────────


def main() -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "ai_tpm_copilot.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
