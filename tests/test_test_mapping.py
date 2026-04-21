"""Tests for analyzers/test_mapping.py — Tier 1 languages."""

from pathlib import Path

import pytest

from qaradar.analyzers.test_mapping import (
    _is_test_file,
    _is_source_file,
    _find_tests_for_source,
    _count_test_functions,
    analyze_test_mapping,
)


# --- _is_test_file ---

@pytest.mark.parametrize("path,expected", [
    # Python
    ("tests/test_calculator.py", True),
    ("tests/calculator_test.py", True),
    # JS/TS
    ("__tests__/utils.test.ts", True),
    ("src/utils.spec.js", True),
    ("src/app.test.tsx", True),
    # Go
    ("pkg/math_test.go", True),
    # Java
    ("src/FooTest.java", True),
    ("src/FooTests.java", True),
    # Rust: filename-pattern
    ("src/foo_test.rs", True),
    # Rust: Cargo integration test in tests/ dir
    ("tests/integration_basic.rs", True),
    ("crates/mylib/tests/smoke.rs", True),
    # Not test files
    ("src/calculator.py", False),
    ("src/utils.ts", False),
    ("pkg/math.go", False),
    # Monorepo: fixtures/helpers in __tests__/ must NOT count
    ("apps/web/__tests__/fixtures/user-data.ts", False),
    ("apps/web/__tests__/helpers/setup.ts", False),
    ("apps/web/__tests__/types.ts", False),
    # Python helper in tests/ without test_ prefix
    ("tests/fixtures/sample_data.py", False),
    ("tests/helpers/db.py", False),
])
def test_is_test_file(path, expected):
    assert _is_test_file(Path(path)) == expected


# --- _is_source_file ---

@pytest.mark.parametrize("path,expected", [
    ("src/calculator.py", True),
    ("src/utils.ts", True),
    ("pkg/math.go", True),
    # Excluded by name
    ("conftest.py", False),
    ("setup.py", False),
    ("__init__.py", False),
    # Test files excluded
    ("tests/test_foo.py", False),
    # Wrong extension
    ("README.md", False),
    ("config.yaml", False),
])
def test_is_source_file(path, expected):
    assert _is_source_file(Path(path)) == expected


# --- _find_tests_for_source ---

def test_find_tests_python():
    source = Path("src/calculator.py")
    tests = [Path("tests/test_calculator.py"), Path("tests/other_test.py")]
    matches = _find_tests_for_source(source, tests)
    assert Path("tests/test_calculator.py") in matches
    assert Path("tests/other_test.py") not in matches


def test_find_tests_typescript():
    source = Path("src/utils.ts")
    tests = [Path("__tests__/utils.test.ts"), Path("__tests__/other.test.ts")]
    matches = _find_tests_for_source(source, tests)
    assert Path("__tests__/utils.test.ts") in matches
    assert Path("__tests__/other.test.ts") not in matches


def test_find_tests_go():
    source = Path("pkg/math.go")
    tests = [Path("pkg/math_test.go"), Path("pkg/other_test.go")]
    matches = _find_tests_for_source(source, tests)
    assert Path("pkg/math_test.go") in matches
    assert Path("pkg/other_test.go") not in matches


def test_find_tests_no_match():
    source = Path("src/orphan.py")
    tests = [Path("tests/test_other.py")]
    assert _find_tests_for_source(source, tests) == []


# --- _count_test_functions ---

def test_count_python_tests(tmp_path):
    f = tmp_path / "test_foo.py"
    f.write_text("def test_one():\n    pass\ndef test_two():\n    pass\n")
    assert _count_test_functions(f) == 2


def test_count_ts_tests(tmp_path):
    f = tmp_path / "foo.test.ts"
    f.write_text("test('one', () => {});\nit('two', () => {});\n")
    assert _count_test_functions(f) == 2


def test_count_go_tests(tmp_path):
    f = tmp_path / "foo_test.go"
    f.write_text("func TestOne(t *testing.T) {}\nfunc TestTwo(t *testing.T) {}\n")
    assert _count_test_functions(f) == 2


