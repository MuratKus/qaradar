"""Tests for Istanbul/Jest JSON coverage parsing + monorepo discovery."""

from pathlib import Path

import pytest

from qaradar.analyzers.coverage import (
    _parse_istanbul_final,
    _parse_istanbul_summary,
    _rel_to_repo,
    analyze_coverage,
)


def test_parse_istanbul_final():
    data = {
        "/abs/repo/src/foo.ts": {
            "path": "/abs/repo/src/foo.ts",
            "s": {"0": 1, "1": 0, "2": 3, "3": 0},
            "b": {"0": [1, 0]},
        },
        "/abs/repo/src/bar.ts": {
            "path": "/abs/repo/src/bar.ts",
            "s": {"0": 0, "1": 0},
            "b": {},
        },
    }
    entries = _parse_istanbul_final(data)
    by_path = {e.path: e for e in entries}
    assert by_path["/abs/repo/src/foo.ts"].line_rate == pytest.approx(0.5)
    assert by_path["/abs/repo/src/foo.ts"].branch_rate == pytest.approx(0.5)
    assert by_path["/abs/repo/src/bar.ts"].line_rate == pytest.approx(0.0)


def test_parse_istanbul_summary():
    data = {
        "total": {"lines": {"total": 100, "covered": 50, "pct": 50}},
        "src/foo.ts": {
            "lines": {"total": 10, "covered": 9, "pct": 90},
            "branches": {"total": 4, "covered": 2, "pct": 50},
        },
    }
    entries = _parse_istanbul_summary(data)
    assert len(entries) == 1
    assert entries[0].path == "src/foo.ts"
    assert entries[0].line_rate == pytest.approx(0.9)
    assert entries[0].branch_rate == pytest.approx(0.5)


def test_rel_to_repo_absolute(tmp_path):
    repo = tmp_path
    (repo / "src").mkdir()
    abs_path = str(repo / "src" / "foo.ts")
    assert _rel_to_repo(abs_path, repo) == "src/foo.ts"


def test_rel_to_repo_relative(tmp_path):
    assert _rel_to_repo("./packages/core/src/foo.ts", tmp_path) == "packages/core/src/foo.ts"


def test_analyze_coverage_finds_monorepo_istanbul(ts_monorepo):
    entries = analyze_coverage(str(ts_monorepo))
    by_path = {e.path: e for e in entries}
    # Discovered under packages/core/coverage/coverage-final.json
    math = next((e for p, e in by_path.items() if "math.ts" in p), None)
    untested = next((e for p, e in by_path.items() if "untested.ts" in p), None)
    assert math is not None and math.line_rate == pytest.approx(1.0)
    assert untested is not None and untested.line_rate == pytest.approx(0.0)


def test_analyze_coverage_dart_lcov(dart_app):
    entries = analyze_coverage(str(dart_app))
    by_path = {e.path: e for e in entries}
    assert any("calculator.dart" in p for p in by_path)
