"""GitHub data fetcher — collects Issues and PRs from GitHub API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ai_tpm_copilot.models.domain import GitHubIssue, IssueComment

if TYPE_CHECKING:
    from ai_tpm_copilot.config.settings import Settings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"
ISSUES_PATH = "/repos/{owner}/{repo}/issues"
COMMENT_PATH = "/repos/{owner}/{repo}/issues/{issue_number}/comments"


class GitHubFetchError(Exception):
    """Raised when GitHub API request fails."""


class AuthError(GitHubFetchError):
    """Raised on 401 — invalid or expired token."""


class GitHubFetcher:
    """Fetches Issues and their comments from GitHub REST API.

    Uses httpx for async HTTP with tenacity for retry logic.
    """

    def __init__(self, settings: Settings):
        self._base_url = GITHUB_API_BASE
        self._token = settings.github_token
        self._repos = settings.github.repos
        self._since_days = settings.github.since_days
        self._per_page = settings.github.per_page
        self._max_retries = settings.github.max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _get(self, path: str, params: dict | None = None) -> list[dict]:
        """Execute a paginated GET request to GitHub API."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        all_items: list[dict] = []
        page = 1
        while True:
            url = f"{self._base_url}{path}"
            params_page = {**(params or {}), "page": page, "per_page": self._per_page}
            logger.debug("GET %s params=%s", url, params_page)
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, headers=headers, params=params_page)
                if resp.status_code == 401:
                    raise AuthError(f"GitHub auth failed: {resp.text}")
                resp.raise_for_status()
                all_items.extend(resp.json())
                # Check for next page via Link header
                link_header = resp.headers.get("Link", "")
                if 'rel="next"' not in link_header:
                    break
                page += 1
        return all_items

    def fetch(self, since_days: int | None = None) -> list[GitHubIssue]:
        """Fetch all Issues for configured repos since N days ago.

        Args:
            since_days: Override default days of history.

        Returns:
            List of GitHubIssue objects with comments populated.
        """
        since_days = since_days or self._since_days
        since_dt = datetime.now(UTC) - timedelta(days=since_days)
        issues: list[GitHubIssue] = []

        for repo in self._repos:
            logger.info("Fetching issues for %s (since %s)", repo, since_dt.date())
            path = ISSUES_PATH.format(owner=repo.split("/")[0], repo=repo.split("/")[1])
            params = {"state": "all", "sort": "updated", "direction": "desc"}

            raw_issues = self._get(path, params)

            for raw in raw_issues:
                created = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))

                # Filter by date
                if created < since_dt:
                    continue

                # Fetch comments
                comments = self._fetch_comments(repo, raw["number"])

                issue = GitHubIssue(
                    id=raw["id"],
                    number=raw["number"],
                    title=raw["title"],
                    body=raw.get("body") or "",
                    state=raw["state"],
                    assignees=[a["login"] for a in raw.get("assignees", [])],
                    labels=[lb["name"] for lb in raw.get("labels", [])],
                    created_at=created,
                    updated_at=updated,
                    comments=comments,
                )
                issues.append(issue)

        logger.info("Fetched %d issues total", len(issues))
        return issues

    def _fetch_comments(self, repo: str, issue_number: int) -> list[IssueComment]:
        """Fetch comments for a single issue."""
        path = COMMENT_PATH.format(
            owner=repo.split("/")[0], repo=repo.split("/")[1], issue_number=issue_number
        )
        try:
            raw_comments = self._get(path)
        except (GitHubFetchError, httpx.HTTPStatusError) as exc:
            logger.warning("Failed to fetch comments for #%d: %s", issue_number, exc)
            return []

        comments = []
        for raw in raw_comments:
            created = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00"))
            comment = IssueComment(
                id=raw["id"],
                body=raw.get("body") or "",
                created_at=created,
                author=raw.get("user", {}).get("login", ""),
            )
            comments.append(comment)
        return comments
