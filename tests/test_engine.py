"""Integration tests for engine.py — end-to-end on fixture repos."""

from unittest.mock import patch

import pytest

from qaradar.engine import run_healthcheck
from qaradar.models import RiskLevel


def _no_churn(repo_path, days=90):
    """Stub that returns empty churn so tests don't need a real git repo."""
    return []


def test_engine_python_fixture(python_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(python_app))

    assert report.total_source_files >= 2
    assert report.total_test_files >= 1
    assert report.files_with_tests >= 1
    assert report.files_without_tests >= 1
    assert report.avg_coverage is not None
    assert 0.0 <= report.avg_coverage <= 1.0

    untested = report.untested_files
    assert any("untested" in f for f in untested)


def test_engine_ts_fixture(ts_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(ts_app))

    assert report.total_source_files >= 2
    assert report.files_with_tests >= 1
    assert report.avg_coverage is not None


def test_engine_go_fixture(go_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(go_app))

    assert report.total_source_files >= 1
    assert report.files_with_tests >= 1


def test_engine_summary_keys(python_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(python_app))

    summary = report.summary()
    for key in ["repo", "source_files", "test_files", "avg_coverage",
                "files_with_tests", "files_without_tests",
                "critical_risk_count", "high_risk_count"]:
        assert key in summary


def test_engine_top_n_respected(python_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(python_app), top_n=1)

    assert len(report.risky_modules) <= 1


def test_engine_empty_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(tmp_path))

    assert report.total_source_files == 0
    assert report.risky_modules == []
