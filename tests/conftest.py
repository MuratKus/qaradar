"""Shared fixtures for QA Radar tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def python_app(tmp_path):
    """Copy the python_app fixture into a temp dir and return its path."""
    import shutil
    src = FIXTURES_DIR / "python_app"
    dest = tmp_path / "python_app"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def ts_app(tmp_path):
    """Copy the ts_app fixture into a temp dir and return its path."""
    import shutil
    src = FIXTURES_DIR / "ts_app"
    dest = tmp_path / "ts_app"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def go_app(tmp_path):
    """Copy the go_app fixture into a temp dir and return its path."""
    import shutil
    src = FIXTURES_DIR / "go_app"
    dest = tmp_path / "go_app"
    shutil.copytree(src, dest)
    return dest


def _copy_fixture(name, tmp_path):
    import shutil
    dest = tmp_path / name
    shutil.copytree(FIXTURES_DIR / name, dest)
    return dest


@pytest.fixture
def dart_app(tmp_path):
    """Flutter/Dart fixture: lib/ source, test/ tests, lcov coverage."""
    return _copy_fixture("dart_app", tmp_path)


@pytest.fixture
def swift_app(tmp_path):
    """Swift fixture: Sources/ + Tests/ with XCTest methods."""
    return _copy_fixture("swift_app", tmp_path)


@pytest.fixture
def kotlin_app(tmp_path):
    """Kotlin fixture: src/main + src/test with @Test methods."""
    return _copy_fixture("kotlin_app", tmp_path)


@pytest.fixture
def objc_app(tmp_path):
    """Objective-C fixture: Sources/ + Tests/ with XCTest methods."""
    return _copy_fixture("objc_app", tmp_path)


@pytest.fixture
def rn_app(tmp_path):
    """React Native fixture: __tests__/ with dash-suffix (Foo-test.ts) convention."""
    return _copy_fixture("rn_app", tmp_path)


@pytest.fixture
def ts_monorepo(tmp_path):
    """TS monorepo fixture: packages/*/src + Istanbul coverage-final.json."""
    return _copy_fixture("ts_monorepo", tmp_path)