def test_count_nonexistent_file(tmp_path):
    assert _count_test_functions(tmp_path / "missing.py") == 0


# --- analyze_test_mapping integration ---

def test_analyze_python_fixture(python_app):
    mappings = analyze_test_mapping(str(python_app))
    by_source = {m.source_path: m for m in mappings}

    calc_key = next((k for k in by_source if "calculator" in k), None)
    assert calc_key is not None
    assert by_source[calc_key].has_tests is True
    assert by_source[calc_key].test_count >= 5

    untested_key = next((k for k in by_source if "untested" in k), None)
    assert untested_key is not None
    assert by_source[untested_key].has_tests is False


def test_analyze_ts_fixture(ts_app):
    mappings = analyze_test_mapping(str(ts_app))
    by_source = {m.source_path: m for m in mappings}

    utils_key = next((k for k in by_source if "utils" in k), None)
    assert utils_key is not None
    assert by_source[utils_key].has_tests is True

    untested_key = next((k for k in by_source if "untested" in k), None)
    assert untested_key is not None
    assert by_source[untested_key].has_tests is False


def test_analyze_go_fixture(go_app):
    mappings = analyze_test_mapping(str(go_app))
    by_source = {m.source_path: m for m in mappings}

    math_key = next((k for k in by_source if "math.go" in k), None)
    assert math_key is not None
    assert by_source[math_key].has_tests is True


def test_analyze_rust_integration_tests_in_tests_dir(tmp_path):
    """Rust source files in src/ are matched to integration tests in sibling tests/ dir."""
    pkg = tmp_path / "mylib"
    (pkg / "src").mkdir(parents=True)
    (pkg / "src" / "lib.rs").write_text("pub fn hello() {}")
    (pkg / "src" / "utils.rs").write_text("pub fn util() {}")
    (pkg / "tests").mkdir()
    (pkg / "tests" / "integration.rs").write_text("#[test]\nfn test_hello() {}")

    mappings = analyze_test_mapping(str(tmp_path))
    by_source = {m.source_path: m for m in mappings}

    lib_key = next((k for k in by_source if "lib.rs" in k), None)
    assert lib_key is not None, "lib.rs not found in mappings"
    assert by_source[lib_key].has_tests is True

    utils_key = next((k for k in by_source if "utils.rs" in k), None)
    assert utils_key is not None, "utils.rs not found in mappings"
    assert by_source[utils_key].has_tests is True


def test_skip_dirs_excludes_sample_directories(tmp_path):
    # cookbook, examples, demo etc. should be ignored without any user config
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.py").write_text("def foo(): pass")
    for sample_dir in ("cookbook", "examples", "samples", "demo", "demos"):
        d = tmp_path / sample_dir
        d.mkdir()
        (d / "sample.py").write_text("# example code")

    mappings = analyze_test_mapping(str(tmp_path))
    paths = {m.source_path for m in mappings}

    assert any("core.py" in p for p in paths)
    assert not any("sample.py" in p for p in paths)


def test_skip_dirs_excludes_docs_src(tmp_path):
    # docs_src tutorial snippets (FastAPI-style) should not count as source
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def foo(): pass")
    (tmp_path / "docs_src").mkdir()
    (tmp_path / "docs_src" / "tutorial001.py").write_text("# tutorial code")

    mappings = analyze_test_mapping(str(tmp_path))
    paths = {m.source_path for m in mappings}

    assert any("app.py" in p for p in paths)
    assert not any("tutorial001.py" in p for p in paths)


def test_analyze_test_mapping_excludes_custom_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def foo(): pass")
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    (gen_dir / "schema.py").write_text("x = 1")

    all_mappings = analyze_test_mapping(str(tmp_path))
    all_paths = {m.source_path for m in all_mappings}
    assert any("app.py" in p for p in all_paths)
    assert any("schema.py" in p for p in all_paths)

    filtered = analyze_test_mapping(str(tmp_path), excludes=["generated/**"])
    filtered_paths = {m.source_path for m in filtered}
    assert any("app.py" in p for p in filtered_paths)
    assert not any("schema.py" in p for p in filtered_paths)
