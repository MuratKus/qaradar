"""QA Radar CLI — run quality analysis from the terminal."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from qaradar.engine import run_healthcheck, run_pr_risk
from qaradar.models import RiskLevel

console = Console()


@click.group()
@click.version_option(version="0.3.2", prog_name="qaradar")
def main():
    """QA Radar — point it at a repo, get the quality landscape."""


@main.command()
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--days", default=90, help="Days of git history to analyze (default: 90)")
@click.option("--top", default=20, help="Number of risky modules to show (default: 20)")
@click.option("--json-output", is_flag=True, help="Output raw JSON instead of formatted tables")
@click.option(
    "--base",
    default=None,
    help="Base ref to diff against (e.g. main, origin/main). Enables diff-aware mode.",
)
def analyze(repo_path: str, days: int, top: int, json_output: bool, base: str | None):
    """Run a full QA health check on a repository.

    With --base, scores only files changed since that ref (diff-aware mode).
    """
    try:
        if base is not None:
            with console.status("[bold blue]Analyzing PR changes..."):
                pr_report = run_pr_risk(repo_path, base_ref=base, churn_days=days)
            if json_output:
                click.echo(json.dumps(pr_report.to_dict(), indent=2))
            else:
                _render_pr_risk(pr_report)
            return

        with console.status("[bold blue]Scanning repository..."):
            report = run_healthcheck(repo_path, churn_days=days, top_n=top)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]Git error:[/red] {e}")
        sys.exit(1)

    if json_output:
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
            "untested_files": report.untested_files,
            "high_churn": [
                {"path": c.path, "commits": c.commit_count}
                for c in report.high_churn_files
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    _render_report(report, days=days)


@main.command()
def serve():
    """Start the QA Radar MCP server (stdio transport)."""
    from qaradar.server import main as server_main

    server_main()


def _render_pr_risk(report) -> None:
    """Render a PrRiskReport with Rich tables."""
    s = report.summary()
    high_plus = s["high_plus_count"]
    total = s["changed_source_files"]

    if report.status == "no_changes":
        console.print("\n[dim]No changes detected relative to base ref.[/dim]\n")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Base ref:[/bold] {s['base_ref']}\n"
            f"[bold]Changed files:[/bold] {s['total_changed_files']}  "
            f"[bold]Source files:[/bold] {total}\n"
            f"[bold red]{s['critical_count']} CRITICAL[/bold red]  "
            f"[yellow]{s['high_count']} HIGH[/yellow]  "
            f"[blue]{s['medium_count']} MEDIUM[/blue]  "
            f"[green]{s['low_count']} LOW[/green]",
            title="[bold blue]QA Radar — PR Risk Report[/bold blue]",
            border_style="blue",
        )
    )

    headline_style = "bold red" if high_plus > 0 else "green"
    console.print(
        f"\n  [{headline_style}]{high_plus} of {total} changed source files are HIGH+ risk[/{headline_style}]"
    )

    if report.risky_changed_files:
        console.print()
        table = Table(title="Risky Changed Files", show_lines=False)
        table.add_column("File", style="cyan", no_wrap=True, max_width=55)
        table.add_column("Risk", justify="center", width=10)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Reasons", style="dim")

        for m in report.risky_changed_files:
            risk_style = _risk_style(m.risk_level)
            table.add_row(
                _truncate(m.path, 55),
                f"[{risk_style}]{m.risk_level.value.upper()}[/{risk_style}]",
                f"{m.risk_score:.2f}",
                "; ".join(m.reasons[:2]) if m.reasons else "-",
            )
        console.print(table)

    if report.changed_files_without_tests:
        console.print()
        console.print(
            f"[bold]Changed files without tests ({len(report.changed_files_without_tests)}):[/bold]"
        )
        for f in report.changed_files_without_tests[:10]:
            console.print(f"  [dim]·[/dim] {f}")

    if report.changed_test_files:
        console.print()
        console.print(f"[dim]Tests also touched: {', '.join(report.changed_test_files[:5])}[/dim]")

    console.print()


def _render_report(report, days: int = 90):
    """Render a health report with Rich tables."""
    summary = report.summary()

    # Header panel
    console.print()
    console.print(
        Panel(
            f"[bold]Repository:[/bold] {summary['repo']}\n"
            f"[bold]Source files:[/bold] {summary['source_files']}  "
            f"[bold]Test files:[/bold] {summary['test_files']}  "
            f"[bold]Ratio:[/bold] {summary['test_to_source_ratio']}\n"
            f"[bold]Avg coverage:[/bold] {_fmt_pct(summary['avg_coverage'])}  "
            f"[bold]Tested:[/bold] {summary['files_with_tests']}  "
            f"[bold]Untested:[/bold] {summary['files_without_tests']}",
            title="[bold blue]QA Radar Health Report[/bold blue]",
            border_style="blue",
        )
    )

    # Risk summary
    critical = summary["critical_risk_count"]
    high = summary["high_risk_count"]
    if critical > 0:
        console.print(f"\n  [bold red]CRITICAL risk modules: {critical}[/bold red]")
    if high > 0:
        console.print(f"  [bold yellow]HIGH risk modules: {high}[/bold yellow]")

    # Risky modules table
    if report.risky_modules:
        console.print()
        table = Table(title="Risky Modules", show_lines=False)
        table.add_column("File", style="cyan", no_wrap=True, max_width=50)
        table.add_column("Risk", justify="center", width=10)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Reasons", style="dim")

        for m in report.risky_modules:
            risk_style = _risk_style(m.risk_level)
            table.add_row(
                _truncate(m.path, 50),
                f"[{risk_style}]{m.risk_level.value.upper()}[/{risk_style}]",
                f"{m.risk_score:.2f}",
                "; ".join(m.reasons[:2]) if m.reasons else "-",
            )
        console.print(table)

    # High churn files
    if report.high_churn_files:
        console.print()
        table = Table(title=f"Highest Churn Files (last {days} days)")
        table.add_column("File", style="cyan", max_width=50)
        table.add_column("Commits", justify="right")
        table.add_column("Lines Changed", justify="right")
        table.add_column("Authors", justify="right")
        table.add_column("Recent (30d)", justify="right")

        for c in report.high_churn_files[:10]:
            table.add_row(
                _truncate(c.path, 50),
                str(c.commit_count),
                str(c.lines_added + c.lines_deleted),
                str(c.unique_authors),
                str(c.recent_commit_count),
            )
        console.print(table)

    # Coverage gaps
    if report.coverage_gaps:
        console.print()
        table = Table(title="Coverage Gaps (<50%)")
        table.add_column("File", style="cyan", max_width=50)
        table.add_column("Line Coverage", justify="right")
        table.add_column("Lines", justify="right")

        for c in report.coverage_gaps[:15]:
            table.add_row(
                _truncate(c.path, 50),
                f"{c.line_rate:.1%}",
                f"{c.lines_covered}/{c.lines_total}",
            )
        console.print(table)

    # Untested files
    if report.untested_files:
        console.print()
        console.print(f"[bold]Untested files ({len(report.untested_files)}):[/bold]")
        for f in report.untested_files[:15]:
            console.print(f"  [dim]·[/dim] {f}")
        if len(report.untested_files) > 15:
            console.print(f"  [dim]... and {len(report.untested_files) - 15} more[/dim]")

    console.print()


def _risk_style(level: RiskLevel) -> str:
    return {
        RiskLevel.CRITICAL: "bold red",
        RiskLevel.HIGH: "yellow",
        RiskLevel.MEDIUM: "blue",
        RiskLevel.LOW: "green",
    }[level]


def _fmt_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1%}"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return "..." + text[-(max_len - 3):]


if __name__ == "__main__":
    main()
