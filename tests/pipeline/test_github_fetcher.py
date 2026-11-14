"""Unit tests for GitHub Fetcher (TC-001, TC-002).

Tests:
  TC-001: Successful data collection (mock 5 Issues, verify fields)
  TC-002: Auth error (mock 401 -> AuthError)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
import respx

from ai_tpm_copilot.config.settings import Settings
from ai_tpm_copilot.pipeline.github_fetcher import AuthError, GitHubFetcher


# ─── Fixtures ─────────────────────────────────────────────────────


def _make_settings(**overrides: Any) -> Settings:
    """Build a minimal Settings object for testing.

    Top-level kwargs override Settings fields; 'github' is merged into
    the GitHubConfig sub-model.
    """
    github = {
        "token": "ghp_test_token_for_testing",
        "repos": ["test-owner/test-repo"],
        "since_days": 7,
        "per_page": 100,
        "max_retries": 3,
    }
    github.update(overrides.pop("github", {}))

    return Settings(
        github=github,
        yandexgpt={
            "folder_id": "test-folder",
            "iam_token": "test-iam-token",
        },
        pii={"enabled": False},
        otel={"enabled": False},
        **overrides,
    )


def _json_response(data: Any, status_code: int = 200, headers: dict | None = None) -> httpx.Response:
    """Create an httpx.Response with JSON content."""
    return httpx.Response(status_code, json=data, headers=headers or {})


def _mock_issue(number: int, title: str | None = None, state: str = "closed",
                created_offset_days: int = 2) -> dict[str, Any]:
    """Create a minimal GitHub API issue dict."""
    if title is None:
        title = f"Issue #{number}"
    created = datetime.now(timezone.utc) - timedelta(days=created_offset_days)
    updated = created + timedelta(hours=1)
    return {
        "id": 1000 + number,
        "number": number,
        "title": title,
        "body": f"Description for issue {number}",
        "state": state,
        "assignees": [{"login": f"user{number}"}],
        "labels": [{"name": f"label{number}"}],
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
    }


def _mock_comment(issue_number: int, body: str = "Nice work!") -> dict[str, Any]:
    """Create a minimal GitHub API comment dict."""
    return {
        "id": 5000 + issue_number,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user": {"login": "commenter"},
    }


# ─── TC-001: Successful data collection ──────────────────────────


@respx.mock
def test_tc001_successful_fetch_five_issues():
    """TC-001: Mock 5 Issues, verify all fields populated correctly."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    issues = [_mock_issue(n) for n in (10, 20, 30, 40, 50)]

    # First page: 3 issues (with Link header for pagination)
    respx.get(
        url="https://api.github.com/repos/test-owner/test-repo/issues",
        params={"state": "all", "sort": "updated", "direction": "desc", "page": "1", "per_page": "100"},
    ).mock(
        return_value=_json_response(
            issues[:3],
            headers={"Link": '</repos/test-owner/test-repo/issues?page=2>; rel="next"'},
        )
    )
    # Second page: 2 issues (no next link)
    respx.get(
        url="https://api.github.com/repos/test-owner/test-repo/issues",
        params={"state": "all", "sort": "updated", "direction": "desc", "page": "2", "per_page": "100"},
    ).mock(return_value=_json_response(issues[3:]))

    # Mock comments for each issue — use exact URL
    for issue in issues:
        respx.get(
            url=f"https://api.github.com/repos/test-owner/test-repo/issues/{issue['number']}/comments"
        ).mock(return_value=_json_response([_mock_comment(issue["number"])]))

    result = fetcher.fetch(since_days=7)

    assert len(result) == 5
    for issue in result:
        assert issue.number in {10, 20, 30, 40, 50}
        assert issue.title.startswith("Issue #")
        assert issue.state == "closed"
        assert len(issue.assignees) == 1
        assert len(issue.labels) == 1
        assert len(issue.comments) == 1
        assert issue.comments[0].body == "Nice work!"
        assert issue.body == f"Description for issue {issue.number}"


