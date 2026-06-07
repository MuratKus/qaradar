"""Test-to-source mapping — discover which files have tests and which don't."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from qaradar.analyzers.languages import (
    LANGUAGES,
    SOURCE_EXTENSIONS,
    TEST_FILE_PATTERNS,
    language_for_ext,
)
from qaradar.models import TestMapping

# SOURCE_EXTENSIONS and TEST_FILE_PATTERNS are re-exported from languages.py
# (the single source of truth) for backwards compatibility with importers.
__all__ = [
    "SOURCE_EXTENSIONS",
    "TEST_FILE_PATTERNS",
    "analyze_test_mapping",
    "get_file_counts",
]

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "env", ".tox", ".mypy_cache", ".pytest_cache", "dist",
    "build", ".next", ".nuxt", "vendor", "target",
    # Sample/demo/docs code — real source that intentionally lacks tests
    "examples", "cookbook", "cookbooks", "samples", "demo", "demos",
    "docs_src", "doc_src",
}


def analyze_test_mapping(repo_path: str, excludes: list[str] | None = None) -> list[TestMapping]:
    """Map source files to their test files.

    Uses naming conventions and directory structure to infer relationships.
    Returns mappings for source files, sorted by untested first.
    """
    repo = Path(repo_path).resolve()

    source_files: list[Path] = []
    test_files: list[Path] = []

    for path in _walk_files(repo):
        rel = path.relative_to(repo)
        if excludes and _matches_excludes(rel, excludes):
            continue
        if _is_test_file(rel):
            test_files.append(rel)
        elif _is_source_file(rel):
            source_files.append(rel)

    # Build mappings
    mappings = []
    for source in source_files:
        matched_tests = _find_tests_for_source(source, test_files)
        test_count = sum(_count_test_functions(repo / t) for t in matched_tests)

        mappings.append(
            TestMapping(
                source_path=source.as_posix(),
                test_paths=[t.as_posix() for t in matched_tests],
                has_tests=len(matched_tests) > 0,
                test_count=test_count,
            )
        )

    # Sort: untested first, then by path
    mappings.sort(key=lambda m: (m.has_tests, m.source_path))
    return mappings


def _walk_files(repo: Path):
    """Walk repo files, skipping ignored directories."""
    for item in repo.iterdir():
        if item.name in SKIP_DIRS or item.name.startswith("."):
            continue
        if item.is_dir():
            yield from _walk_files(item)
        elif item.is_file():
            yield item


def _is_test_file(rel_path: Path) -> bool:
    """Check if a path is a test file by filename convention."""
    if any(p.match(rel_path.name) for p in TEST_FILE_PATTERNS):
        return True

    # Rust: Cargo convention — every .rs file in a tests/ dir is an integration test.
    if rel_path.suffix == ".rs" and "tests" in rel_path.parts[:-1]:
        return True

    return False


def _is_source_file(rel_path: Path) -> bool:
    """Check if a path is a source file (not test, not config)."""
    if rel_path.suffix not in SOURCE_EXTENSIONS:
        return False

    name = rel_path.name
    # Skip common non-source files
    if name in {"setup.py", "conftest.py", "manage.py", "__init__.py"}:
        return False

    # Skip if it looks like a test
    if _is_test_file(rel_path):
        return False

    return True


def _find_tests_for_source(source: Path, test_files: list[Path]) -> list[Path]:
    """Find test files that likely correspond to a source file.

    Matching is driven by each language's ``stem_templates`` (see
    ``languages.py``): the source stem is expanded into candidate test stems and
    compared against each test file's stem. Rust keeps a special case for
    integration tests living in a sibling ``tests/`` directory.
    """
    lang = language_for_ext(source.suffix)
    if lang is None:
        return []

    wanted_stems = {t.format(stem=source.stem) for t in lang.stem_templates}
    matches = []

    for test in test_files:
        # A test must belong to the same language family (shared extensions).
        if test.suffix not in lang.source_exts:
            continue

        if test.stem in wanted_stems:
            matches.append(test)
            continue

        # Rust: any .rs file in a sibling tests/ dir is an integration test.
        if lang.name == "rust" and _rust_integration_match(source, test):
            matches.append(test)

    return matches


def _rust_integration_match(source: Path, test: Path) -> bool:
    """Rust: tests/ is a sibling to src/ in the same package."""
    src_parts = list(source.parts)
    test_parts = list(test.parts)
    if "src" not in src_parts:
        return False
    src_idx = src_parts.index("src")
    pkg_prefix = src_parts[:src_idx]
    return (
        len(test_parts) > src_idx
        and test_parts[:src_idx] == pkg_prefix
        and test_parts[src_idx] == "tests"
    )


def _count_test_functions(test_path: Path) -> int:
    """Count test functions/methods in a test file (best effort).

    Uses the counting rules of the language that owns the test file's
    extension (see ``languages.py``). If the extension is unknown, every
    language's rules are tried — the patterns are distinct enough across
    languages that false positives are negligible.
    """
    if not test_path.exists():
        return 0

    try:
        content = test_path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return 0

    lang = language_for_ext(test_path.suffix)
    langs = [lang] if lang is not None else list(LANGUAGES)

    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for candidate in langs:
            if (
                any(stripped.startswith(p) for p in candidate.count_startswith)
                or stripped in candidate.count_exact
                or any(r.match(stripped) for r in candidate.count_regex)
            ):
                count += 1
                break

    return count


def _matches_excludes(rel_path: Path, excludes: list[str]) -> bool:
    """Return True if rel_path matches any exclude glob pattern."""
    path_str = rel_path.as_posix()
    for pattern in excludes:
        if fnmatch.fnmatch(path_str, pattern):
            return True
        # Also match if any parent dir prefix matches
        if fnmatch.fnmatch(rel_path.parts[0] + "/", pattern.split("/")[0] + "/"):
            prefix = pattern.split("/")[0]
            if rel_path.parts[0] == prefix:
                return True
    return False


def get_file_counts(repo_path: str) -> tuple[int, int]:
    """Quick count of source files and test files."""
    repo = Path(repo_path).resolve()
    source_count = 0
    test_count = 0

    for path in _walk_files(repo):
        rel = path.relative_to(repo)
        if _is_test_file(rel):
            test_count += 1
        elif _is_source_file(rel):
            source_count += 1

    return source_count, test_count
