"""YAML config loader and runtime override behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from hype_frog import config_defaults
from hype_frog.config_loader import apply_user_config, load_user_config


@pytest.fixture(autouse=True)
def _clear_runtime_overrides() -> None:
    config_defaults._RUNTIME_OVERRIDES.clear()
    yield
    config_defaults._RUNTIME_OVERRIDES.clear()


def test_load_user_config_missing_returns_empty(tmp_path: Path) -> None:
    assert load_user_config(tmp_path) == {}


def test_apply_user_config_applies_known_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "hype_frog.config.yaml"
    config_path.write_text(
        "THIN_CONTENT_WORD_THRESHOLD: 300\nPSI_BASE_DELAY_SECONDS: 3.0\n",
        encoding="utf-8",
    )
    apply_user_config(tmp_path)
    assert config_defaults.get_thin_content_word_threshold() == 300
    assert config_defaults.get_psi_base_delay_seconds() == 3.0


def test_apply_runtime_override_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown config key"):
        config_defaults.apply_runtime_override("NOT_A_REAL_KEY", 1)
