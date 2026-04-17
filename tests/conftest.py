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
