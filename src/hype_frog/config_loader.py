"""Load optional ``hype_frog.config.yaml`` overrides from the project root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hype_frog.core import get_logger

from . import config_defaults as defaults

logger = get_logger(__name__)

_CONFIG_FILENAMES: tuple[str, ...] = ("hype_frog.config.yaml", "hype_frog.config.yml")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        logger.warning(
            "Found %s but PyYAML is not installed; install with `uv sync` to apply YAML overrides.",
            path.name,
        )
        return {}

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return {}
    except Exception as exc:
        logger.warning("Could not parse %s: %s", path, exc)
        return {}

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        logger.warning("%s must contain a mapping at the top level.", path.name)
        return {}
    return raw


def load_user_config(project_root: Path) -> dict[str, Any]:
    """Return merged user overrides from the first present config file."""
    for name in _CONFIG_FILENAMES:
        path = project_root / name
        if path.is_file():
            return _read_yaml(path)
    return {}


def apply_user_config(project_root: Path) -> None:
    """Apply recognised keys from ``hype_frog.config.yaml`` into runtime overrides."""
    data = load_user_config(project_root)
    if not data:
        return

    applied: list[str] = []
    for key, value in data.items():
        if key not in defaults.USER_CONFIG_KEYS:
            logger.warning("Ignoring unknown config key in hype_frog.config.yaml: %s", key)
            continue
        defaults.apply_runtime_override(key, value)
        applied.append(key)

    if applied:
        logger.info(
            "Applied %s override(s) from hype_frog.config.yaml: %s",
            len(applied),
            ", ".join(sorted(applied)),
        )
