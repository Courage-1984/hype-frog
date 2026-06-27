from __future__ import annotations

from hype_frog.pipeline.graph_engine import (
    compute_internal_link_intelligence as _compute_internal_link_intelligence,
)


def compute_internal_link_intelligence(
    extra_rows: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    return _compute_internal_link_intelligence(extra_rows)


def value_or_default(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
