"""GitHub data importer.

Exports repositories, issues, pull requests, discussions, releases, and optionally stars.
Uses the public GitHub REST API via the standard library; no external deps.
Requires ``owner_repo`` like "octocat/Hello-World".
Authentication token can be supplied via ``GITHUB_TOKEN`` env var for higher rate limits.
"""

import json
import logging
import os
import urllib.request
from typing import Callable, List, Dict, Any

from app.import.manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _github_api(path: str) -> Any:
    """Fetch JSON from GitHub API, handling optional token.
    ponytail: simple urllib, no pagination beyond first page.
    """
    base = "https://api.github.com"
    url = f"{base}{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def _load_repository(owner_repo: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    # Repo metadata
    repo_data = _github_api(f"/repos/{owner_repo}")
    repo_rec = {
        "type": "repository",
        "external_id": f"repo:{owner_repo}",
        "full_name": repo_data.get("full_name"),
        "description": repo_data.get("description"),
        "html_url": repo_data.get("html_url"),
        "created_at": repo_data.get("created_at"),
        "updated_at": repo_data.get("updated_at"),
        "pushed_at": repo_data.get("pushed_at"),
        "stargazers_count": repo_data.get("stargazers_count"),
        "forks_count": repo_data.get("forks_count"),
    }
    records.append(repo_rec)
    # Issues (includes PRs but we filter later)
    issues = _github_api(f"/repos/{owner_repo}/issues?state=all&per_page=100")
    for issue in issues:
        if "pull_request" in issue:
            continue  # skip PRs here
        rec = {
            "type": "issue",
            "external_id": f"issue:{owner_repo}:{issue.get('number')}",
            "number": issue.get("number"),
            "title": issue.get("title"),
            "user": issue.get("user", {}).get("login"),
            "state": issue.get("state"),
            "created_at": issue.get("created_at"),
            "closed_at": issue.get("closed_at"),
            "body": issue.get("body"),
        }
        records.append(rec)
    # Pull requests
    prs = _github_api(f"/repos/{owner_repo}/pulls?state=all&per_page=100")
    for pr in prs:
        rec = {
            "type": "pull_request",
            "external_id": f"pr:{owner_repo}:{pr.get('number')}",
            "number": pr.get("number"),
            "title": pr.get("title"),
            "user": pr.get("user", {}).get("login"),
            "state": pr.get("state"),
            "created_at": pr.get("created_at"),
            "merged_at": pr.get("merged_at"),
            "body": pr.get("body"),
        }
        records.append(rec)
    # Releases
    releases = _github_api(f"/repos/{owner_repo}/releases?per_page=100")
    for rel in releases:
        rec = {
            "type": "release",
            "external_id": f"release:{owner_repo}:{rel.get('id')}",
            "tag_name": rel.get("tag_name"),
            "name": rel.get("name"),
            "created_at": rel.get("created_at"),
            "published_at": rel.get("published_at"),
            "body": rel.get("body"),
        }
        records.append(rec)
    # Discussions (GitHub API may require preview header; skip if unavailable)
    try:
        discussions = _github_api(f"/repos/{owner_repo}/discussions?per_page=100")
        for d in discussions:
            rec = {
                "type": "discussion",
                "external_id": f"discussion:{owner_repo}:{d.get('id')}",
                "title": d.get("title"),
                "author": d.get("author", {}).get("login"),
                "created_at": d.get("created_at"),
                "body": d.get("body"),
            }
            records.append(rec)
    except Exception:
        logger.info("Discussions API not available or failed for %s", owner_repo)
    return records


async def import_github(owner_repo: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Import GitHub data for *owner_repo*.
    Returns number of newly created events.
    """
    records = _load_repository(owner_repo)
    if not records:
        return 0
    if progress_callback:
        progress_callback(len(records))
    created = await import_records("github_import", records)
    logger.info("Imported %d new GitHub observations for %s", created, owner_repo)
    return created

# Register – identity handler
register_importer("github_import", "1.0", lambda rec: rec)  # ponytail: identity