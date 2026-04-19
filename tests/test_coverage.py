"""Tests for analyzers/coverage.py — all four formats."""


import pytest

from qaradar.analyzers.coverage import (
    _parse_coverage_json,
    _parse_cobertura_xml,
    _parse_lcov,
    _parse_go_cover,
    analyze_coverage,
)


# --- coverage.py JSON ---

def test_parse_coverage_json(tmp_path):
    f = tmp_path / "coverage.json"
    f.write_text("""{
      "files": {
        "src/foo.py": {"summary": {"covered_lines": 8, "missing_lines": 2}},
        "src/bar.py": {"summary": {"covered_lines": 0, "missing_lines": 5}}
      }
    }""")
    entries = _parse_coverage_json(f)
    by_path = {e.path: e for e in entries}

    assert "src/foo.py" in by_path
    assert by_path["src/foo.py"].line_rate == pytest.approx(0.8)
    assert by_path["src/foo.py"].lines_covered == 8
    assert by_path["src/foo.py"].lines_total == 10

    assert by_path["src/bar.py"].line_rate == pytest.approx(0.0)


def test_parse_coverage_json_skips_zero_total(tmp_path):
    f = tmp_path / "coverage.json"
    f.write_text('{"files": {"empty.py": {"summary": {"covered_lines": 0, "missing_lines": 0}}}}')
    entries = _parse_coverage_json(f)
    assert entries == []


def test_analyze_coverage_json_fixture(python_app):
    entries = analyze_coverage(str(python_app))
    by_path = {e.path: e for e in entries}
    assert "src/calculator.py" in by_path
    assert by_path["src/calculator.py"].line_rate == pytest.approx(1.0)
    assert "src/untested.py" in by_path
    assert by_path["src/untested.py"].line_rate == pytest.approx(0.0)
    # Sorted worst first
    assert entries[0].line_rate <= entries[-1].line_rate


# --- Cobertura XML ---

COBERTURA_XML = """\
<?xml version="1.0" ?>
<coverage>
  <packages>
    <package name="src">
      <classes>
        <class filename="src/app.py" line-rate="0.75" branch-rate="0.5">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            <line number="3" hits="1"/>
            <line number="4" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""

def test_parse_cobertura_xml(tmp_path):
    f = tmp_path / "coverage.xml"
    f.write_text(COBERTURA_XML)
    entries = _parse_cobertura_xml(f)
    assert len(entries) == 1
    e = entries[0]
    assert e.path == "src/app.py"
    assert e.line_rate == pytest.approx(0.75)
    assert e.lines_covered == 3
    assert e.lines_total == 4
    assert e.branch_rate == pytest.approx(0.5)


# --- LCOV ---

LCOV_DATA = """\
SF:src/utils.ts
LF:10
LH:8
BRF:4
BRH:3
end_of_record
SF:src/empty.ts
LF:0
LH:0
end_of_record
"""

def test_parse_lcov(tmp_path):
    f = tmp_path / "lcov.info"
    f.write_text(LCOV_DATA)
    entries = _parse_lcov(f)
    by_path = {e.path: e for e in entries}

    assert "src/utils.ts" in by_path
    e = by_path["src/utils.ts"]
    assert e.line_rate == pytest.approx(0.8)
    assert e.lines_covered == 8
    assert e.lines_total == 10
    assert e.branch_rate == pytest.approx(0.75)

    # Zero-total file should be skipped
    assert "src/empty.ts" not in by_path


def test_analyze_coverage_lcov_fixture(ts_app):
    entries = analyze_coverage(str(ts_app))
    by_path = {e.path: e for e in entries}
    assert "src/utils.ts" in by_path
    assert by_path["src/utils.ts"].line_rate == pytest.approx(1.0)
    assert "src/untested.ts" in by_path
    assert by_path["src/untested.ts"].line_rate == pytest.approx(0.0)


# --- Go cover profile ---

GO_COVER = """\
mode: set
pkg/math.go:3.25,5.2 1 1
pkg/math.go:7.30,9.2 1 0
pkg/other.go:1.10,3.2 2 1
"""

def test_parse_go_cover(tmp_path):
    f = tmp_path / "cover.out"
    f.write_text(GO_COVER)
    entries = _parse_go_cover(f)
    by_path = {e.path: e for e in entries}

    assert "pkg/math.go" in by_path
    e = by_path["pkg/math.go"]
    assert e.lines_total == 2
    assert e.lines_covered == 1
    assert e.line_rate == pytest.approx(0.5)

    assert "pkg/other.go" in by_path
    assert by_path["pkg/other.go"].line_rate == pytest.approx(1.0)


def test_analyze_coverage_go_fixture(go_app):
    entries = analyze_coverage(str(go_app))
    assert len(entries) > 0
    assert all(e.lines_total > 0 for e in entries)


def test_analyze_coverage_empty_repo(tmp_path):
    entries = analyze_coverage(str(tmp_path))
    assert entries == []
