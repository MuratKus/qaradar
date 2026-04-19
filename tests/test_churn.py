"""Tests for analyzers/churn.py — using monkeypatched git output."""

from unittest.mock import patch

import pytest

from qaradar.analyzers.churn import analyze_churn


SAMPLE_GIT_LOG = """\
COMMIT|abc123|2026-04-10T10:00:00+00:00|Alice
10\t2\tsrc/calculator.py
5\t1\tsrc/utils.py
COMMIT|def456|2026-04-01T10:00:00+00:00|Bob
3\t0\tsrc/calculator.py
-\t-\tbinary.png
"""


def test_analyze_churn_parses_output(tmp_path):
    # Create a fake .git dir so the repo check passes
    (tmp_path / ".git").mkdir()
    # Create the source files so they "exist"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculator.py").touch()
    (tmp_path / "src" / "utils.py").touch()

    with patch("qaradar.analyzers.churn._git", return_value=SAMPLE_GIT_LOG):
        results = analyze_churn(str(tmp_path), days=90)

    by_path = {r.path: r for r in results}

    assert "src/calculator.py" in by_path
    calc = by_path["src/calculator.py"]
    assert calc.commit_count == 2
    assert calc.lines_added == 13
    assert calc.lines_deleted == 2
    assert calc.unique_authors == 2

    assert "src/utils.py" in by_path
    assert by_path["src/utils.py"].commit_count == 1

    # Binary file should be skipped
    assert not any("binary" in p for p in by_path)


def test_analyze_churn_sorted_descending(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculator.py").touch()
    (tmp_path / "src" / "utils.py").touch()

    with patch("qaradar.analyzers.churn._git", return_value=SAMPLE_GIT_LOG):
        results = analyze_churn(str(tmp_path))

    assert results[0].commit_count >= results[-1].commit_count


def test_analyze_churn_skips_missing_files(tmp_path):
    (tmp_path / ".git").mkdir()
    # Only create one of the two files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculator.py").touch()
    # src/utils.py intentionally missing

    with patch("qaradar.analyzers.churn._git", return_value=SAMPLE_GIT_LOG):
        results = analyze_churn(str(tmp_path))

    paths = [r.path for r in results]
    assert "src/calculator.py" in paths
    assert "src/utils.py" not in paths


def test_analyze_churn_empty_git_output(tmp_path):
    (tmp_path / ".git").mkdir()

    with patch("qaradar.analyzers.churn._git", return_value=""):
        results = analyze_churn(str(tmp_path))

    assert results == []


def test_analyze_churn_requires_git_repo(tmp_path):
    with pytest.raises(ValueError, match="Not a git repository"):
        analyze_churn(str(tmp_path))
