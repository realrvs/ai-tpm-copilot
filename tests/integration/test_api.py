"""Integration tests for FastAPI endpoints (T-022, T-023, T-024).

Tests:
  TC-API-001: POST /api/v1/reports generates a report
  TC-API-002: GET /api/v1/reports/{id} retrieves the report
  TC-API-003: GET /health returns healthy status
  TC-API-004: GET /api/v1/reports/{invalid_id} returns 404
  TC-API-005: POST /api/v1/reports with custom days
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from ai_tpm_copilot.api import _reports, app

# ─── Test client fixture ──────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_reports():
    """Clear in-memory report store before each test."""
    _reports.clear()
    yield
    _reports.clear()


@pytest.fixture
def client():
    """Create a test client."""
    from fastapi.testclient import TestClient

    return TestClient(app)


# ─── TC-API-003: Health check ─────────────────────────────────────


def test_tc_api_003_health_check(client):
    """TC-API-003: GET /health returns healthy status without auth."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0a0"
    assert "uptime_seconds" in data
    assert "timestamp" in data


# ─── TC-API-001: POST /api/v1/reports ────────────────────────────


@respx.mock
def test_tc_api_001_post_report(client):
    """TC-API-001: POST /api/v1/reports generates a report successfully."""
    # Mock GitHub API
    issues = [
        {
            "id": 1000,
            "number": 10,
            "title": "Test issue",
            "body": "Test body",
            "state": "closed",
            "assignees": [],
            "labels": [],
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ]
    respx.get(url__startswith="https://api.github.com/repos/test/test/issues").mock(
        return_value=httpx.Response(200, json=issues)
    )
    respx.get(url="https://api.github.com/repos/test/test/issues/10/comments").mock(
        return_value=httpx.Response(200, json=[])
    )

    # Mock YandexGPT
    llm_response = {
        "completion": {
            "candidates": [
                {
                    "text": """\
## Выполнено
- #10 **Test issue** — _closed_
""",
                }
            ],
        },
    }
    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    # Mock Settings.load to avoid ENV requirements
    mock_settings = MagicMock()
    mock_settings.github.token.get_secret_value.return_value = "ghp_test"
    mock_settings.github.repos = ["test/test"]
    mock_settings.github.since_days = 7
    mock_settings.yandexgpt.folder_id = "f"
    mock_settings.yandexgpt.iam_token.get_secret_value.return_value = "t"
    mock_settings.pii.enabled = False
    mock_settings.otel.enabled = False
    mock_settings.report.output_dir = Path("/tmp/test_reports")
    mock_settings.report.fact_check_strict = True
    mock_settings.report.fuzzy_matching = True
    mock_settings.enable_fact_check_strict = True
    mock_settings.enable_fuzzy_matching = True
    mock_settings.enable_telegram_delivery = False

    with patch("ai_tpm_copilot.api.Settings.load", return_value=mock_settings):
        # Manually set the global settings to avoid 503
        import ai_tpm_copilot.api as api_module

        api_module._app_settings = mock_settings

        response = client.post(
            "/api/v1/reports",
            json={"days": 7, "repos": ["test/test"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["report_id"] is not None
    assert data["markdown"] is not None
    assert "## Выполнено" in data["markdown"]
    assert "#10" in data["markdown"]
    assert "duration_ms" in data


# ─── TC-API-002: GET /api/v1/reports/{id} ────────────────────────


@respx.mock
def test_tc_api_002_get_report(client):
    """TC-API-002: GET /api/v1/reports/{id} retrieves the report."""
    # First generate a report
    issues = [
        {
            "id": 1000,
            "number": 10,
            "title": "Test issue",
            "body": "Test body",
            "state": "closed",
            "assignees": [],
            "labels": [],
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ]
    respx.get(url__startswith="https://api.github.com/repos/test/test/issues").mock(
        return_value=httpx.Response(200, json=issues)
    )
    respx.get(url="https://api.github.com/repos/test/test/issues/10/comments").mock(
        return_value=httpx.Response(200, json=[])
    )

    llm_response = {
        "completion": {
            "candidates": [
                {
                    "text": "## Выполнено\n- #10 **Test issue**",
                }
            ],
        },
    }
    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    mock_settings = MagicMock()
    mock_settings.github.token.get_secret_value.return_value = "ghp_test"
    mock_settings.github.repos = ["test/test"]
    mock_settings.github.since_days = 7
    mock_settings.yandexgpt.folder_id = "f"
    mock_settings.yandexgpt.iam_token.get_secret_value.return_value = "t"
    mock_settings.pii.enabled = False
    mock_settings.otel.enabled = False
    mock_settings.report.output_dir = Path("/tmp/test_reports")
    mock_settings.report.fact_check_strict = True
    mock_settings.report.fuzzy_matching = True
    mock_settings.enable_fact_check_strict = True
    mock_settings.enable_fuzzy_matching = True
    mock_settings.enable_telegram_delivery = False

    with patch("ai_tpm_copilot.api.Settings.load", return_value=mock_settings):
        import ai_tpm_copilot.api as api_module

        api_module._app_settings = mock_settings

        gen_response = client.post(
            "/api/v1/reports",
            json={"days": 7, "repos": ["test/test"]},
        )

    assert gen_response.status_code == 200
    report_id = gen_response.json()["report_id"]

    # Now retrieve the report
    get_response = client.get(f"/api/v1/reports/{report_id}")

    assert get_response.status_code == 200
    data = get_response.json()
    assert data["report_id"] == report_id
    assert data["status"] == "completed"
    assert data["markdown"] is not None


# ─── TC-API-004: 404 for invalid report ──────────────────────────


def test_tc_api_004_get_report_not_found(client):
    """TC-API-004: GET /api/v1/reports/{invalid_id} returns 404."""
    response = client.get("/api/v1/reports/non-existent-id")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


# ─── TC-API-005: Custom days ─────────────────────────────────────


@respx.mock
def test_tc_api_005_custom_days(client):
    """TC-API-005: POST /api/v1/reports with custom days parameter."""
    issues = [
        {
            "id": 1000,
            "number": 20,
            "title": "Custom days issue",
            "body": "Test",
            "state": "closed",
            "assignees": [],
            "labels": [],
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ]
    respx.get(url__startswith="https://api.github.com/repos/test/test/issues").mock(
        return_value=httpx.Response(200, json=issues)
    )
    respx.get(url="https://api.github.com/repos/test/test/issues/20/comments").mock(
        return_value=httpx.Response(200, json=[])
    )

    llm_response = {
        "completion": {
            "candidates": [
                {
                    "text": "## Выполнено\n- #20 **Custom days issue**",
                }
            ],
        },
    }
    respx.post("https://llm.api.cloud.yandex.net/generativeLlm/completions").mock(
        return_value=httpx.Response(200, json=llm_response)
    )

    mock_settings = MagicMock()
    mock_settings.github.token.get_secret_value.return_value = "ghp_test"
    mock_settings.github.repos = ["test/test"]
    mock_settings.github.since_days = 7
    mock_settings.yandexgpt.folder_id = "f"
    mock_settings.yandexgpt.iam_token.get_secret_value.return_value = "t"
    mock_settings.pii.enabled = False
    mock_settings.otel.enabled = False
    mock_settings.report.output_dir = Path("/tmp/test_reports")
    mock_settings.report.fact_check_strict = True
    mock_settings.report.fuzzy_matching = True
    mock_settings.enable_fact_check_strict = True
    mock_settings.enable_fuzzy_matching = True
    mock_settings.enable_telegram_delivery = False

    with patch("ai_tpm_copilot.api.Settings.load", return_value=mock_settings):
        import ai_tpm_copilot.api as api_module

        api_module._app_settings = mock_settings

        response = client.post(
            "/api/v1/reports",
            json={"days": 30, "repos": ["test/test"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "#20" in data["markdown"]
