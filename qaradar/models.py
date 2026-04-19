"""Shared data models for QA Radar analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FileChurn:
    """Git churn data for a single file."""

    path: str
    commit_count: int
    lines_added: int
    lines_deleted: int
    unique_authors: int
    last_modified: str  # ISO date
    recent_commit_count: int = 0  # commits in last 30 days


@dataclass
class CoverageEntry:
    """Coverage data for a single file."""

    path: str
    line_rate: float  # 0.0 - 1.0
    lines_covered: int
    lines_total: int
    branch_rate: Optional[float] = None
    branches_covered: Optional[int] = None
    branches_total: Optional[int] = None


@dataclass
class TestMapping:
    """Mapping between a source file and its test files."""

    source_path: str
    test_paths: list[str] = field(default_factory=list)
    has_tests: bool = False
    test_count: int = 0  # number of test functions/methods found


@dataclass
class ModuleRisk:
    """Combined risk assessment for a module/file."""

    path: str
    risk_level: RiskLevel
    risk_score: float  # 0.0 - 1.0
    churn_score: float
    coverage_score: float
    test_mapping_score: float
    reasons: list[str] = field(default_factory=list)

    # raw data references
    churn: Optional[FileChurn] = None
    coverage: Optional[CoverageEntry] = None
    test_mapping: Optional[TestMapping] = None


@dataclass
class HealthReport:
    """Complete QA health report for a repository."""

    repo_path: str
    analyzed_at: str  # ISO datetime
    total_source_files: int
    total_test_files: int
    test_to_source_ratio: float

    # per-file results
    risky_modules: list[ModuleRisk] = field(default_factory=list)
    untested_files: list[str] = field(default_factory=list)
    high_churn_files: list[FileChurn] = field(default_factory=list)
    coverage_gaps: list[CoverageEntry] = field(default_factory=list)

    # summary stats
    avg_coverage: Optional[float] = None
    files_with_tests: int = 0
    files_without_tests: int = 0
    coverage_status: str = "ok"  # "ok" | "no_report_found"

    def summary(self) -> dict:
        """Return a compact summary dict."""
        return {
            "repo": self.repo_path,
            "analyzed_at": self.analyzed_at,
            "source_files": self.total_source_files,
            "test_files": self.total_test_files,
            "test_to_source_ratio": round(self.test_to_source_ratio, 2),
            "avg_coverage": round(self.avg_coverage, 2) if self.avg_coverage else None,
            "files_with_tests": self.files_with_tests,
            "files_without_tests": self.files_without_tests,
            "critical_risk_count": sum(
                1 for m in self.risky_modules if m.risk_level == RiskLevel.CRITICAL
            ),
            "high_risk_count": sum(
                1 for m in self.risky_modules if m.risk_level == RiskLevel.HIGH
            ),
            "coverage_status": self.coverage_status,
        }


@dataclass
class PrRiskReport:
    """Risk report scoped to files changed in a PR / branch diff."""

    repo_path: str
    analyzed_at: str
    base_ref: str
    head_ref: str
    fork_point_sha: str

    total_changed_files: int
    changed_source_files: int
    changed_test_files: list[str] = field(default_factory=list)
    changed_untracked_by_analyzers: list[str] = field(default_factory=list)

    risky_changed_files: list[ModuleRisk] = field(default_factory=list)
    changed_files_without_tests: list[str] = field(default_factory=list)

    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    status: str = "ok"  # "ok" | "no_changes"

    def summary(self) -> dict:
        """Return a compact summary dict."""
        high_plus = self.critical_count + self.high_count
        return {
            "repo": self.repo_path,
            "analyzed_at": self.analyzed_at,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "total_changed_files": self.total_changed_files,
            "changed_source_files": self.changed_source_files,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "high_plus_count": high_plus,
            "files_without_tests": len(self.changed_files_without_tests),
            "status": self.status,
        }
