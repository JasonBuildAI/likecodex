"""GitHub integration tools using REST API."""

from __future__ import annotations

import json
import os
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


_GITHUB_API = "https://api.github.com"


def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable not set")
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "LikeCodex/0.1",
    }


def _parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("repo must be in owner/repo format")
    return parts[0], parts[1]


class GitHubTools:
    """Tools for interacting with GitHub repositories."""

    @staticmethod
    def create_pr_schema() -> dict[str, Any]:
        return {
            "description": "Create a pull request on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository in owner/repo format",
                    },
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "PR description"},
                    "head": {"type": "string", "description": "Head branch"},
                    "base": {"type": "string", "default": "main", "description": "Base branch"},
                },
                "required": ["repo", "title", "head"],
            },
        }

    @staticmethod
    def review_pr_schema() -> dict[str, Any]:
        return {
            "description": "Review a pull request (approve / comment / request changes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "pr_number": {"type": "integer"},
                    "body": {"type": "string", "description": "Review body"},
                    "event": {
                        "type": "string",
                        "enum": ["APPROVE", "COMMENT", "REQUEST_CHANGES"],
                        "default": "COMMENT",
                    },
                },
                "required": ["repo", "pr_number", "body"],
            },
        }

    @staticmethod
    def add_pr_comment_schema() -> dict[str, Any]:
        return {
            "description": "Add a comment to a pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "pr_number": {"type": "integer"},
                    "body": {"type": "string", "description": "Comment text"},
                },
                "required": ["repo", "pr_number", "body"],
            },
        }

    @staticmethod
    def create_issue_schema() -> dict[str, Any]:
        return {
            "description": "Create an issue on a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "Issue description"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Issue labels",
                    },
                },
                "required": ["repo", "title"],
            },
        }

    @staticmethod
    def list_prs_schema() -> dict[str, Any]:
        return {
            "description": "List pull requests for a repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["repo"],
            },
        }

    @staticmethod
    def list_issues_schema() -> dict[str, Any]:
        return {
            "description": "List issues for a repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["repo"],
            },
        }

    async def create_pr(
        self,
        repo: str,
        title: str,
        head: str,
        body: str = "",
        base: str = "main",
    ) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required. Install with: pip install httpx"})
        try:
            owner, name = _parse_repo(repo)
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GITHUB_API}/repos/{owner}/{name}/pulls",
                    headers=_headers(),
                    json={"title": title, "body": body, "head": head, "base": base},
                    timeout=30,
                )
                return json.dumps(resp.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def review_pr(
        self,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
    ) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            owner, name = _parse_repo(repo)
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GITHUB_API}/repos/{owner}/{name}/pulls/{pr_number}/reviews",
                    headers=_headers(),
                    json={"body": body, "event": event},
                    timeout=30,
                )
                return json.dumps(resp.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def add_pr_comment(self, repo: str, pr_number: int, body: str) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            owner, name = _parse_repo(repo)
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GITHUB_API}/repos/{owner}/{name}/issues/{pr_number}/comments",
                    headers=_headers(),
                    json={"body": body},
                    timeout=30,
                )
                return json.dumps(resp.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            owner, name = _parse_repo(repo)
            payload: dict[str, Any] = {"title": title, "body": body}
            if labels:
                payload["labels"] = labels
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_GITHUB_API}/repos/{owner}/{name}/issues",
                    headers=_headers(),
                    json=payload,
                    timeout=30,
                )
                return json.dumps(resp.json())
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_prs(self, repo: str, state: str = "open", limit: int = 10) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            owner, name = _parse_repo(repo)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GITHUB_API}/repos/{owner}/{name}/pulls",
                    headers=_headers(),
                    params={"state": state, "per_page": limit},
                    timeout=30,
                )
                items = resp.json()
                result = [
                    {
                        "number": it["number"],
                        "title": it["title"],
                        "state": it["state"],
                        "user": it["user"]["login"],
                        "created_at": it["created_at"],
                        "html_url": it["html_url"],
                    }
                    for it in (items if isinstance(items, list) else [])
                ]
                return json.dumps({"prs": result, "count": len(result)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_issues(self, repo: str, state: str = "open", limit: int = 10) -> str:
        if not HAS_HTTPX:
            return json.dumps({"error": "httpx is required"})
        try:
            owner, name = _parse_repo(repo)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_GITHUB_API}/repos/{owner}/{name}/issues",
                    headers=_headers(),
                    params={"state": state, "per_page": limit},
                    timeout=30,
                )
                items = resp.json()
                result = [
                    {
                        "number": it["number"],
                        "title": it["title"],
                        "state": it["state"],
                        "user": it["user"]["login"],
                        "created_at": it["created_at"],
                        "html_url": it["html_url"],
                    }
                    for it in (items if isinstance(items, list) else [])
                ]
                return json.dumps({"issues": result, "count": len(result)})
        except Exception as e:
            return json.dumps({"error": str(e)})
