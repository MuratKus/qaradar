"""Re-run criteria — decide whether (and how) to re-analyze a repo.

This is the "engine bit" of scheduling: given the recorded last run, the
configured cadence, and the current git state, it answers *should we run again,
and over the whole repo or just the diff?* It does **not** itself schedule
anything — wire ``should_run`` into cron, CI, a git hook, or call it from an
agent (via the ``qaradar_should_run`` MCP tool) after it finishes work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from qaradar.config import QaradarConfig, load_config
from qaradar.git import changed_files, commits_since, head_sha
from qaradar.state import load_state


@dataclass
class RunDecision:
    run: bool
    scope: str  # "full" | "diff" | "none"
    reason: str
    last_run_at: str | None = None
    last_run_sha: str | None = None
    head_sha: str | None = None
    days_since: float | None = None
    commits_since: int | None = None
    changed_files_since: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def should_run(
    repo_path: str,
    config: QaradarConfig | None = None,
    now: datetime | None = None,
) -> RunDecision:
    """Evaluate the re-run criteria for a repo.

    Logic:
      * No prior run recorded            -> run, scope="full"
      * Stored SHA no longer in history  -> run, scope="full"
      * >= interval_days since last run  -> run, scope="full"
      * >= min_changed_files changed     -> run, scope="diff"
      * otherwise                        -> no run, scope="none"
    """
    if config is None:
        config = load_config(repo_path)
    sched = config.schedule
    now = now or datetime.now(timezone.utc)
    repo = Path(repo_path).resolve()

    head = head_sha(repo)
    state = load_state(repo_path)

    if state is None or not state.head_sha:
        return RunDecision(
            run=True,
            scope="full",
            reason="No previous run recorded",
            head_sha=head,
        )

    commits = commits_since(repo, state.head_sha)
    if commits is None:
        return RunDecision(
            run=True,
            scope="full",
            reason="Last-run commit no longer in history (history rewritten); full rescan",
            last_run_at=state.analyzed_at,
            last_run_sha=state.head_sha,
            head_sha=head,
        )

    changed = len(changed_files(repo, state.head_sha))

    last_dt = _parse_iso(state.analyzed_at)
    days_since = (now - last_dt).total_seconds() / 86400 if last_dt else None

    base = RunDecision(
        run=False,
        scope="none",
        reason="",
        last_run_at=state.analyzed_at,
        last_run_sha=state.head_sha,
        head_sha=head,
        days_since=round(days_since, 3) if days_since is not None else None,
        commits_since=commits,
        changed_files_since=changed,
    )

    if days_since is not None and days_since >= sched.interval_days:
        base.run = True
        base.scope = "full"
        base.reason = (
            f"{days_since:.1f}d since last run >= interval_days "
            f"({sched.interval_days}); full rescan"
        )
        return base

    if changed >= sched.min_changed_files:
        base.run = True
        base.scope = "diff"
        base.reason = (
            f"{changed} files changed since last run >= min_changed_files "
            f"({sched.min_changed_files}); diff-scoped run"
        )
        return base

    base.reason = (
        f"No criteria met ({changed} changed files, "
        f"{days_since:.1f}d elapsed)" if days_since is not None
        else f"No criteria met ({changed} changed files)"
    )
    return base
