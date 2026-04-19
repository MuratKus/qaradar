"""Risk scoring — combine churn, coverage, and test mapping into actionable risk levels."""

from __future__ import annotations

from pathlib import Path

from qaradar.models import (
    CoverageEntry,
    FileChurn,
    ModuleRisk,
    RiskLevel,
    TestMapping,
)

from qaradar.analyzers.test_mapping import _is_test_file


def score_risks(
    churn_data: list[FileChurn],
    coverage_data: list[CoverageEntry],
    test_mappings: list[TestMapping],
) -> list[ModuleRisk]:
    """Combine all signals into per-file risk assessments.

    Scoring weights:
    - Churn:     0.35 (high churn = more opportunity for regression)
    - Coverage:  0.35 (low coverage = less safety net)
    - Test map:  0.30 (no tests = blind spot)

    Returns modules sorted by risk_score descending (riskiest first).
    """
    # Index data by path for fast lookup
    churn_by_path = {c.path: c for c in churn_data}
    coverage_by_path = {c.path: c for c in coverage_data}
    test_map_by_path = {t.source_path: t for t in test_mappings}

    # Collect all known source file paths (exclude test files)
    all_paths: set[str] = set()
    all_paths.update(churn_by_path.keys())
    all_paths.update(coverage_by_path.keys())
    all_paths.update(test_map_by_path.keys())
    all_paths = {p for p in all_paths if not _is_test_file(Path(p))}

    # Compute normalization factors for churn
    max_commits = max((c.commit_count for c in churn_data), default=1)
    max_churn_lines = max((c.lines_added + c.lines_deleted for c in churn_data), default=1)

    results = []
    for path in all_paths:
        churn = churn_by_path.get(path)
        coverage = coverage_by_path.get(path)
        test_map = test_map_by_path.get(path)

        churn_score = _compute_churn_score(churn, max_commits, max_churn_lines)
        coverage_score = _compute_coverage_score(coverage)
        test_map_score = _compute_test_mapping_score(test_map)

        # Weighted combination
        risk_score = (
            0.35 * churn_score
            + 0.35 * coverage_score
            + 0.30 * test_map_score
        )

        reasons = _build_reasons(churn, coverage, test_map, churn_score, coverage_score, test_map_score)
        risk_level = _classify_risk(risk_score)

        results.append(
            ModuleRisk(
                path=path,
                risk_level=risk_level,
                risk_score=round(risk_score, 3),
                churn_score=round(churn_score, 3),
                coverage_score=round(coverage_score, 3),
                test_mapping_score=round(test_map_score, 3),
                reasons=reasons,
                churn=churn,
                coverage=coverage,
                test_mapping=test_map,
            )
        )

    results.sort(key=lambda r: r.risk_score, reverse=True)
    return results


def _compute_churn_score(
    churn: FileChurn | None, max_commits: int, max_churn_lines: int
) -> float:
    """Higher score = more risky (more churn)."""
    if churn is None:
        return 0.3  # unknown = moderate baseline

    commit_ratio = churn.commit_count / max(max_commits, 1)
    churn_lines = churn.lines_added + churn.lines_deleted
    lines_ratio = churn_lines / max(max_churn_lines, 1)

    # Recent activity amplifier: if most commits are recent, risk is higher
    recency_factor = 1.0
    if churn.commit_count > 0:
        recent_ratio = churn.recent_commit_count / churn.commit_count
        recency_factor = 1.0 + (recent_ratio * 0.5)  # up to 1.5x

    raw = (0.6 * commit_ratio + 0.4 * lines_ratio) * recency_factor
    return min(raw, 1.0)


def _compute_coverage_score(coverage: CoverageEntry | None) -> float:
    """Higher score = more risky (less coverage)."""
    if coverage is None:
        return 0.7  # no coverage data = assume risky

    # Invert: 0% coverage → 1.0 risk, 100% coverage → 0.0 risk
    line_risk = 1.0 - coverage.line_rate

    # Branch coverage penalty if available
    if coverage.branch_rate is not None:
        branch_risk = 1.0 - coverage.branch_rate
        return 0.6 * line_risk + 0.4 * branch_risk

    return line_risk


def _compute_test_mapping_score(test_map: TestMapping | None) -> float:
    """Higher score = more risky (fewer/no tests)."""
    if test_map is None:
        return 0.5  # unknown

    if not test_map.has_tests:
        return 1.0  # no tests at all

    # More test functions = lower risk, with diminishing returns
    if test_map.test_count >= 10:
        return 0.05
    elif test_map.test_count >= 5:
        return 0.15
    elif test_map.test_count >= 3:
        return 0.25
    elif test_map.test_count >= 1:
        return 0.4

    return 0.6  # has test files but no detected test functions


def _classify_risk(score: float) -> RiskLevel:
    """Map numeric score to risk level."""
    if score >= 0.75:
        return RiskLevel.CRITICAL
    elif score >= 0.55:
        return RiskLevel.HIGH
    elif score >= 0.35:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def _build_reasons(
    churn: FileChurn | None,
    coverage: CoverageEntry | None,
    test_map: TestMapping | None,
    churn_score: float,
    coverage_score: float,
    test_map_score: float,
) -> list[str]:
    """Generate human-readable risk reasons."""
    reasons = []

    if churn and churn_score > 0.5:
        reasons.append(
            f"High churn: {churn.commit_count} commits, "
            f"{churn.lines_added + churn.lines_deleted} lines changed"
        )
        if churn.recent_commit_count > 3:
            reasons.append(f"Active recently: {churn.recent_commit_count} commits in last 30 days")

    if coverage is not None and coverage_score > 0.5:
        pct = round(coverage.line_rate * 100, 1)
        reasons.append(f"Low coverage: {pct}% line coverage ({coverage.lines_covered}/{coverage.lines_total})")
    elif coverage is None and coverage_score > 0.5:
        reasons.append("No coverage data available")

    if test_map is not None and test_map_score > 0.5:
        if not test_map.has_tests:
            reasons.append("No test files found for this source file")
        elif test_map.test_count == 0:
            reasons.append("Test files exist but no test functions detected")
    elif test_map is None:
        reasons.append("Could not determine test mapping")

    return reasons
