"""Test-to-source mapping — discover which files have tests and which don't."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from qaradar.models import TestMapping

TEST_FILE_PATTERNS = [
    re.compile(r"^test_.*\.py$"),           # Python: test_foo.py
    re.compile(r"^.*_test\.py$"),           # Python: foo_test.py
    re.compile(r"^.*\.test\.[jt]sx?$"),     # JS/TS: foo.test.js, foo.test.tsx
    re.compile(r"^.*\.spec\.[jt]sx?$"),     # JS/TS: foo.spec.js, foo.spec.tsx
    re.compile(r"^.*Test\.java$"),          # Java: FooTest.java
    re.compile(r"^.*Tests\.java$"),         # Java: FooTests.java
    re.compile(r"^.*_test\.go$"),           # Go: foo_test.go
    re.compile(r"^.*_test\.rb$"),           # Ruby: foo_test.rb
    re.compile(r"^.*_spec\.rb$"),           # Ruby: foo_spec.rb
    re.compile(r"^.*Tests?\.kt$"),          # Kotlin
    re.compile(r"^.*Tests?\.swift$"),       # Swift
    re.compile(r"^.*_test\.rs$"),           # Rust
]

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt", ".swift", ".go", ".rb", ".rs",
}

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
    """Find test files that likely correspond to a source file."""
    stem = source.stem
    ext = source.suffix
    matches = []

    for test in test_files:
        test_name = test.name
        test_stem = test.stem

        # Direct naming conventions
        # Python: foo.py → test_foo.py or foo_test.py
        if ext == ".py":
            if test_name == f"test_{stem}.py" or test_name == f"{stem}_test.py":
                matches.append(test)
                continue

        # JS/TS: foo.js → foo.test.js or foo.spec.js
        if ext in {".js", ".ts", ".jsx", ".tsx"}:
            base = stem.split(".")[0]  # handle foo.test → foo
            if test_stem in {f"{base}.test", f"{base}.spec"}:
                matches.append(test)
                continue

        # Java/Kotlin: Foo.java → FooTest.java
        if ext in {".java", ".kt"}:
            if test_stem in {f"{stem}Test", f"{stem}Tests"}:
                matches.append(test)
                continue

        # Go: foo.go → foo_test.go
        if ext == ".go":
            if test_name == f"{stem}_test.go":
                matches.append(test)
                continue

        # Ruby: foo.rb → foo_test.rb or foo_spec.rb
        if ext == ".rb":
            if test_name in {f"{stem}_test.rb", f"{stem}_spec.rb"}:
                matches.append(test)
                continue

        # Rust: foo.rs → foo_test.rs (direct), or any .rs in sibling tests/ dir
        if ext == ".rs":
            if test_name == f"{stem}_test.rs":
                matches.append(test)
                continue
            # Integration tests: tests/ is a sibling to src/ in the same package
            src_parts = list(source.parts)
            test_parts = list(test.parts)
            if "src" in src_parts:
                src_idx = src_parts.index("src")
                pkg_prefix = src_parts[:src_idx]
                if (len(test_parts) > src_idx
                        and test_parts[:src_idx] == pkg_prefix
                        and test_parts[src_idx] == "tests"):
                    matches.append(test)
                    continue

    return matches


def _count_test_functions(test_path: Path) -> int:
    """Count test functions/methods in a test file (best effort)."""
    if not test_path.exists():
        return 0

    try:
        content = test_path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return 0

    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        # Python: def test_xxx
        if stripped.startswith("def test_") or stripped.startswith("async def test_"):
            count += 1
        # JS/TS: it(', test(', it.each
        elif re.match(r"^\s*(it|test)\s*[\.(]", stripped):
            count += 1
        # Java/Kotlin: @Test
        elif stripped == "@Test":
            count += 1
        # Go: func Test
        elif stripped.startswith("func Test"):
            count += 1
        # Ruby: it "
        elif re.match(r"^\s*it\s+['\"]", stripped):
            count += 1

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
