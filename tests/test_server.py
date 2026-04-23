"""Tests for MCP tool handlers — verify they offload blocking work to a thread."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from qaradar.server import (
    ChurnInput,
    CoverageInput,
    HealthcheckInput,
    PrRiskInput,
    RiskyModulesInput,
    UntestedFilesInput,
    qaradar_churn,
    qaradar_coverage_gaps,
    qaradar_healthcheck,
    qaradar_pr_risk,
    qaradar_risky_modules,
    qaradar_untested_files,
)


def _run(coro):
    return asyncio.run(coro)


def _fake_health_report():
    r = MagicMock()
    r.summary.return_value = {
        "repo": ".", "analyzed_at": "2026-01-01", "source_files": 0,
        "test_files": 0, "test_to_source_ratio": 0, "avg_coverage": None,
        "files_with_tests": 0, "files_without_tests": 0,
        "critical_risk_count": 0, "high_risk_count": 0, "coverage_status": "ok",
    }
    r.risky_modules = []
    r.untested_files = []
    r.high_churn_files = []
    r.coverage_gaps = []
    return r


def _fake_pr_report():
    r = MagicMock()
    r.status = "ok"
    r.critical_count = 0
    r.high_count = 0
    r.changed_source_files = 0
    r.risky_changed_files = []
    r.changed_files_without_tests = []
    r.changed_test_files = []
    r.changed_untracked_by_analyzers = []
    r.summary.return_value = {
        "status": "ok", "base_ref": "main", "total_changed_files": 0,
        "changed_source_files": 0, "critical_count": 0, "high_count": 0,
        "medium_count": 0, "low_count": 0, "high_plus_count": 0,
        "files_without_tests": 0,
    }
    return r


def _make_run_sync_spy():
    """Return a fake anyio.to_thread.run_sync that records calls and executes the fn."""
    calls = []

    async def fake_run_sync(fn, *args, **kwargs):
        calls.append(True)
        return fn()

    return fake_run_sync, calls


# ---------------------------------------------------------------------------
# qaradar_pr_risk
# ---------------------------------------------------------------------------

def test_pr_risk_handler_offloads_to_thread():
    """qaradar_pr_risk must not call run_pr_risk directly in the event loop."""
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.run_pr_risk", return_value=_fake_pr_report()),
    ):
        _run(qaradar_pr_risk(PrRiskInput(repo_path=".", base_ref="main")))

    assert calls, "qaradar_pr_risk must offload work via anyio.to_thread.run_sync"


# ---------------------------------------------------------------------------
# qaradar_healthcheck
# ---------------------------------------------------------------------------

def test_healthcheck_handler_offloads_to_thread():
    """qaradar_healthcheck must not call run_healthcheck directly in the event loop."""
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.run_healthcheck", return_value=_fake_health_report()),
    ):
        _run(qaradar_healthcheck(HealthcheckInput(repo_path=".")))

    assert calls, "qaradar_healthcheck must offload work via anyio.to_thread.run_sync"


# ---------------------------------------------------------------------------
# qaradar_risky_modules
# ---------------------------------------------------------------------------

def test_risky_modules_handler_offloads_to_thread():
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.load_config", return_value=MagicMock(
            excludes=MagicMock(patterns=None),
            paths=MagicMock(coverage_file=None),
            weights=MagicMock(),
        )),
        patch("qaradar.server.analyze_churn", return_value=[]),
        patch("qaradar.server.analyze_coverage", return_value=[]),
        patch("qaradar.server.analyze_test_mapping", return_value=[]),
        patch("qaradar.server.score_risks", return_value=[]),
    ):
        _run(qaradar_risky_modules(RiskyModulesInput(repo_path=".")))

    assert calls, "qaradar_risky_modules must offload work via anyio.to_thread.run_sync"


# ---------------------------------------------------------------------------
# qaradar_churn
# ---------------------------------------------------------------------------

def test_churn_handler_offloads_to_thread():
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.load_config", return_value=MagicMock(
            excludes=MagicMock(patterns=None),
        )),
        patch("qaradar.server.analyze_churn", return_value=[]),
    ):
        _run(qaradar_churn(ChurnInput(repo_path=".")))

    assert calls, "qaradar_churn must offload work via anyio.to_thread.run_sync"


# ---------------------------------------------------------------------------
# qaradar_coverage_gaps
# ---------------------------------------------------------------------------

def test_coverage_gaps_handler_offloads_to_thread():
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.load_config", return_value=MagicMock(
            paths=MagicMock(coverage_file=None),
        )),
        patch("qaradar.server.analyze_coverage", return_value=[]),
    ):
        _run(qaradar_coverage_gaps(CoverageInput(repo_path=".")))

    assert calls, "qaradar_coverage_gaps must offload work via anyio.to_thread.run_sync"


# ---------------------------------------------------------------------------
# qaradar_untested_files
# ---------------------------------------------------------------------------

def test_untested_files_handler_offloads_to_thread():
    fake_run_sync, calls = _make_run_sync_spy()

    with (
        patch("anyio.to_thread.run_sync", side_effect=fake_run_sync),
        patch("qaradar.server.load_config", return_value=MagicMock(
            excludes=MagicMock(patterns=None),
        )),
        patch("qaradar.server.analyze_test_mapping", return_value=[]),
    ):
        _run(qaradar_untested_files(UntestedFilesInput(repo_path=".")))

    assert calls, "qaradar_untested_files must offload work via anyio.to_thread.run_sync"