@respx.mock
def test_tc001_single_page_fetch():
    """TC-001 variant: all issues fit on one page (no 'next' link)."""
    settings = _make_settings(github={"per_page": 100})
    fetcher = GitHubFetcher(settings)

    issues = [_mock_issue(n, created_offset_days=1) for n in (1, 2, 3)]

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=_json_response(issues))

    result = fetcher.fetch(since_days=7)

    assert len(result) == 3
    numbers = {i.number for i in result}
    assert numbers == {1, 2, 3}


@respx.mock
def test_tc001_date_filtering():
    """TC-001 variant: issues older than since_days are excluded."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    # Mix of recent and old issues
    issues = [
        _mock_issue(1, created_offset_days=1),   # recent — include
        _mock_issue(2, created_offset_days=3),   # recent — include
        _mock_issue(3, created_offset_days=14),  # old — exclude
    ]

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=_json_response(issues))

    for issue in issues:
        respx.get(
            url=f"https://api.github.com/repos/test-owner/test-repo/issues/{issue['number']}/comments"
        ).mock(return_value=_json_response([]))

    result = fetcher.fetch(since_days=7)

    assert len(result) == 2
    numbers = {i.number for i in result}
    assert numbers == {1, 2}
    assert 3 not in numbers


@respx.mock
def test_tc001_multiple_repos():
    """TC-001 variant: fetch from multiple configured repositories."""
    settings = _make_settings(github={"repos": ["owner/repo-alpha", "owner/repo-beta"]})
    fetcher = GitHubFetcher(settings)

    for repo, label in [("owner/repo-alpha", "alpha"), ("owner/repo-beta", "beta")]:
        issues = [_mock_issue(1, title=f"{label} issue")]
        respx.get(
            url=f"https://api.github.com/repos/{repo}/issues"
        ).mock(return_value=_json_response(issues))
        respx.get(
            url=f"https://api.github.com/repos/{repo}/issues/1/comments"
        ).mock(return_value=_json_response([]))

    result = fetcher.fetch(since_days=7)

    assert len(result) == 2
    titles = {i.title for i in result}
    assert titles == {"alpha issue", "beta issue"}


# ─── TC-002: Auth error ──────────────────────────────────────────


@respx.mock
def test_tc002_auth_error_on_401():
    """TC-002: 401 response raises AuthError."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(
        return_value=_json_response(
            {"message": "Bad credentials"},
            status_code=401,
        )
    )

    with pytest.raises(AuthError, match="auth failed"):
        fetcher.fetch(since_days=7)


@respx.mock
def test_tc002_auth_error_preserves_message():
    """TC-002: AuthError contains the API error message."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(
        return_value=_json_response(
            {"message": "Token expired, please regenerate"},
            status_code=401,
        )
    )

    with pytest.raises(AuthError) as exc_info:
        fetcher.fetch(since_days=7)

    assert "Token expired" in str(exc_info.value)


# ─── Additional edge-case tests ──────────────────────────────────


@respx.mock
def test_fetch_empty_response():
    """Edge case: API returns empty list — should return empty results, not error."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    respx.get(
        url__startswith="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=_json_response([]))

    result = fetcher.fetch(since_days=7)

    assert result == []


@respx.mock
def test_fetch_comments_on_error():
    """Edge case: comments endpoint fails — log warning, continue with empty comments."""
    settings = _make_settings()
    fetcher = GitHubFetcher(settings)

    issue = [_mock_issue(42)]

    respx.get(
        url="https://api.github.com/repos/test-owner/test-repo/issues"
    ).mock(return_value=_json_response(issue))

    # Comments endpoint returns 500
    respx.get(
        url="https://api.github.com/repos/test-owner/test-repo/issues/42/comments"
    ).mock(return_value=_json_response({"message": "Internal Error"}, status_code=500))

    result = fetcher.fetch(since_days=7)

    assert len(result) == 1
    assert result[0].number == 42
    assert result[0].comments == []  # comments should be empty, not raise
