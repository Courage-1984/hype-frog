"""Executive ROI math for the Hype Frog reporter (Sprint 6).

These helpers correlate live traffic (GSC clicks) with the
answer-engine readiness (Semantic AEO Score) and field web vitals
(Field LCP) already produced by the crawler / extractor stack to
power the Content Optimisation Hub's executive priority columns and
the Dashboard's aggregated traffic-lift metric.

All functions are deliberately ``None``-safe: any missing or
malformed input collapses to a neutral ``0.0`` (numeric metrics) or
``"Standard"`` (priority flag) rather than raising — see the
``Graceful Math`` rule in the Sprint 6 brief.
"""

from __future__ import annotations

import math
from typing import Final, TypedDict

# Tunable constants. Kept module-level so they can be referenced from
# tests and tooltips without importing pandas / openpyxl.
AEO_MAX_LIFT_FACTOR: Final[float] = 0.25
"""Maximum proportion of current traffic recoverable by closing the AEO gap."""

CRITICAL_CLICKS_THRESHOLD: Final[int] = 500
"""Minimum monthly clicks for a page to qualify as a high-traffic asset."""

CRITICAL_AEO_THRESHOLD: Final[float] = 50.0
"""Below this Semantic AEO Score, a high-traffic page is at-risk of cannibalisation."""

CRITICAL_LCP_MS_THRESHOLD: Final[float] = 2500.0
"""Field LCP above this (ms) is the Core Web Vitals 'poor' boundary."""


class ExecutiveROIResult(TypedDict):
    """Return shape of :func:`calculate_executive_roi`."""

    potential_traffic_lift: int
    aeo_visibility_gain: float
    instant_priority: str


def _safe_float(value: object) -> float | None:
    """Return ``value`` as a finite ``float``; ``None`` for malformed inputs."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            value = float(stripped)
        except (TypeError, ValueError):
            return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _safe_clicks(value: object) -> int:
    """Coerce a clicks-like value to a non-negative ``int`` (``0`` on failure)."""
    numeric = _safe_float(value)
    if numeric is None or numeric < 0:
        return 0
    return int(numeric)


def calculate_executive_roi(
    clicks: int | None,
    aeo_score: float | None,
    lcp_ms: float | None,
) -> ExecutiveROIResult:
    """Correlate traffic, semantic readiness, and field LCP into ROI signals.

    Args:
        clicks: Monthly Google Search Console clicks for the URL. ``None``
            or non-numeric inputs are treated as ``0``.
        aeo_score: Semantic AEO Score in the ``[0, 100]`` range produced
            by ``hype_frog.extractors.semantic_engine``. ``None`` collapses
            visibility headroom and traffic lift to ``0.0`` because we
            cannot estimate the gap without a baseline.
        lcp_ms: Field Largest Contentful Paint in milliseconds (from the
            Sprint 2 ``PerformanceObserver`` capture). ``None`` is treated
            as "unknown" for the priority check (does NOT trigger
            CRITICAL on its own).

    Returns:
        A :class:`ExecutiveROIResult` with:
        * ``potential_traffic_lift`` — clicks captured back if the AEO
          gap closes, capped at ``AEO_MAX_LIFT_FACTOR`` (25%) of current
          clicks. Always ``>= 0``.
        * ``aeo_visibility_gain`` — semantic headroom on the
          ``[0, 100]`` scale (``100 - aeo_score``). ``0.0`` when the
          score is missing.
        * ``instant_priority`` — ``"CRITICAL"`` when traffic exceeds
          :data:`CRITICAL_CLICKS_THRESHOLD` AND (``aeo_score`` is below
          :data:`CRITICAL_AEO_THRESHOLD` OR ``lcp_ms`` exceeds
          :data:`CRITICAL_LCP_MS_THRESHOLD`). ``"Standard"`` otherwise.
    """
    safe_clicks = _safe_clicks(clicks)
    if safe_clicks <= 0:
        # Zero-click rule: no traffic baseline means zero lift, always.
        potential_lift = 0
        safe_aeo = _safe_float(aeo_score)
        visibility_gain = (
            round(100.0 - max(0.0, min(100.0, safe_aeo)), 2)
            if safe_aeo is not None
            else 0.0
        )
    else:
        safe_aeo = _safe_float(aeo_score)
        if safe_aeo is None:
            visibility_gain = 0.0
            potential_lift = 0
        else:
            clamped_aeo = max(0.0, min(100.0, safe_aeo))
            visibility_gain = round(100.0 - clamped_aeo, 2)
            potential_lift = int(
                round(safe_clicks * (visibility_gain / 100.0) * AEO_MAX_LIFT_FACTOR)
            )

    safe_lcp = _safe_float(lcp_ms)

    aeo_at_risk = safe_aeo is not None and safe_aeo < CRITICAL_AEO_THRESHOLD
    lcp_at_risk = safe_lcp is not None and safe_lcp > CRITICAL_LCP_MS_THRESHOLD
    is_critical = (
        safe_clicks > CRITICAL_CLICKS_THRESHOLD and (aeo_at_risk or lcp_at_risk)
    )

    return ExecutiveROIResult(
        potential_traffic_lift=potential_lift,
        aeo_visibility_gain=visibility_gain,
        instant_priority="CRITICAL" if is_critical else "Standard",
    )


__all__ = [
    "AEO_MAX_LIFT_FACTOR",
    "CRITICAL_AEO_THRESHOLD",
    "CRITICAL_CLICKS_THRESHOLD",
    "CRITICAL_LCP_MS_THRESHOLD",
    "ExecutiveROIResult",
    "calculate_executive_roi",
]
