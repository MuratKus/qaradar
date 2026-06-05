"""Tests for qaradar/schedule.py — re-run criteria."""

from datetime import datetime, timedelta, timezone

from qaradar.config import QaradarConfig, ScheduleConfig
from qaradar.git import head_sha
from qaradar.models import HealthReport
from qaradar.schedule import should_run
from qaradar.state import save_run


def _empty_report(analyzed_at):
    return HealthReport(
        repo_path=".",
        analyzed_at=analyzed_at,
        total_source_files=1,
        total_test_files=0,
        test_to_source_ratio=0.0,
    )


def _save_at_head(repo, analyzed_at):
    save_run(str(repo), _empty_report(analyzed_at), head_sha(repo))


def test_no_prior_run_is_full(git_repo):
    repo, _ = git_repo
    decision = should_run(str(repo))
    assert decision.run is True
    assert decision.scope == "full"


def test_no_changes_no_run(git_repo):
    repo, _ = git_repo
    now = datetime.now(timezone.utc)
    _save_at_head(repo, now.isoformat())

    decision = should_run(str(repo), now=now)
    assert decision.run is False
    assert decision.scope == "none"
    assert decision.commits_since == 0
    assert decision.changed_files_since == 0


def test_interval_elapsed_triggers_full(git_repo):
    repo, _ = git_repo
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    _save_at_head(repo, old)

    config = QaradarConfig(schedule=ScheduleConfig(interval_days=7, min_changed_files=100))
    decision = should_run(str(repo), config=config, now=now)
    assert decision.run is True
    assert decision.scope == "full"
    assert decision.days_since >= 10


def test_diff_threshold_triggers_diff(git_repo):
    repo, commit = git_repo
    now = datetime.now(timezone.utc)
    _save_at_head(repo, now.isoformat())

    commit("b.py", message="add b")
    commit("c.py", message="add c")

    config = QaradarConfig(schedule=ScheduleConfig(interval_days=365, min_changed_files=2))
    decision = should_run(str(repo), config=config, now=now)
    assert decision.run is True
    assert decision.scope == "diff"
    assert decision.changed_files_since >= 2


def test_changes_below_threshold_no_run(git_repo):
    repo, commit = git_repo
    now = datetime.now(timezone.utc)
    _save_at_head(repo, now.isoformat())
    commit("b.py", message="add b")

    config = QaradarConfig(schedule=ScheduleConfig(interval_days=365, min_changed_files=10))
    decision = should_run(str(repo), config=config, now=now)
    assert decision.run is False
    assert decision.scope == "none"
    assert decision.commits_since == 1
