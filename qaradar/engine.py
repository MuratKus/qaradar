"""Core engine — orchestrate all analyzers into a single health report."""

from __future__ import annotations

from datetime import datetime, timezone

from qaradar.analyzers.churn import analyze_churn
from qaradar.analyzers.coverage import analyze_coverage
from qaradar.analyzers.risk import score_risks
from qaradar.analyzers.test_mapping import analyze_test_mapping, get_file_counts
from qaradar.config import QaradarConfig, load_config
from qaradar.models import HealthReport, RiskLevel


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
