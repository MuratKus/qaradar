"""Central registry of language support.

Single source of truth for which file extensions are source code, how test
files are named per language, how a source file maps to its test file(s), and
how to count test functions inside a test file.

Adding a language = adding one ``Language`` entry below (plus a fixture/test).
Previously this knowledge was split between ``test_mapping.py`` and
``churn.py``; both now derive from here so they can never drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Language:
    """Test conventions for a single language.

    Attributes:
        name: Identifier (lowercase).
        source_exts: File suffixes (with dot) that count as source for this
            language. Test files for the language share these suffixes.
        test_patterns: Regexes matched against a *filename* to decide whether a
            file is a test file.
        stem_templates: ``str.format`` templates expanded with ``stem=<source
            stem>`` and compared against a candidate test file's stem to map a
            source file to its tests. e.g. ``"test_{stem}"`` matches
            ``test_foo`` for source ``foo``.
        count_startswith: Stripped-line prefixes that mark a test function.
        count_exact: Exact stripped lines that mark a test function.
        count_regex: Regexes matched against a stripped line that mark a test.
    """

    name: str
    source_exts: tuple[str, ...]
    test_patterns: tuple[re.Pattern, ...] = ()
    stem_templates: tuple[str, ...] = ()
    count_startswith: tuple[str, ...] = ()
    count_exact: tuple[str, ...] = ()
    count_regex: tuple[re.Pattern, ...] = field(default_factory=tuple)


LANGUAGES: tuple[Language, ...] = (
    Language(
        name="python",
        source_exts=(".py",),
        test_patterns=(
            re.compile(r"^test_.*\.py$"),   # test_foo.py
            re.compile(r"^.*_test\.py$"),   # foo_test.py
        ),
        stem_templates=("test_{stem}", "{stem}_test"),
        count_startswith=("def test_", "async def test_"),
    ),
    Language(
        # JS / TS / JSX / TSX — also covers React Native (dash-suffix convention)
        name="javascript",
        source_exts=(".js", ".ts", ".jsx", ".tsx"),
        test_patterns=(
            re.compile(r"^.*\.test\.[jt]sx?$"),   # foo.test.ts
            re.compile(r"^.*\.spec\.[jt]sx?$"),   # foo.spec.tsx
            re.compile(r"^.*-test\.[jt]sx?$"),    # React Native: Foo-test.js
            re.compile(r"^.*-spec\.[jt]sx?$"),    # Foo-spec.js
        ),
        stem_templates=(
            "{stem}.test", "{stem}.spec",
            "{stem}-test", "{stem}-spec",
        ),
        count_regex=(re.compile(r"^(it|test)\s*[.(]"),),
    ),
    Language(
        name="go",
        source_exts=(".go",),
        test_patterns=(re.compile(r"^.*_test\.go$"),),
        stem_templates=("{stem}_test",),
        count_startswith=("func Test",),
    ),
    Language(
        name="java",
        source_exts=(".java",),
        test_patterns=(
            re.compile(r"^.*Test\.java$"),
            re.compile(r"^.*Tests\.java$"),
        ),
        stem_templates=("{stem}Test", "{stem}Tests"),
        count_exact=("@Test",),
    ),
    Language(
        name="kotlin",
        source_exts=(".kt",),
        test_patterns=(re.compile(r"^.*Tests?\.kt$"),),
        stem_templates=("{stem}Test", "{stem}Tests"),
        count_exact=("@Test",),
    ),
    Language(
        name="swift",
        source_exts=(".swift",),
        test_patterns=(re.compile(r"^.*Tests?\.swift$"),),
        stem_templates=("{stem}Test", "{stem}Tests"),
        # XCTest methods: func testSomething()
        count_regex=(re.compile(r"^func test"),),
    ),
    Language(
        name="objc",
        source_exts=(".m", ".mm"),
        test_patterns=(
            re.compile(r"^.*Tests?\.mm?$"),   # FooTests.m / FooTest.mm
        ),
        stem_templates=("{stem}Test", "{stem}Tests"),
        # XCTest in Objective-C: - (void)testSomething
        count_regex=(re.compile(r"^-\s*\(\s*void\s*\)\s*test"),),
    ),
    Language(
        name="dart",
        source_exts=(".dart",),
        test_patterns=(re.compile(r"^.*_test\.dart$"),),
        stem_templates=("{stem}_test",),
        # package:test / flutter_test
        count_regex=(re.compile(r"^(test|testWidgets)\s*\("),),
    ),
    Language(
        name="ruby",
        source_exts=(".rb",),
        test_patterns=(
            re.compile(r"^.*_test\.rb$"),
            re.compile(r"^.*_spec\.rb$"),
        ),
        stem_templates=("{stem}_test", "{stem}_spec"),
        count_regex=(re.compile(r"^it\s+['\"]"),),
    ),
    Language(
        name="rust",
        source_exts=(".rs",),
        test_patterns=(re.compile(r"^.*_test\.rs$"),),
        stem_templates=("{stem}_test",),
        count_startswith=("#[test",),
    ),
)


# --- Derived lookups (single source of truth for the rest of the package) ---

#: All file suffixes treated as source code, across every language.
SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    ext for lang in LANGUAGES for ext in lang.source_exts
)

#: Every test-filename regex, flattened — used by ``_is_test_file``.
TEST_FILE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    pat for lang in LANGUAGES for pat in lang.test_patterns
)

_LANG_BY_EXT: dict[str, Language] = {
    ext: lang for lang in LANGUAGES for ext in lang.source_exts
}


def language_for_ext(ext: str) -> Language | None:
    """Return the ``Language`` owning a file suffix (e.g. ``".ts"``), or None."""
    return _LANG_BY_EXT.get(ext)
