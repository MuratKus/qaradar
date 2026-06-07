"""Tests for qaradar/state.py — snapshot persistence + risk delta."""

from qaradar.models import HealthReport, ModuleRisk, RiskLevel
from qaradar.state import (
    compute_delta,
    load_state,
    save_run,
    snapshot_from_report,
    state_path,
)


def _report(risks, analyzed_at="2026-06-01T00:00:00+00:00"):
    modules = [
        ModuleRisk(
            path=path,
            risk_level=level,
            risk_score=score,
            churn_score=0.0,
            coverage_score=0.0,
            test_mapping_score=0.0,
        )
        for path, level, score in risks
    ]
    return HealthReport(
        repo_path=".",
        analyzed_at=analyzed_at,
        total_source_files=10,
        total_test_files=5,
        test_to_source_ratio=0.5,
        risky_modules=modules,
    )


def test_save_and_load_roundtrip(tmp_path):
    report = _report([("src/a.py", RiskLevel.HIGH, 0.6)])
    assert load_state(str(tmp_path)) is None

    save_run(str(tmp_path), report, head_sha="abc123")
    assert state_path(str(tmp_path)).exists()

    loaded = load_state(str(tmp_path))
    assert loaded is not None
    assert loaded.head_sha == "abc123"
    assert "src/a.py" in loaded.file_risks
    assert loaded.file_risks["src/a.py"]["risk_level"] == "high"


def test_load_state_handles_corrupt_file(tmp_path):
    p = state_path(str(tmp_path))
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert load_state(str(tmp_path)) is None


def test_snapshot_from_report():
    report = _report([("x.py", RiskLevel.CRITICAL, 0.9)])
    snap = snapshot_from_report(report, "sha1")
    assert snap.head_sha == "sha1"
    assert snap.file_risks["x.py"]["risk_score"] == 0.9


def test_delta_new_and_resolved():
    prev_report = _report([("keep.py", RiskLevel.HIGH, 0.6), ("gone.py", RiskLevel.HIGH, 0.6)])
    prev = snapshot_from_report(prev_report, "sha0")

    curr = _report([("keep.py", RiskLevel.HIGH, 0.6), ("fresh.py", RiskLevel.HIGH, 0.6)])
    delta = compute_delta(prev, curr)

    assert [c.path for c in delta.new_risks] == ["fresh.py"]
    assert [c.path for c in delta.resolved_risks] == ["gone.py"]


def test_delta_worsened_and_improved():
    prev = snapshot_from_report(
        _report([("up.py", RiskLevel.MEDIUM, 0.4), ("down.py", RiskLevel.CRITICAL, 0.9)]),
        "sha0",
    )
    curr = _report([("up.py", RiskLevel.CRITICAL, 0.8), ("down.py", RiskLevel.MEDIUM, 0.4)])
    delta = compute_delta(prev, curr)

    assert [c.path for c in delta.worsened] == ["up.py"]
    assert [c.path for c in delta.improved] == ["down.py"]


def test_delta_no_previous_is_all_new():
    curr = _report([("a.py", RiskLevel.HIGH, 0.6)])
    delta = compute_delta(None, curr)
    assert len(delta.new_risks) == 1
    assert delta.resolved_risks == []
