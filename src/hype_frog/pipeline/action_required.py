from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def _coerce_score(value: object) -> float | None:
    """Parse a numeric score from row data; return None if absent or unusable."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            out = float(stripped)
        except ValueError:
            return None
    else:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def determine_action_required(row_data: Mapping[str, Any]) -> str:
    """Return the Content Hub ``Action Required`` label from Copy and SEO scores.

    Values are chosen so Excel conditional formatting can branch on exact literals:
    ``Needs Copy`` (copy readiness), ``Needs Optimization`` (SEO readiness), or
    ``Complete`` when both score thresholds are met.
    """
    copy_score = _coerce_score(row_data.get("Copy Score"))
    seo_score = _coerce_score(row_data.get("SEO Score"))

    if copy_score is None or copy_score < 80.0:
        return "Needs Copy"
    if seo_score is None or seo_score < 50.0:
        return "Needs Optimization"
    return "Complete"


__all__ = ["determine_action_required"]
