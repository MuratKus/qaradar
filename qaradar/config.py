"""Load and validate optional qaradar.toml configuration."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field


class WeightsConfig(BaseModel):
    churn: float = Field(default=0.35, ge=0.0, le=1.0)
    coverage: float = Field(default=0.35, ge=0.0, le=1.0)
    test_mapping: float = Field(default=0.30, ge=0.0, le=1.0)


class PathsConfig(BaseModel):
    coverage_file: str | None = None


class ExcludesConfig(BaseModel):
    patterns: list[str] = Field(default_factory=list)


class ScheduleConfig(BaseModel):
    """Criteria that govern when a scheduled/incremental re-run is warranted.

    Consumed by ``qaradar.schedule.should_run`` — the engine that powers
    ``qaradar should-run`` and the ``qaradar_should_run`` MCP tool.
    """

    # Re-run the full healthcheck at least this often.
    interval_days: float = Field(default=7.0, ge=0.0)
    # Re-run (diff-scoped) once this many source files have changed since the
    # last recorded run.
    min_changed_files: int = Field(default=25, ge=1)


class QaradarConfig(BaseModel):
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    excludes: ExcludesConfig = Field(default_factory=ExcludesConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)


def load_config(repo_path: str) -> QaradarConfig:
    """Load qaradar.toml from repo_path, returning defaults if absent."""
    config_file = Path(repo_path) / "qaradar.toml"
    if not config_file.exists():
        return QaradarConfig()

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(config_file, "rb") as f:
        data = tomllib.load(f)

    return QaradarConfig.model_validate(data)
