"""QA Radar MCP Server — expose quality analysis tools to AI coding agents."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from qaradar.analyzers.churn import analyze_churn
from qaradar.analyzers.coverage import analyze_coverage
from qaradar.analyzers.risk import score_risks
from qaradar.analyzers.test_mapping import analyze_test_mapping
from qaradar.engine import run_healthcheck
from qaradar.models import RiskLevel

mcp = FastMCP("qaradar_mcp")


# --- Input models ---


class HealthcheckInput(BaseModel):
    """Input for full QA healthcheck."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(
        default=".",
        description="Path to the git repository to analyze (default: current directory)",
    )
    churn_days: int = Field(
        default=90,
        description="Number of days of git history to analyze for churn",
        ge=7,
        le=365,
    )
    top_n: int = Field(
        default=20,
        description="Number of top risky modules to include",
        ge=5,
        le=100,
    )


class RiskyModulesInput(BaseModel):
    """Input for risky modules query."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(default=".", description="Path to the git repository")
    min_risk: str = Field(
        default="high",
        description="Minimum risk level to include: 'critical', 'high', 'medium', or 'low'",
    )
    churn_days: int = Field(default=90, ge=7, le=365)


class ChurnInput(BaseModel):
    """Input for churn analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(default=".", description="Path to the git repository")
    days: int = Field(default=90, description="Number of days of history", ge=7, le=365)
    limit: int = Field(default=15, description="Max files to return", ge=1, le=100)


class CoverageInput(BaseModel):
    """Input for coverage gap analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(default=".", description="Path to the git repository")
    threshold: float = Field(
        default=0.5,
        description="Coverage threshold — files below this are flagged (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )


class UntestedFilesInput(BaseModel):
    """Input for untested files query."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(default=".", description="Path to the git repository")


# --- Tools ---


@mcp.tool(
    name="qaradar_healthcheck",
    annotations={
        "title": "QA Health Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qaradar_healthcheck(params: HealthcheckInput) -> str:
    """Run a full QA health check on a repository.

    Analyzes git churn, coverage data, and test mapping to produce a
    comprehensive quality landscape report with risk-scored modules.

    Returns a JSON report with: summary stats, risky modules ranked by
    risk score, untested files, high-churn files, and coverage gaps.
    """
    report = run_healthcheck(
        repo_path=params.repo_path,
        churn_days=params.churn_days,
        top_n=params.top_n,
    )
    return _format_report(report)


@mcp.tool(
    name="qaradar_risky_modules",
    annotations={
        "title": "Find Risky Modules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qaradar_risky_modules(params: RiskyModulesInput) -> str:
    """Find modules with the highest quality risk in the repository.

    Combines churn frequency, coverage gaps, and missing tests to identify
    files that deserve the most testing attention. Use this to prioritize
    where to write tests or focus exploratory testing.
    """
    risk_levels = _parse_min_risk(params.min_risk)

    churn = analyze_churn(params.repo_path, days=params.churn_days)
    coverage = analyze_coverage(params.repo_path)
    mappings = analyze_test_mapping(params.repo_path)
    risks = score_risks(churn, coverage, mappings)

    filtered = [r for r in risks if r.risk_level in risk_levels]

    items = []
    for r in filtered[:30]:
        item = {
            "path": r.path,
            "risk_level": r.risk_level.value,
            "risk_score": r.risk_score,
            "reasons": r.reasons,
            "scores": {
                "churn": r.churn_score,
                "coverage": r.coverage_score,
                "test_mapping": r.test_mapping_score,
            },
        }
        items.append(item)

    return json.dumps({"risky_modules": items, "count": len(items)}, indent=2)


@mcp.tool(
    name="qaradar_churn",
    annotations={
        "title": "Analyze Code Churn",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qaradar_churn(params: ChurnInput) -> str:
    """Analyze git history to find the most frequently changed files.

    High-churn files are more likely to contain regressions. Use this to
    identify hotspots that need stronger test coverage or closer review.
    """
    churn = analyze_churn(params.repo_path, days=params.days)

    items = []
    for c in churn[: params.limit]:
        items.append(
            {
                "path": c.path,
                "commits": c.commit_count,
                "lines_changed": c.lines_added + c.lines_deleted,
                "authors": c.unique_authors,
                "last_modified": c.last_modified,
                "recent_commits_30d": c.recent_commit_count,
            }
        )

    return json.dumps({"high_churn_files": items, "period_days": params.days}, indent=2)


@mcp.tool(
    name="qaradar_coverage_gaps",
    annotations={
        "title": "Find Coverage Gaps",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qaradar_coverage_gaps(params: CoverageInput) -> str:
    """Find files with coverage below the given threshold.

    Parses coverage reports (coverage.py JSON/XML, Cobertura, LCOV) and
    returns files sorted by coverage ascending (worst first).
    """
    coverage = analyze_coverage(params.repo_path)
    gaps = [c for c in coverage if c.line_rate < params.threshold]

    items = []
    for c in gaps:
        item = {
            "path": c.path,
            "line_coverage": f"{c.line_rate:.1%}",
            "lines_covered": c.lines_covered,
            "lines_total": c.lines_total,
        }
        if c.branch_rate is not None:
            item["branch_coverage"] = f"{c.branch_rate:.1%}"
        items.append(item)

    return json.dumps(
        {
            "coverage_gaps": items,
            "threshold": f"{params.threshold:.0%}",
            "count": len(items),
        },
        indent=2,
    )


@mcp.tool(
    name="qaradar_untested_files",
    annotations={
        "title": "Find Untested Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def qaradar_untested_files(params: UntestedFilesInput) -> str:
    """Find source files that have no corresponding test files.

    Uses naming conventions across languages (Python, JS/TS, Java, Go, Ruby,
    Kotlin, Swift, Rust) to detect test-to-source mappings.
    """
    mappings = analyze_test_mapping(params.repo_path)

    untested = [m for m in mappings if not m.has_tests]
    tested = [m for m in mappings if m.has_tests]

    untested_paths = [m.source_path for m in untested]
    tested_summary = [
        {"source": m.source_path, "tests": m.test_paths, "test_count": m.test_count}
        for m in tested[:10]
    ]

    return json.dumps(
        {
            "untested_files": untested_paths,
            "untested_count": len(untested),
            "tested_count": len(tested),
            "tested_examples": tested_summary,
        },
        indent=2,
    )


# --- Helpers ---


def _format_report(report) -> str:
    """Format a HealthReport as structured JSON for agent consumption."""
    output = {
        "summary": report.summary(),
        "risky_modules": [
            {
                "path": r.path,
                "risk_level": r.risk_level.value,
                "risk_score": r.risk_score,
                "reasons": r.reasons,
            }
            for r in report.risky_modules
        ],
        "untested_files": report.untested_files[:20],
        "high_churn_files": [
            {
                "path": c.path,
                "commits": c.commit_count,
                "lines_changed": c.lines_added + c.lines_deleted,
            }
            for c in report.high_churn_files
        ],
        "coverage_gaps": [
            {"path": c.path, "coverage": f"{c.line_rate:.1%}"}
            for c in report.coverage_gaps[:15]
        ],
    }
    return json.dumps(output, indent=2)


def _parse_min_risk(level: str) -> set[RiskLevel]:
    """Parse minimum risk level into a set of included levels."""
    level = level.lower()
    if level == "critical":
        return {RiskLevel.CRITICAL}
    elif level == "high":
        return {RiskLevel.CRITICAL, RiskLevel.HIGH}
    elif level == "medium":
        return {RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM}
    else:
        return {RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW}


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
