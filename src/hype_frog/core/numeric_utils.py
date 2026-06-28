"""Shared numeric helpers: safe float coercion, NaN/Inf guards, rounding."""

from __future__ import annotations

import math


def safe_float(value: object, default: float = 0.0) -> float:
    """Coerce any value to float, returning *default* for None, NaN, Inf, or non-numeric."""
    if value is None:
        return default
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


def round2(value: object, default: float = 0.0) -> float:
    """Return *value* rounded to 2 decimal places, or *default* for non-numeric inputs."""
    v = safe_float(value, default)
    return round(v, 2)


def round4(value: object, default: float = 0.0) -> float:
    """Return *value* rounded to 4 decimal places, or *default* for non-numeric inputs."""
    v = safe_float(value, default)
    return round(v, 4)


def clamp_pct(value: object, default: float = 0.0) -> float:
    """Coerce *value* to a float clamped to [0, 100], or *default* for invalid inputs."""
    return max(0.0, min(100.0, safe_float(value, default)))


def safe_int(value: object, default: int = 0) -> int:
    """Coerce any value to int, returning *default* for None, NaN, Inf, or non-numeric."""
    if value is None:
        return default
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(num) or math.isinf(num):
        return default
    return int(num)
