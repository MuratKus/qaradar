"""Coverage gap analysis — parse coverage reports and find weak spots."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from qaradar.models import CoverageEntry


def analyze_coverage(repo_path: str) -> list[CoverageEntry]:
    """Auto-detect and parse coverage reports in the repo.

    Supports:
    - coverage.py JSON (coverage.json)
    - coverage.py XML / Cobertura (coverage.xml)
    - lcov (coverage.lcov, lcov.info)

    Returns files sorted by line_rate ascending (worst coverage first).
    """
    repo = Path(repo_path).resolve()
    entries: list[CoverageEntry] = []

    # Try each format in order of preference
    for finder in [_find_coverage_json, _find_cobertura_xml, _find_lcov]:
        found = finder(repo)
        if found:
            entries = found
            break

    entries.sort(key=lambda e: e.line_rate)
    return entries


def _find_coverage_json(repo: Path) -> Optional[list[CoverageEntry]]:
    """Parse coverage.py JSON format."""
    candidates = [
        repo / "coverage.json",
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
        repo / "cobertura.xml",
        repo / "test-results" / "coverage.xml",
        repo / "reports" / "coverage.xml",
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
