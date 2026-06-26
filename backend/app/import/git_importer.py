"""Git repository importer.

Exports each commit as a record containing:
- external_id (commit hash)
- repository (absolute path)
- commit_hash
- author_name / author_email
- timestamp (Unix epoch seconds)
- message
- changed_files (list of paths relative to repo)
- branch (current branch name) – simplified, not exhaustive.

Uses the system ``git`` command; no extra dependencies.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, List, Dict, Any

from .manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _run_git(args: List[str], cwd: str) -> str:
    """Run a git command in *cwd* and return stdout.
    ponytail: minimal wrapper, raises on error.
    """
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _collect_commits(repo_path: str) -> List[Dict[str, Any]]:
    """Return a list of commit records ordered chronologically (oldest first)."""
    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        logger.error("Not a git repository: %s", repo_path)
        return []
    # Get current branch name (fallback "unknown")
    try:
        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], str(repo))
    except Exception:
        branch = "unknown"
    # Git log with raw format for easy parsing
    log_output = _run_git([
        "log",
        "--reverse",  # chronological
        "--pretty=format:%H|%an|%ae|%ad|%s",
        "--name-only",
    ], str(repo))
    records: List[Dict[str, Any]] = []
    # Split into blocks separated by blank line
    blocks = log_output.split("\n\n") if log_output else []
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        header = lines[0]
        parts = header.split("|", 4)
        if len(parts) != 5:
            continue
        commit_hash, author_name, author_email, date_str, subject = parts
        # Convert date to epoch seconds using git's %ad (default format) via date -d
        try:
            ts_str = _run_git(["show", "-s", "--format=%ct", commit_hash], str(repo))
            timestamp = int(ts_str)
        except Exception:
            timestamp = 0
        changed = [p for p in lines[1:] if p]
        record: Dict[str, Any] = {
            "external_id": commit_hash,
            "repository": str(repo),
            "commit_hash": commit_hash,
            "author_name": author_name,
            "author_email": author_email,
            "timestamp": timestamp,
            "message": subject,
            "changed_files": changed,
            "branch": branch,
        }
        records.append(record)
    return records


async def import_git(repo_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Import all commits from *repo_path*.
    Returns number of newly created events.
    """
    records = _collect_commits(repo_path)
    if not records:
        return 0
    if progress_callback:
        progress_callback(len(records))
    created = await import_records("git_import", records)
    logger.info("Imported %d new git observations from %s", created, repo_path)
    return created

# Register – identity handler (payload already prepared)
register_importer("git_import", "1.0", lambda rec: rec)  # ponytail: identity
