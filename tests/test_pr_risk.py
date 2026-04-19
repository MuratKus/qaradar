"""Tests for run_pr_risk — diff-aware risk analysis."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from qaradar.engine import run_pr_risk
from qaradar.models import FileChurn, ModuleRisk, RiskLevel, TestMapping


# Helpers

def _make_churn(path: str, commits: int = 5, lines: int = 100) -> FileChurn:
    return FileChurn(
        path=path,
        commit_count=commits,
        lines_added=lines,
        lines_deleted=0,
        unique_authors=1,
        last_modified="2026-04-01",
        recent_commit_count=commits,
    )


def _make_risk(path: str, level: RiskLevel = RiskLevel.HIGH) -> ModuleRisk:
    scores = {
        RiskLevel.CRITICAL: 0.9,
        RiskLevel.HIGH: 0.6,
        RiskLevel.MEDIUM: 0.4,
        RiskLevel.LOW: 0.1,
    }
    return ModuleRisk(
        path=path,
        risk_level=level,
        risk_score=scores[level],
        churn_score=0.5,
        coverage_score=0.5,
        test_mapping_score=0.5,
    )


def _git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one commit."""
    (tmp_path / ".git").mkdir()
    return tmp_path


# --- empty diff ---

def test_empty_diff_returns_no_changes_status(tmp_path):
    repo = _git_repo(tmp_path)

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=[]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    assert report.status == "no_changes"
    assert report.total_changed_files == 0
    assert report.risky_changed_files == []


# --- normalization invariant ---

def test_normalization_uses_full_repo_not_just_changed_files(tmp_path):
    """Regression: scoring must use full-repo churn for normalization.

    If we only passed changed-file churn to score_risks, max_commits would be
    computed over a single file, making every PR file look maximally churny.
    This test verifies the output-layer filter approach preserves correct scores.
    """
    repo = _git_repo(tmp_path)

    # Full repo has a very high-churn file that is NOT in the diff.
    # The changed file has low churn (2 commits). With correct normalization
    # (max_commits=100), the changed file's churn score should be low, not 1.0.
    high_churn_file = _make_churn("src/hotspot.py", commits=100, lines=1000)
    low_churn_file = _make_churn("src/changed.py", commits=2, lines=20)
    full_churn = [high_churn_file, low_churn_file]

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=["src/changed.py"]),
        patch("qaradar.engine.analyze_churn", return_value=full_churn),
        patch("qaradar.engine.analyze_coverage", return_value=[]),
        patch("qaradar.engine.analyze_test_mapping", return_value=[]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    assert len(report.risky_changed_files) == 1
    risk = report.risky_changed_files[0]
    assert risk.path == "src/changed.py"
    # churn_score should be well below 1.0 because max_commits=100 from hotspot
    assert risk.churn_score < 0.5, (
        f"churn_score={risk.churn_score} — normalization is using the wrong max"
    )


# --- test file bucketing ---

def test_test_files_go_to_changed_test_files_not_risky(tmp_path):
    repo = _git_repo(tmp_path)
    # A Python test file in the diff
    changed = ["src/calculator.py", "tests/test_calculator.py"]

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=changed),
        patch("qaradar.engine.analyze_churn", return_value=[]),
        patch("qaradar.engine.analyze_coverage", return_value=[]),
        patch("qaradar.engine.analyze_test_mapping", return_value=[]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    assert "tests/test_calculator.py" in report.changed_test_files
    risky_paths = [r.path for r in report.risky_changed_files]
    assert "tests/test_calculator.py" not in risky_paths


# --- untracked files ---

def test_non_source_files_go_to_untracked_bucket(tmp_path):
    repo = _git_repo(tmp_path)
    changed = ["src/app.py", "README.md", ".github/workflows/ci.yml"]

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=changed),
        patch("qaradar.engine.analyze_churn", return_value=[]),
        patch("qaradar.engine.analyze_coverage", return_value=[]),
        patch("qaradar.engine.analyze_test_mapping", return_value=[]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    assert "README.md" in report.changed_untracked_by_analyzers
    assert ".github/workflows/ci.yml" in report.changed_untracked_by_analyzers


# --- Windows backslash path matching ---

def test_windows_backslash_paths_match_posix_diff_paths(tmp_path):
    """TestMapping.source_path may use backslashes on Windows; diff uses forward slashes."""
    repo = _git_repo(tmp_path)

    # Simulate Windows-style path from test_mapping analyzer
    windows_path_mapping = TestMapping(
        source_path="src\\calculator.py",  # backslash as from Path.__str__ on Windows
        test_paths=[],
        has_tests=False,
        test_count=0,
    )

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=["src/calculator.py"]),
        patch("qaradar.engine.analyze_churn", return_value=[]),
        patch("qaradar.engine.analyze_coverage", return_value=[]),
        patch("qaradar.engine.analyze_test_mapping", return_value=[windows_path_mapping]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    # The changed source file should be recognized as having no tests
    assert "src/calculator.py" in report.changed_files_without_tests


# --- risk counts ---

def test_risk_counts_are_correct(tmp_path):
    repo = _git_repo(tmp_path)
    changed = ["src/a.py", "src/b.py", "src/c.py"]

    mock_risks = [
        _make_risk("src/a.py", RiskLevel.CRITICAL),
        _make_risk("src/b.py", RiskLevel.HIGH),
        _make_risk("src/c.py", RiskLevel.MEDIUM),
        _make_risk("src/not_changed.py", RiskLevel.CRITICAL),  # should be excluded
    ]

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=changed),
        patch("qaradar.engine.analyze_churn", return_value=[]),
        patch("qaradar.engine.analyze_coverage", return_value=[]),
        patch("qaradar.engine.analyze_test_mapping", return_value=[]),
        patch("qaradar.engine.score_risks", return_value=mock_risks),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    assert report.critical_count == 1
    assert report.high_count == 1
    assert report.medium_count == 1
    assert report.low_count == 0
    assert len(report.risky_changed_files) == 3
    risky_paths = {r.path for r in report.risky_changed_files}
    assert "src/not_changed.py" not in risky_paths


# --- summary ---

def test_summary_returns_expected_keys(tmp_path):
    repo = _git_repo(tmp_path)

    with (
        patch("qaradar.engine.resolve_base_ref", return_value="main"),
        patch("qaradar.engine.fork_point_sha", return_value="abc123"),
        patch("qaradar.engine.changed_files", return_value=[]),
    ):
        report = run_pr_risk(str(repo), base_ref="main")

    s = report.summary()
    for key in ("base_ref", "total_changed_files", "critical_count", "high_plus_count", "status"):
        assert key in s, f"Missing key: {key}"
