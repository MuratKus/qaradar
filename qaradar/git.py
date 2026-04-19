"""Shared git utilities for QA Radar analyzers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` and return stdout. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {result.stderr.strip()}")
    return result.stdout


def resolve_base_ref(repo: Path, explicit: str | None) -> str:
    """Resolve the base ref to compare against.

    Resolution order:
    1. `explicit` argument if provided
    2. GITHUB_BASE_REF env var (prefixed with origin/)
    3. origin/HEAD
    4. main
    5. master

    Raises ValueError if nothing resolves.
    """
    if explicit:
        return explicit

    github_base = os.environ.get("GITHUB_BASE_REF")
    if github_base:
        return f"origin/{github_base}"

    candidates = ["origin/HEAD", "main", "master"]
    for candidate in candidates:
        try:
            _git(repo, "rev-parse", "--verify", candidate)
            return candidate
        except RuntimeError:
            continue

    raise ValueError(
        f"Could not resolve base ref. Tried: {candidates}. "
        "Pass --base explicitly or set GITHUB_BASE_REF."
    )


def changed_files(repo: Path, base: str, head: str = "HEAD") -> list[str]:
    """Return repo-relative POSIX paths of files changed between `base` and `head`.

    Uses merge-base so the comparison is against the fork point, not the
    current tip of `base` (matches PR semantics).
    """
    try:
        fork_point = _git(repo, "merge-base", base, head).strip()
    except RuntimeError:
        # Fall back to direct diff if merge-base fails (e.g. unrelated histories)
        fork_point = base

    output = _git(repo, "diff", "--name-only", f"{fork_point}..{head}")
    paths = [line.strip() for line in output.splitlines() if line.strip()]
    # git always emits forward slashes — no normalization needed
    return paths


def fork_point_sha(repo: Path, base: str, head: str = "HEAD") -> str:
    """Return the merge-base SHA between `base` and `head`."""
    try:
        return _git(repo, "merge-base", base, head).strip()
    except RuntimeError:
        return _git(repo, "rev-parse", base).strip()
