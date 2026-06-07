"""Tests for mobile + monorepo language support (Phase 1 additions)."""

from pathlib import Path

import pytest

from qaradar.analyzers.languages import SOURCE_EXTENSIONS, language_for_ext
from qaradar.analyzers.test_mapping import (
    _count_test_functions,
    _find_tests_for_source,
    _is_test_file,
    analyze_test_mapping,
)


# --- registry sanity ---

def test_registry_covers_new_extensions():
    for ext in (".m", ".mm", ".dart", ".swift", ".kt"):
        assert ext in SOURCE_EXTENSIONS
        assert language_for_ext(ext) is not None


# --- _is_test_file for new conventions ---

@pytest.mark.parametrize("path,expected", [
    # Objective-C
    ("Tests/CalculatorTests.m", True),
    ("Tests/CalculatorTest.mm", True),
    ("Sources/Calculator.m", False),
    # Dart
    ("test/calculator_test.dart", True),
    ("lib/calculator.dart", False),
    # React Native dash-suffix
    ("__tests__/utils-test.ts", True),
    ("__tests__/App-test.tsx", True),
    ("__tests__/utils-spec.js", True),
    # Bare files in __tests__ are still NOT tests (no .test/-test suffix)
    ("__tests__/types.ts", False),
    ("__tests__/helpers/setup.ts", False),
])
def test_is_test_file_new_conventions(path, expected):
    assert _is_test_file(Path(path)) == expected


# --- source→test mapping for new conventions ---

def test_find_tests_objc():
    src = Path("Sources/Calculator.m")
    tests = [Path("Tests/CalculatorTests.m"), Path("Tests/OtherTests.m")]
    matches = _find_tests_for_source(src, tests)
    assert Path("Tests/CalculatorTests.m") in matches
    assert Path("Tests/OtherTests.m") not in matches


def test_find_tests_dart():
    src = Path("lib/calculator.dart")
    tests = [Path("test/calculator_test.dart"), Path("test/other_test.dart")]
    matches = _find_tests_for_source(src, tests)
    assert Path("test/calculator_test.dart") in matches


def test_find_tests_react_native_dash():
    src = Path("src/utils.ts")
    tests = [Path("__tests__/utils-test.ts"), Path("__tests__/other-test.ts")]
    matches = _find_tests_for_source(src, tests)
    assert Path("__tests__/utils-test.ts") in matches
    assert Path("__tests__/other-test.ts") not in matches


# --- counting test functions across languages ---

@pytest.mark.parametrize("filename,content,expected", [
    ("CalculatorTests.swift", "func testAdd() {}\nfunc testSub() {}\n", 2),
    ("CalculatorTest.kt", "@Test\nfun a() {}\n@Test\nfun b() {}\n", 2),
    ("CalculatorTests.m", "- (void)testAdd {}\n- (void)testSub {}\n", 2),
    ("calculator_test.dart", "test('a', () {});\ntestWidgets('b', (t) {});\n", 2),
])
def test_count_test_functions_new_languages(tmp_path, filename, content, expected):
    f = tmp_path / filename
    f.write_text(content)
    assert _count_test_functions(f) == expected


# --- integration on fixtures ---

@pytest.mark.parametrize("fixture_name,tested_hint,untested_hint", [
    ("dart_app", "calculator", "untested"),
    ("swift_app", "Calculator", "Untested"),
    ("kotlin_app", "Calculator", "Untested"),
    ("objc_app", "Calculator", "Untested"),
    ("rn_app", "utils", "untested"),
])
def test_fixture_test_mapping(request, fixture_name, tested_hint, untested_hint):
    app = request.getfixturevalue(fixture_name)
    mappings = analyze_test_mapping(str(app))
    by_source = {m.source_path: m for m in mappings}

    tested = next((m for k, m in by_source.items() if tested_hint in k), None)
    assert tested is not None, f"{tested_hint} not found in {list(by_source)}"
    assert tested.has_tests is True
    assert tested.test_count >= 2

    untested = next((m for k, m in by_source.items() if untested_hint in k), None)
    assert untested is not None
    assert untested.has_tests is False


def test_ts_monorepo_test_mapping(ts_monorepo):
    mappings = analyze_test_mapping(str(ts_monorepo))
    by_source = {m.source_path: m for m in mappings}

    math = next((m for k, m in by_source.items() if "math.ts" in k), None)
    assert math is not None
    assert math.has_tests is True

    untested = next((m for k, m in by_source.items() if "untested.ts" in k), None)
    assert untested is not None
    assert untested.has_tests is False
