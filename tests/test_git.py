"""Tests for qaradar/git.py — resolve_base_ref, changed_files, fork_point_sha."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from qaradar.git import changed_files, fork_point_sha, resolve_base_ref


# --- resolve_base_ref ---

def test_resolve_base_ref_returns_explicit(tmp_path):
    result = resolve_base_ref(tmp_path, "my-branch")
    assert result == "my-branch"


def test_resolve_base_ref_uses_github_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "release/2.0")
    result = resolve_base_ref(tmp_path, None)
    assert result == "origin/release/2.0"


def test_resolve_base_ref_explicit_beats_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "release/2.0")
    result = resolve_base_ref(tmp_path, "explicit-ref")
    assert result == "explicit-ref"


def test_resolve_base_ref_falls_back_to_main(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    def fake_git(repo, *args):
        if args == ("rev-parse", "--verify", "origin/HEAD"):
            raise RuntimeError("not found")
        if args == ("rev-parse", "--verify", "main"):
            return "abc123\n"
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = resolve_base_ref(tmp_path, None)
    assert result == "main"


def test_resolve_base_ref_falls_back_to_master(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    def fake_git(repo, *args):
        if args[0] == "rev-parse":
            ref = args[-1]
            if ref == "master":
                return "abc123\n"
            raise RuntimeError("not found")
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = resolve_base_ref(tmp_path, None)
    assert result == "master"


def test_resolve_base_ref_raises_when_nothing_resolves(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    with patch("qaradar.git._git", side_effect=RuntimeError("not found")):
        with pytest.raises(ValueError, match="Could not resolve base ref"):
            resolve_base_ref(tmp_path, None)


# --- changed_files ---

def test_changed_files_returns_posix_paths(tmp_path):
    def fake_git(repo, *args):
        if args[0] == "merge-base":
            return "fork123\n"
        if args[0] == "diff":
            return "src/foo.py\nsrc/bar/baz.py\n"
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = changed_files(tmp_path, "main")

    assert result == ["src/foo.py", "src/bar/baz.py"]


def test_changed_files_empty_diff_returns_empty_list(tmp_path):
    def fake_git(repo, *args):
        if args[0] == "merge-base":
            return "fork123\n"
        if args[0] == "diff":
            return ""
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = changed_files(tmp_path, "main")

    assert result == []


def test_changed_files_falls_back_when_merge_base_fails(tmp_path):
    def fake_git(repo, *args):
        if args[0] == "merge-base":
            raise RuntimeError("unrelated histories")
        if args[0] == "diff":
            # fallback uses base directly
            assert args[2] == "main..HEAD"
            return "src/fallback.py\n"
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = changed_files(tmp_path, "main")

    assert result == ["src/fallback.py"]


def test_changed_files_strips_blank_lines(tmp_path):
    def fake_git(repo, *args):
        if args[0] == "merge-base":
            return "fork123\n"
        if args[0] == "diff":
            return "\nsrc/a.py\n\nsrc/b.py\n\n"
        raise RuntimeError(f"unexpected: {args}")

    with patch("qaradar.git._git", side_effect=fake_git):
        result = changed_files(tmp_path, "main")

    assert result == ["src/a.py", "src/b.py"]


# --- fork_point_sha ---

def test_fork_point_sha_returns_merge_base(tmp_path):
    with patch("qaradar.git._git", return_value="deadbeef\n"):
        result = fork_point_sha(tmp_path, "main")
    assert result == "deadbeef"


def test_fork_point_sha_falls_back_to_rev_parse(tmp_path):
    call_count = [0]

    def fake_git(repo, *args):
        call_count[0] += 1
        if args[0] == "merge-base":
            raise RuntimeError("fail")
        return "fallbacksha\n"

    with patch("qaradar.git._git", side_effect=fake_git):
        result = fork_point_sha(tmp_path, "main")

    assert result == "fallbacksha"
    assert call_count[0] == 2
