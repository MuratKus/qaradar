"""Tests for the CLI — analyze command, output formats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from click.testing import CliRunner

from qaradar.cli import main
from qaradar.models import PrRiskReport


def _pr_report(repo_path: str, **kwargs) -> PrRiskReport:
    defaults = dict(
        repo_path=repo_path,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        base_ref="main",
        head_ref="HEAD",
        fork_point_sha="abc123",
        total_changed_files=0,
        changed_source_files=0,
        status="no_changes",
    )
    defaults.update(kwargs)
    return PrRiskReport(**defaults)


def test_pr_risk_json_output_includes_risky_changed_files(tmp_path):
    """--json-output with --base must include risky_changed_files list, not just counts."""
    runner = CliRunner()
    report = _pr_report(str(tmp_path))

    with patch("qaradar.cli.run_pr_risk", return_value=report):
        result = runner.invoke(main, ["analyze", str(tmp_path), "--base", "main", "--json-output"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = json.loads(result.output)
    assert "risky_changed_files" in data, (
        f"CLI --json-output with --base must include 'risky_changed_files', "
        f"but got keys: {list(data.keys())}"
    )
    assert isinstance(data["risky_changed_files"], list)


def test_pr_risk_json_output_includes_changed_files_without_tests(tmp_path):
    """--json-output with --base must include changed_files_without_tests list."""
    runner = CliRunner()
    report = _pr_report(str(tmp_path))

    with patch("qaradar.cli.run_pr_risk", return_value=report):
        result = runner.invoke(main, ["analyze", str(tmp_path), "--base", "main", "--json-output"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "changed_files_without_tests" in data, (
        f"Missing 'changed_files_without_tests' in JSON output. Keys: {list(data.keys())}"
    )
