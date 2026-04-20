"""QA Radar MCP Server — expose quality analysis tools to AI coding agents."""

from __future__ import annotations

import json

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from qaradar.analyzers.churn import analyze_churn
from qaradar.analyzers.coverage import analyze_coverage
from qaradar.analyzers.risk import score_risks
from qaradar.analyzers.test_mapping import analyze_test_mapping
from qaradar.config import load_config
from qaradar.engine import run_healthcheck, run_pr_risk
from qaradar.models import RiskLevel

mcp = FastMCP(
    "qaradar_mcp",
    instructions=(
        "Use this server whenever the user asks what to test, which files are risky, "
        "where regressions are likely, which modules lack tests, or wants a quality "
        "health report of a repository. Prefer these tools over running git log or "
        "parsing coverage reports manually — they return pre-scored, structured results "
        "at a fraction of the token cost."
    ),
)


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


class PrRiskInput(BaseModel):
    """Input for PR diff-aware risk analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo_path: str = Field(
        default=".",
        description="Path to the git repository to analyze (default: current directory)",
    )
    base_ref: str | None = Field(
        default=None,
        description=(
            "Base branch or ref to diff against (e.g. 'main', 'origin/main', 'HEAD~3'). "
            "Auto-detected from GITHUB_BASE_REF env or common branch names if omitted."
        ),
    )
    churn_days: int = Field(
        default=90,
        description="Days of git history used for historical churn scoring",
        ge=7,
        le=365,
    )
    max_results: int = Field(
        default=50,
        description="Maximum number of risky files to return",
        ge=1,
        le=500,
    )


# --- Tools ---


@mcp.tool(
    name="qaradar_healthcheck",
    annotations=ToolAnnotations(
        title="QA Health Check",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_healthcheck(params: HealthcheckInput) -> str:
    """Use when the user wants a full quality overview or asks 'what's the health of this repo?'.

    Analyzes git churn, coverage data, and test mapping to produce a
    comprehensive quality landscape report with risk-scored modules.

    Returns a JSON report with: summary stats, risky modules ranked by
    risk score, untested files, high-churn files, and coverage gaps.
    """
    report = await anyio.to_thread.run_sync(
        lambda: run_healthcheck(
            repo_path=params.repo_path,
            churn_days=params.churn_days,
            top_n=params.top_n,
        )
    )
    return _format_report(report)


@mcp.tool(
    name="qaradar_risky_modules",
    annotations=ToolAnnotations(
        title="Find Risky Modules",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_risky_modules(params: RiskyModulesInput) -> str:
    """Use when the user asks what to test first, which files are riskiest, or where regressions are likely.

    Combines churn frequency, coverage gaps, and missing tests to identify
    files that deserve the most testing attention. Ranks results by risk score
    so the most critical files appear first.
    """
    risk_levels = _parse_min_risk(params.min_risk)

    def _compute():
        cfg = load_config(params.repo_path)
        churn = analyze_churn(params.repo_path, days=params.churn_days, excludes=cfg.excludes.patterns or None)
        coverage = analyze_coverage(params.repo_path, explicit_path=cfg.paths.coverage_file)
        mappings = analyze_test_mapping(params.repo_path, excludes=cfg.excludes.patterns or None)
        return score_risks(churn, coverage, mappings, weights=cfg.weights)

    risks = await anyio.to_thread.run_sync(_compute)
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
    annotations=ToolAnnotations(
        title="Analyze Code Churn",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_churn(params: ChurnInput) -> str:
    """Use when the user asks which files change most often, what the hotspots are, or where regressions tend to occur.

    Analyzes git history to find frequently changed files — high-churn files
    are more likely to contain regressions and deserve stronger test coverage.
    """
    def _compute():
        cfg = load_config(params.repo_path)
        return analyze_churn(params.repo_path, days=params.days, excludes=cfg.excludes.patterns or None)

    churn = await anyio.to_thread.run_sync(_compute)
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
    annotations=ToolAnnotations(
        title="Find Coverage Gaps",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_coverage_gaps(params: CoverageInput) -> str:
    """Use when the user asks which files have low coverage, where the blind spots are, or wants to improve test coverage.

    Parses coverage reports (coverage.py JSON/XML, Cobertura, LCOV, Go cover profile)
    and returns files sorted by coverage ascending — worst-covered files first.
    """
    def _compute():
        cfg = load_config(params.repo_path)
        return analyze_coverage(params.repo_path, explicit_path=cfg.paths.coverage_file)

    coverage = await anyio.to_thread.run_sync(_compute)
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
    annotations=ToolAnnotations(
        title="Find Untested Files",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_untested_files(params: UntestedFilesInput) -> str:
    """Use when the user asks which files have no tests, what's completely uncovered, or wants to find testing blind spots.

    Detects source files with no corresponding test files using naming
    conventions across Python, JS/TS, Go, Java, Kotlin, Ruby, Swift, and Rust.
    """
    def _compute():
        cfg = load_config(params.repo_path)
        return analyze_test_mapping(params.repo_path, excludes=cfg.excludes.patterns or None)

    mappings = await anyio.to_thread.run_sync(_compute)
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


@mcp.tool(
    name="qaradar_pr_risk",
    annotations=ToolAnnotations(
        title="PR Diff Risk Analysis",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def qaradar_pr_risk(params: PrRiskInput) -> str:
    """Use when the user asks what's risky in this PR, which changed files need review, or which of my changes lack tests.

    Scores only files changed between a base ref and HEAD — not the whole repo.
    Uses full-repo normalization so risk scores stay calibrated even when only
    a few files changed. Automatically detects the base branch from git or
    GITHUB_BASE_REF if base_ref is not specified.

    Returns a JSON report with: risky changed files ranked by risk score,
    changed files without tests, test files touched, and a headline summary.
    """
    report = await anyio.to_thread.run_sync(
        lambda: run_pr_risk(
            repo_path=params.repo_path,
            base_ref=params.base_ref,
            churn_days=params.churn_days,
        )
    )
    return _format_pr_risk_report(report, max_results=params.max_results)


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


def _format_pr_risk_report(report, max_results: int = 50) -> str:
    """Format a PrRiskReport as structured JSON for agent consumption."""
    high_plus = report.critical_count + report.high_count
    headline = (
        f"{high_plus} of {report.changed_source_files} changed source files are HIGH+ risk"
        if report.status == "ok"
        else "No changes detected relative to base ref"
    )
    output = {
        "summary": report.summary(),
        "headline": headline,
        "risky_changed_files": [
            {
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
            for r in report.risky_changed_files[:max_results]
        ],
        "changed_files_without_tests": report.changed_files_without_tests,
        "changed_test_files": report.changed_test_files,
        "changed_untracked_by_analyzers": report.changed_untracked_by_analyzers,
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
