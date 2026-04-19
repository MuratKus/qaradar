"""Tests for qaradar.config — load_config and QaradarConfig."""

import pytest

from qaradar.config import QaradarConfig, load_config


def test_load_config_returns_defaults_when_no_file(tmp_path):
    config = load_config(str(tmp_path))
    assert config.weights.churn == pytest.approx(0.35)
    assert config.weights.coverage == pytest.approx(0.35)
    assert config.weights.test_mapping == pytest.approx(0.30)
    assert config.paths.coverage_file is None
    assert config.excludes.patterns == []


def test_load_config_reads_weights_from_toml(tmp_path):
    (tmp_path / "qaradar.toml").write_text(
        "[weights]\nchurn = 0.5\ncoverage = 0.3\ntest_mapping = 0.2\n"
    )
    config = load_config(str(tmp_path))
    assert config.weights.churn == pytest.approx(0.5)
    assert config.weights.coverage == pytest.approx(0.3)
    assert config.weights.test_mapping == pytest.approx(0.2)


def test_load_config_reads_coverage_path(tmp_path):
    (tmp_path / "qaradar.toml").write_text(
        '[paths]\ncoverage_file = "build/coverage.xml"\n'
    )
    config = load_config(str(tmp_path))
    assert config.paths.coverage_file == "build/coverage.xml"


def test_load_config_reads_excludes(tmp_path):
    (tmp_path / "qaradar.toml").write_text(
        '[excludes]\npatterns = ["vendor/**", "generated/**"]\n'
    )
    config = load_config(str(tmp_path))
    assert config.excludes.patterns == ["vendor/**", "generated/**"]


def test_load_config_partial_weights_use_defaults_for_rest(tmp_path):
    (tmp_path / "qaradar.toml").write_text("[weights]\nchurn = 0.6\n")
    config = load_config(str(tmp_path))
    assert config.weights.churn == pytest.approx(0.6)
    assert config.weights.coverage == pytest.approx(0.35)
    assert config.weights.test_mapping == pytest.approx(0.30)


def test_load_config_rejects_weight_above_one(tmp_path):
    (tmp_path / "qaradar.toml").write_text("[weights]\nchurn = 1.5\n")
    with pytest.raises(Exception):
        load_config(str(tmp_path))


def test_load_config_rejects_negative_weight(tmp_path):
    (tmp_path / "qaradar.toml").write_text("[weights]\ncoverage = -0.1\n")
    with pytest.raises(Exception):
        load_config(str(tmp_path))


def test_qaradar_config_default_instance():
    config = QaradarConfig()
    assert config.weights.churn + config.weights.coverage + config.weights.test_mapping == pytest.approx(1.0)
