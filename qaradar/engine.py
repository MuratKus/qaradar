"""Core engine — orchestrate all analyzers into a single health report."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qaradar.analyzers.churn import analyze_churn
from qaradar.analyzers.coverage import analyze_coverage
from qaradar.analyzers.risk import score_risks
from qaradar.analyzers.test_mapping import _is_test_file, analyze_test_mapping, get_file_counts
from qaradar.config import QaradarConfig, load_config
from qaradar.git import changed_files, fork_point_sha, resolve_base_ref
from qaradar.models import HealthReport, PrRiskReport, RiskLevel


def _posix(path: str) -> str:
    """Normalize a path to POSIX forward slashes."""
    return path.replace("\\", "/")


def run_healthcheck(
    repo_path: str,
    churn_days: int = 90,
    top_n: int = 20,
    config: QaradarConfig | None = None,
) -> HealthReport:
    """Run a full QA health check on a repository.

    Args:
        repo_path: Path to the git repository root.
        churn_days: How many days of git history to analyze.
        top_n: Number of top risky modules to include in report.

    Returns:
        A complete HealthReport with risk assessments.
    """
    if config is None:
        config = load_config(repo_path)

    excludes = config.excludes.patterns or None
    explicit_coverage = config.paths.coverage_file

    # Run individual analyzers
    churn_data = analyze_churn(repo_path, days=churn_days, excludes=excludes)
    coverage_data = analyze_coverage(repo_path, explicit_path=explicit_coverage)
    test_mappings = analyze_test_mapping(repo_path, excludes=excludes)

    # Combine into risk scores
    all_risks = score_risks(churn_data, coverage_data, test_mappings, weights=config.weights)

    # File counts
    source_count, test_count = get_file_counts(repo_path)

    # Compute summary stats
    avg_coverage = None
    coverage_status = "no_report_found"
    if coverage_data:
        avg_coverage = sum(c.line_rate for c in coverage_data) / len(coverage_data)
        coverage_status = "ok"

    files_with_tests = sum(1 for m in test_mappings if m.has_tests)
    files_without_tests = sum(1 for m in test_mappings if not m.has_tests)

    # Filter top risky modules
    risky_modules = [r for r in all_risks if r.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}]
    if len(risky_modules) < top_n:
        # Pad with medium-risk if we don't have enough high/critical
        medium = [r for r in all_risks if r.risk_level == RiskLevel.MEDIUM]
        risky_modules.extend(medium[: top_n - len(risky_modules)])
    risky_modules = risky_modules[:top_n]

    # Untested files
    untested = [m.source_path for m in test_mappings if not m.has_tests]

    # High churn files (top 10)
    high_churn = churn_data[:10]

    # Coverage gaps (below 50%)
    coverage_gaps = [c for c in coverage_data if c.line_rate < 0.5]

    return HealthReport(
        repo_path=repo_path,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        total_source_files=source_count,
        total_test_files=test_count,
        test_to_source_ratio=test_count / max(source_count, 1),
        risky_modules=risky_modules,
        untested_files=untested,
        high_churn_files=high_churn,
        coverage_gaps=coverage_gaps,
        avg_coverage=avg_coverage,
        files_with_tests=files_with_tests,
        files_without_tests=files_without_tests,
        coverage_status=coverage_status,
    )


def run_pr_risk(
    repo_path: str,
    base_ref: str | None = None,
    churn_days: int = 90,
    config: QaradarConfig | None = None,
) -> PrRiskReport:
    """Score only files changed between `base_ref` and HEAD.

    Args:
        repo_path: Path to the git repository root.
        base_ref: Base branch/ref to diff against. Auto-detected if None.
        churn_days: Days of git history for churn scoring.

    Returns:
        A PrRiskReport with risk assessments scoped to the changed files.
    """
    if config is None:
        config = load_config(repo_path)

    repo = Path(repo_path).resolve()
    excludes = config.excludes.patterns or None
    explicit_coverage = config.paths.coverage_file

    base = resolve_base_ref(repo, base_ref)
    sha = fork_point_sha(repo, base)
    changed = set(changed_files(repo, base))

    if not changed:
        return PrRiskReport(
            repo_path=repo_path,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            base_ref=base,
            head_ref="HEAD",
            fork_point_sha=sha,
            total_changed_files=0,
            changed_source_files=0,
            status="no_changes",
        )

    # Run full-repo analyzers so normalization factors are correct.
    # Filtering happens on the *output* of score_risks, not the input.
    churn_data = analyze_churn(repo_path, days=churn_days, excludes=excludes)
    coverage_data = analyze_coverage(repo_path, explicit_path=explicit_coverage)
    test_mappings = analyze_test_mapping(repo_path, excludes=excludes)

    all_risks = score_risks(churn_data, coverage_data, test_mappings, weights=config.weights)

    # Classify changed files into buckets
    analyzer_known: set[str] = set()
    analyzer_known.update(_posix(r.path) for r in all_risks)
    test_map_paths = {_posix(m.source_path) for m in test_mappings if not m.has_tests}

    changed_test_files = [p for p in changed if _is_test_file(Path(p))]
    changed_source_files_set = set(changed) - set(changed_test_files)
    changed_untracked = [
        p for p in changed_source_files_set if p not in analyzer_known
    ]

    # Filter risk list to changed source files (POSIX-normalize to handle Windows paths)
    risky_changed = [r for r in all_risks if _posix(r.path) in changed_source_files_set]

    # Changed source files with no tests
    changed_without_tests = [p for p in changed_source_files_set if p in test_map_paths]

    critical = sum(1 for r in risky_changed if r.risk_level == RiskLevel.CRITICAL)
    high = sum(1 for r in risky_changed if r.risk_level == RiskLevel.HIGH)
    medium = sum(1 for r in risky_changed if r.risk_level == RiskLevel.MEDIUM)
    low = sum(1 for r in risky_changed if r.risk_level == RiskLevel.LOW)

    return PrRiskReport(
        repo_path=repo_path,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        base_ref=base,
        head_ref="HEAD",
        fork_point_sha=sha,
        total_changed_files=len(changed),
        changed_source_files=len(changed_source_files_set) - len(changed_untracked),
        changed_test_files=sorted(changed_test_files),
        changed_untracked_by_analyzers=sorted(changed_untracked),
        risky_changed_files=risky_changed,
        changed_files_without_tests=sorted(changed_without_tests),
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        status="ok",
    )
