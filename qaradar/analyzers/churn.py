"""Git churn analysis — find files that change frequently."""

from __future__ import annotations

import fnmatch
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qaradar.git import _git
from qaradar.models import FileChurn


def analyze_churn(
    repo_path: str,
    days: int = 90,
    extensions: tuple[str, ...] = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".swift", ".rb", ".go", ".rs"),
    excludes: list[str] | None = None,
) -> list[FileChurn]:
    """Analyze git history for file churn over the given period.

    Returns files sorted by commit count (descending).
    """
    if shutil.which("git") is None:
        raise RuntimeError("git not found in PATH — install git and retry")

    repo = Path(repo_path).resolve()
    if not (repo / ".git").exists():
        raise ValueError(f"Not a git repository: {repo}")

    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    # Get per-file commit counts and stats
    # Using --numstat for lines added/deleted, --format for commit metadata
    log_output = _git(
        repo,
        "log",
        f"--since={since_date}",
        "--pretty=format:COMMIT|%H|%aI|%aN",
        "--numstat",
    )

    if not (log_output or "").strip():
        return []

    file_stats: dict[str, dict] = defaultdict(
        lambda: {
            "commits": set(),
            "authors": set(),
            "lines_added": 0,
            "lines_deleted": 0,
            "last_date": "",
            "recent_commits": set(),
        }
    )

    current_commit = None
    current_date = ""
    current_author = ""

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("COMMIT|"):
            parts = line.split("|", 3)
            current_commit = parts[1]
            current_date = parts[2]
            current_author = parts[3]
            continue

        if current_commit is None:
            continue

        # numstat line: added<TAB>deleted<TAB>filepath
        parts = line.split("\t")
        if len(parts) != 3:
            continue

        added_str, deleted_str, filepath = parts

        # Skip binary files (shown as -)
        if added_str == "-" or deleted_str == "-":
            continue

        # Filter by extension
        if not any(filepath.endswith(ext) for ext in extensions):
            continue

        stats = file_stats[filepath]
        stats["commits"].add(current_commit)
        stats["authors"].add(current_author)
        stats["lines_added"] += int(added_str)
        stats["lines_deleted"] += int(deleted_str)

        if not stats["last_date"] or current_date > stats["last_date"]:
            stats["last_date"] = current_date

        # Track recent commits (last 30 days)
        if current_date >= thirty_days_ago:
            stats["recent_commits"].add(current_commit)

    results = []
    for filepath, stats in file_stats.items():
        # Only include files that still exist
        if not (repo / filepath).exists():
            continue

        # Apply excludes
        if excludes and any(fnmatch.fnmatch(filepath, pattern) for pattern in excludes):
            continue

        results.append(
            FileChurn(
                path=filepath,
                commit_count=len(stats["commits"]),
                lines_added=stats["lines_added"],
                lines_deleted=stats["lines_deleted"],
                unique_authors=len(stats["authors"]),
                last_modified=stats["last_date"][:10] if stats["last_date"] else "",
                recent_commit_count=len(stats["recent_commits"]),
            )
        )

    results.sort(key=lambda f: f.commit_count, reverse=True)
    return results
