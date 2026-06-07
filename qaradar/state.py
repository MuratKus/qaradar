"""Persistence for QA Radar — last-run marker + risk snapshot per repo.

State lives in ``<repo>/.qaradar/state.json`` (add ``.qaradar/`` to
``.gitignore``). It records the last analyzed commit, when it ran, and a
compact per-file risk snapshot. That's enough to:

  * decide whether a re-run is warranted (see ``qaradar.schedule``), and
  * report what changed since the last run (``compute_delta``).

Deliberately minimal — no run history, no external database. A "collection of
repos" is just many repos each with their own ``.qaradar/state.json``; the
orchestration that loops over them is left to the caller's infra.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from qaradar.models import HealthReport, RiskLevel

SCHEMA_VERSION = 1
STATE_DIR = ".qaradar"
STATE_FILE = "state.json"

# Ordering used to decide whether risk got worse or better between runs.
_RISK_ORDER = {
    RiskLevel.LOW.value: 0,
    RiskLevel.MEDIUM.value: 1,
    RiskLevel.HIGH.value: 2,
    RiskLevel.CRITICAL.value: 3,
}


@dataclass
class RunSnapshot:
    """A single recorded run."""

    analyzed_at: str           # ISO datetime
    head_sha: str
    summary: dict = field(default_factory=dict)
    # path -> {"risk_level": str, "risk_score": float}
    file_risks: dict = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass
class RiskChange:
    path: str
    from_level: str | None
    to_level: str | None
    from_score: float | None
    to_score: float | None


@dataclass
class DeltaReport:
    """What changed in risk between two runs."""

    new_risks: list[RiskChange] = field(default_factory=list)
    resolved_risks: list[RiskChange] = field(default_factory=list)
    worsened: list[RiskChange] = field(default_factory=list)
    improved: list[RiskChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "new_risks": [asdict(c) for c in self.new_risks],
            "resolved_risks": [asdict(c) for c in self.resolved_risks],
            "worsened": [asdict(c) for c in self.worsened],
            "improved": [asdict(c) for c in self.improved],
            "counts": {
                "new": len(self.new_risks),
                "resolved": len(self.resolved_risks),
                "worsened": len(self.worsened),
                "improved": len(self.improved),
            },
        }


def state_path(repo_path: str) -> Path:
    """Return the path to the state file for a repo (not guaranteed to exist)."""
    return Path(repo_path).resolve() / STATE_DIR / STATE_FILE


def load_state(repo_path: str) -> RunSnapshot | None:
    """Load the last recorded run for a repo, or None if there is none."""
    path = state_path(repo_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    last = data.get("last_run")
    if not isinstance(last, dict):
        return None
    return RunSnapshot(
        analyzed_at=last.get("analyzed_at", ""),
        head_sha=last.get("head_sha", ""),
        summary=last.get("summary", {}),
        file_risks=last.get("file_risks", {}),
        schema_version=last.get("schema_version", SCHEMA_VERSION),
    )


def snapshot_from_report(report: HealthReport, head_sha: str) -> RunSnapshot:
    """Build a compact snapshot from a HealthReport."""
    file_risks = {
        m.path: {"risk_level": m.risk_level.value, "risk_score": m.risk_score}
        for m in report.risky_modules
    }
    return RunSnapshot(
        analyzed_at=report.analyzed_at,
        head_sha=head_sha,
        summary=report.summary(),
        file_risks=file_risks,
    )


def save_run(repo_path: str, report: HealthReport, head_sha: str) -> RunSnapshot:
    """Persist a run snapshot to ``<repo>/.qaradar/state.json``."""
    snapshot = snapshot_from_report(report, head_sha)
    path = state_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "last_run": asdict(snapshot)}
    path.write_text(json.dumps(payload, indent=2))
    return snapshot


def compute_delta(
    previous: RunSnapshot | None,
    report: HealthReport,
    score_epsilon: float = 0.05,
) -> DeltaReport:
    """Diff a fresh report's risk landscape against a previous snapshot."""
    delta = DeltaReport()
    current = {
        m.path: (m.risk_level.value, m.risk_score) for m in report.risky_modules
    }
    prev = (
        {p: (v.get("risk_level"), v.get("risk_score")) for p, v in previous.file_risks.items()}
        if previous
        else {}
    )

    for path, (level, score) in current.items():
        if path not in prev:
            delta.new_risks.append(RiskChange(path, None, level, None, score))
            continue
        prev_level, prev_score = prev[path]
        rank_now = _RISK_ORDER.get(level, 0)
        rank_prev = _RISK_ORDER.get(prev_level, 0)
        if rank_now > rank_prev or (score - (prev_score or 0)) > score_epsilon:
            delta.worsened.append(RiskChange(path, prev_level, level, prev_score, score))
        elif rank_now < rank_prev or ((prev_score or 0) - score) > score_epsilon:
            delta.improved.append(RiskChange(path, prev_level, level, prev_score, score))

    for path, (prev_level, prev_score) in prev.items():
        if path not in current:
            delta.resolved_risks.append(RiskChange(path, prev_level, None, prev_score, None))

    return delta
