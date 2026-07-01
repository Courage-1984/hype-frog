"""Cross-platform path helpers (prefer over ``os.path`` in runtime code)."""

from __future__ import annotations

from pathlib import Path


def as_resolved_path(value: str | Path) -> Path:
    """Expand user home and return an absolute path."""
    return Path(value).expanduser().resolve()


def path_exists(value: str | Path | None) -> bool:
    """Return True when ``value`` points at an existing filesystem entry."""
    if value is None:
        return False
    if isinstance(value, Path):
        target = value
    else:
        cleaned = str(value).strip()
        if not cleaned:
            return False
        target = Path(cleaned).expanduser()
    try:
        return target.exists()
    except OSError:
        return False


def ensure_parent_dir(value: str | Path) -> Path:
    """Create the parent directory for a file path when missing."""
    path = Path(value).expanduser()
    parent = path.parent
    if str(parent) not in {".", ""}:
        parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


__all__ = ["as_resolved_path", "ensure_parent_dir", "path_exists"]
