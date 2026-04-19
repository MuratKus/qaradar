"""Coverage gap analysis — parse coverage reports and find weak spots."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from qaradar.models import CoverageEntry


def analyze_coverage(repo_path: str, explicit_path: Optional[str] = None) -> list[CoverageEntry]:
    """Auto-detect and parse coverage reports in the repo.

    Supports:
    - coverage.py JSON (coverage.json)
    - coverage.py XML / Cobertura (coverage.xml)
    - lcov (coverage.lcov, lcov.info)
    - Go cover profile (cover.out, coverage.out)

    If explicit_path is given it takes precedence over auto-discovery.
    Returns files sorted by line_rate ascending (worst coverage first).
    """
    repo = Path(repo_path).resolve()
    entries: list[CoverageEntry] = []

    if explicit_path:
        p = Path(explicit_path)
        if not p.is_absolute():
            p = repo / p
        if p.exists():
            entries = _parse_by_extension(p)
    else:
        for finder in [_find_coverage_json, _find_cobertura_xml, _find_lcov, _find_go_cover]:
            found = finder(repo)
            if found:
                entries = found
                break

    entries.sort(key=lambda e: e.line_rate)
    return entries


def _parse_by_extension(path: Path) -> list[CoverageEntry]:
    """Dispatch to the right parser based on file name/extension."""
    name = path.name
    if name.endswith(".json"):
        return _parse_coverage_json(path)
    if name.endswith(".xml"):
        return _parse_cobertura_xml(path)
    if name.endswith(".info") or name.endswith(".lcov"):
        return _parse_lcov(path)
    if name in ("cover.out", "coverage.out", "c.out"):
        return _parse_go_cover(path)
    return []


def _find_coverage_json(repo: Path) -> Optional[list[CoverageEntry]]:
    """Parse coverage.py JSON format."""
    candidates = [
        repo / "coverage.json",
        repo / "coverage" / "coverage.json",
        repo / ".coverage.json",
        repo / "htmlcov" / "status.json",
    ]
    for path in candidates:
        if path.exists():
            return _parse_coverage_json(path)
    return None


def _parse_coverage_json(path: Path) -> list[CoverageEntry]:
    """Parse coverage.py JSON report."""
    with open(path) as f:
        data = json.load(f)

    entries = []
    files_data = data.get("files", {})

    for filepath, file_info in files_data.items():
        summary = file_info.get("summary", {})
        covered = summary.get("covered_lines", 0)
        missing = summary.get("missing_lines", 0)
        total = covered + missing

        if total == 0:
            continue

        entries.append(
            CoverageEntry(
                path=filepath,
                line_rate=covered / total if total > 0 else 0.0,
                lines_covered=covered,
                lines_total=total,
                branch_rate=None,
                branches_covered=summary.get("covered_branches"),
                branches_total=summary.get("num_branches"),
            )
        )
    return entries


def _find_cobertura_xml(repo: Path) -> Optional[list[CoverageEntry]]:
    """Find and parse Cobertura/coverage.py XML."""
    candidates = [
        repo / "coverage.xml",
        repo / "coverage" / "coverage.xml",
        repo / "cobertura.xml",
        repo / "test-results" / "coverage.xml",
        repo / "reports" / "coverage.xml",
        repo / "build" / "reports" / "coverage.xml",
    ]
    for path in candidates:
        if path.exists():
            return _parse_cobertura_xml(path)
    return None


def _parse_cobertura_xml(path: Path) -> list[CoverageEntry]:
    """Parse Cobertura XML format (also used by coverage.py xml)."""
    tree = ET.parse(path)
    root = tree.getroot()
    entries = []

    for package in root.iter("package"):
        for cls in package.iter("class"):
            filename = cls.get("filename", "")
            line_rate = float(cls.get("line-rate", "0"))
            branch_rate_str = cls.get("branch-rate")

            lines = cls.find("lines")
            total = 0
            covered = 0
            if lines is not None:
                for line in lines.iter("line"):
                    total += 1
                    if int(line.get("hits", "0")) > 0:
                        covered += 1

            if total == 0:
                continue

            entries.append(
                CoverageEntry(
                    path=filename,
                    line_rate=line_rate,
                    lines_covered=covered,
                    lines_total=total,
                    branch_rate=float(branch_rate_str) if branch_rate_str else None,
                )
            )
    return entries


def _find_lcov(repo: Path) -> Optional[list[CoverageEntry]]:
    """Find and parse LCOV format."""
    candidates = [
        repo / "coverage.lcov",
        repo / "lcov.info",
        repo / "coverage" / "lcov.info",
    ]
    for path in candidates:
        if path.exists():
            return _parse_lcov(path)
    return None


def _parse_lcov(path: Path) -> list[CoverageEntry]:
    """Parse LCOV info format."""
    entries = []
    current_file = None
    lines_found = 0
    lines_hit = 0
    branches_found = 0
    branches_hit = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SF:"):
                current_file = line[3:]
                lines_found = 0
                lines_hit = 0
                branches_found = 0
                branches_hit = 0
            elif line.startswith("LF:"):
                lines_found = int(line[3:])
            elif line.startswith("LH:"):
                lines_hit = int(line[3:])
            elif line.startswith("BRF:"):
                branches_found = int(line[4:])
            elif line.startswith("BRH:"):
                branches_hit = int(line[4:])
            elif line == "end_of_record" and current_file:
                if lines_found > 0:
                    entries.append(
                        CoverageEntry(
                            path=current_file,
                            line_rate=lines_hit / lines_found if lines_found > 0 else 0.0,
                            lines_covered=lines_hit,
                            lines_total=lines_found,
                            branch_rate=(
                                branches_hit / branches_found if branches_found > 0 else None
                            ),
                            branches_covered=branches_hit if branches_found > 0 else None,
                            branches_total=branches_found if branches_found > 0 else None,
                        )
                    )
                current_file = None

    return entries


def _find_go_cover(repo: Path) -> Optional[list[CoverageEntry]]:
    """Find and parse a Go cover profile."""
    candidates = [
        repo / "cover.out",
        repo / "coverage.out",
        repo / "c.out",
    ]
    for path in candidates:
        if path.exists():
            return _parse_go_cover(path)
    return None


def _parse_go_cover(path: Path) -> list[CoverageEntry]:
    """Parse Go cover profile format.

    Format:
        mode: set|count|atomic
        path/to/file.go:startLine.startCol,endLine.endCol numStmt count
    """
    file_stats: dict[str, dict] = {}

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("mode:"):
                continue

            # e.g. github.com/user/pkg/foo.go:10.5,20.10 3 1
            try:
                location, rest = line.rsplit(" ", 2)[0], line.split()
                filepath = location.split(":")[0]
                num_stmt = int(rest[1])
                count = int(rest[2])
            except (ValueError, IndexError):
                continue

            if filepath not in file_stats:
                file_stats[filepath] = {"total": 0, "covered": 0}
            file_stats[filepath]["total"] += num_stmt
            if count > 0:
                file_stats[filepath]["covered"] += num_stmt

    entries = []
    for filepath, stats in file_stats.items():
        total = stats["total"]
        if total == 0:
            continue
        covered = stats["covered"]
        entries.append(
            CoverageEntry(
                path=filepath,
                line_rate=covered / total,
                lines_covered=covered,
                lines_total=total,
            )
        )
    return entries
