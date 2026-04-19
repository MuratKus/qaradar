"""Integration tests for engine.py — end-to-end on fixture repos."""

from unittest.mock import patch

import pytest

from qaradar.engine import run_healthcheck


def _no_churn(repo_path, days=90, excludes=None):
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


def test_engine_non_git_dir_raises_clear_error(tmp_path):
    """Non-git directory gives a descriptive ValueError, not a raw git error."""
    with pytest.raises(ValueError, match="git repo"):
        run_healthcheck(str(tmp_path))


def test_engine_no_coverage_sets_status_field(tmp_path):
    (tmp_path / ".git").mkdir()
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(tmp_path))

    assert report.coverage_status == "no_report_found"


def test_engine_with_coverage_sets_status_ok(python_app):
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(python_app))

    assert report.coverage_status == "ok"


_COBERTURA_XML = """\
<?xml version="1.0" ?>
<coverage>
  <packages><package name="src">
    <classes><class filename="src/app.py" line-rate="0.75" branch-rate="0.5">
      <lines>
        <line number="1" hits="1"/>
        <line number="2" hits="0"/>
      </lines>
    </class></classes>
  </package></packages>
</coverage>
"""


def test_engine_uses_qaradar_toml_coverage_path(tmp_path):
    (tmp_path / ".git").mkdir()
    cov_dir = tmp_path / "custom"
    cov_dir.mkdir()
    (cov_dir / "cov.xml").write_text(_COBERTURA_XML)
    (tmp_path / "qaradar.toml").write_text('[paths]\ncoverage_file = "custom/cov.xml"\n')
    with patch("qaradar.engine.analyze_churn", side_effect=_no_churn):
        report = run_healthcheck(str(tmp_path))
    assert report.coverage_status == "ok"
    assert report.avg_coverage is not None
