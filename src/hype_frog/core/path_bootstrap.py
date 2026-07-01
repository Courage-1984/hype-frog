"""Consistent ``src/`` layout bootstrap for scripts and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path

_MARKED = "_hype_frog_src_bootstrapped"


def package_root() -> Path:
    """Return the ``hype_frog`` package directory."""
    return Path(__file__).resolve().parent.parent


def src_root() -> Path:
    """Return the ``src/`` directory that contains the ``hype_frog`` package."""
    return package_root().parent


def repo_root() -> Path:
    """Return the repository root (parent of ``src/`` in development layouts)."""
    return src_root().parent


def bootstrap_src_path(*, anchor: Path | None = None) -> Path:
    """Ensure ``src/`` is importable when invoking scripts outside an installed package.

    No-op when ``hype_frog`` is already importable (``uv run``, PyInstaller, editable install).
    """
    if "hype_frog" in sys.modules:
        return src_root()

    src = src_root()
    if anchor is not None:
        candidate = Path(anchor).resolve()
        for parent in (candidate, *candidate.parents):
            maybe_src = parent / "src"
            if (maybe_src / "hype_frog").is_dir():
                src = maybe_src
                break

    src_str = str(src)
    if src.is_dir() and src_str not in sys.path:
        sys.path.insert(0, src_str)
    setattr(sys, _MARKED, True)
    return src


__all__ = ["bootstrap_src_path", "package_root", "repo_root", "src_root"]
