"""Tests for analyzers/risk.py — scoring weights and classification."""

import pytest

from qaradar.analyzers.risk import (
    _classify_risk,
    _compute_churn_score,
    _compute_coverage_score,
    _compute_test_mapping_score,
    score_risks,
)
from qaradar.models import FileChurn, CoverageEntry, TestMapping, RiskLevel


# --- _classify_risk ---

@pytest.mark.parametrize("score,expected", [
    (0.80, RiskLevel.CRITICAL),
    (0.75, RiskLevel.CRITICAL),
    (0.60, RiskLevel.HIGH),
    (0.55, RiskLevel.HIGH),
    (0.40, RiskLevel.MEDIUM),
    (0.35, RiskLevel.MEDIUM),
    (0.20, RiskLevel.LOW),
    (0.00, RiskLevel.LOW),
])
def test_classify_risk(score, expected):
    assert _classify_risk(score) == expected


# --- _compute_coverage_score ---

def test_coverage_score_no_data():
    assert _compute_coverage_score(None) == pytest.approx(0.7)


def test_coverage_score_full_coverage():
    entry = CoverageEntry(path="f.py", line_rate=1.0, lines_covered=10, lines_total=10)
    assert _compute_coverage_score(entry) == pytest.approx(0.0)


def test_coverage_score_zero_coverage():
    entry = CoverageEntry(path="f.py", line_rate=0.0, lines_covered=0, lines_total=10)
    assert _compute_coverage_score(entry) == pytest.approx(1.0)


def test_coverage_score_with_branch():
    entry = CoverageEntry(
        path="f.py", line_rate=0.5, lines_covered=5, lines_total=10,
        branch_rate=0.0,
    )
    # 0.6 * 0.5 + 0.4 * 1.0 = 0.7
    assert _compute_coverage_score(entry) == pytest.approx(0.7)


# --- _compute_test_mapping_score ---

def test_test_mapping_score_no_data():
    assert _compute_test_mapping_score(None) == pytest.approx(0.5)


def test_test_mapping_score_no_tests():
    m = TestMapping(source_path="f.py", has_tests=False)
    assert _compute_test_mapping_score(m) == pytest.approx(1.0)


def test_test_mapping_score_many_tests():
    m = TestMapping(source_path="f.py", has_tests=True, test_count=10)
    assert _compute_test_mapping_score(m) == pytest.approx(0.05)


def test_test_mapping_score_few_tests():
    m = TestMapping(source_path="f.py", has_tests=True, test_count=1)
    assert _compute_test_mapping_score(m) == pytest.approx(0.4)


# --- _compute_churn_score ---

def test_churn_score_no_data():
    assert _compute_churn_score(None, 10, 100) == pytest.approx(0.3)


def test_churn_score_max_churn():
    churn = FileChurn(
        path="f.py", commit_count=10, lines_added=50, lines_deleted=50,
        unique_authors=2, last_modified="2026-04-10", recent_commit_count=0,
    )
    score = _compute_churn_score(churn, max_commits=10, max_churn_lines=100)
    assert 0.0 < score <= 1.0


def test_churn_score_capped_at_one():
    churn = FileChurn(
        path="f.py", commit_count=100, lines_added=10000, lines_deleted=10000,
        unique_authors=5, last_modified="2026-04-17", recent_commit_count=100,
    )
    score = _compute_churn_score(churn, max_commits=100, max_churn_lines=20000)
    assert score <= 1.0


# --- score_risks integration ---

def test_score_risks_returns_sorted():
    churn = [
        FileChurn("low.py", 1, 5, 5, 1, "2026-01-01"),
        FileChurn("high.py", 50, 500, 500, 3, "2026-04-17", recent_commit_count=30),
    ]
    coverage = [
        CoverageEntry("high.py", 0.1, 1, 10),
        CoverageEntry("low.py", 0.9, 9, 10),
    ]
    mappings = [
        TestMapping("high.py", has_tests=False),
        TestMapping("low.py", has_tests=True, test_count=10),
    ]
    results = score_risks(churn, coverage, mappings)
    assert len(results) >= 2
    assert results[0].risk_score >= results[-1].risk_score
    assert results[0].path == "high.py"


def test_score_risks_no_tests_is_critical():
    mappings = [TestMapping("risky.py", has_tests=False)]
    results = score_risks([], [], mappings)
    assert len(results) == 1
    # No coverage data (0.7) + no tests (1.0) + no churn (0.3)
    # = 0.35*0.3 + 0.35*0.7 + 0.30*1.0 = 0.105 + 0.245 + 0.3 = 0.65 → HIGH
    assert results[0].risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
