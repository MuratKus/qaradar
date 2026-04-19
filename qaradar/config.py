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


class QaradarConfig(BaseModel):
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    excludes: ExcludesConfig = Field(default_factory=ExcludesConfig)


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
