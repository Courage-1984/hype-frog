"""Unit tests for :mod:`hype_frog.core.scoring` — Sprint 6 ROI math.

Covers the executive ROI helper that powers the Content Optimisation Hub:

* Mathematical correctness of ``potential_traffic_lift`` and
  ``aeo_visibility_gain`` for the standard happy paths and the explicit
  25 % traffic-lift cap.
* The ``Instant Priority`` truth table (``CRITICAL`` vs ``Standard``)
  over the ``clicks × aeo_score × lcp_ms`` matrix, including each
  documented threshold boundary.
* Failsafe coercion: ``None``, negatives, junk strings, booleans,
  ``NaN``/``inf`` must all collapse to neutral defaults rather than
  raising — guarded by ``_safe_float`` / ``_safe_clicks``.

Note on Rule #3 (Extraction State): these tests deliberately do not
construct any crawl row payloads. ``calculate_executive_roi`` consumes
scalar metrics, so no ``Extraction State`` field is in scope here.
This is **NOT** the same module as ``tests/rules/test_scoring.py``,
which exercises ``hype_frog.rules.score_url_health``.
"""

from __future__ import annotations

import math

from hype_frog.core.scoring import (
    AEO_MAX_LIFT_FACTOR,
    CRITICAL_AEO_THRESHOLD,
    CRITICAL_CLICKS_THRESHOLD,
    CRITICAL_LCP_MS_THRESHOLD,
    calculate_executive_roi,
)


# ---------------------------------------------------------------------------
# Standard case — math correctness
# ---------------------------------------------------------------------------


def test_standard_case_healthy_high_traffic_page() -> None:
    """1000 clicks + AEO 80 + LCP 2000 → +50 lift, 20 % headroom, Standard."""
    result = calculate_executive_roi(clicks=1000, aeo_score=80.0, lcp_ms=2000.0)
    # 1000 * (20 / 100) * 0.25 = 50.0
    assert result["potential_traffic_lift"] == 50.0
    assert result["aeo_visibility_gain"] == 20.0
    assert result["instant_priority"] == "Standard"


def test_standard_case_low_aeo_amplifies_lift_within_25pc_cap() -> None:
    """AEO 0 → full headroom, lift hits the explicit 25 % traffic cap."""
    result = calculate_executive_roi(clicks=1000, aeo_score=0.0, lcp_ms=2000.0)
    # 1000 * (100 / 100) * 0.25 = 250.0  (AEO_MAX_LIFT_FACTOR enforced)
    assert result["potential_traffic_lift"] == 250.0
    assert result["aeo_visibility_gain"] == 100.0


def test_aeo_above_100_clamps_to_100_yielding_zero_headroom() -> None:
    result = calculate_executive_roi(clicks=1000, aeo_score=120.0, lcp_ms=2000.0)
    assert result["aeo_visibility_gain"] == 0.0
    assert result["potential_traffic_lift"] == 0.0


def test_aeo_below_zero_clamps_to_zero_yielding_full_headroom() -> None:
    result = calculate_executive_roi(clicks=200, aeo_score=-25.0, lcp_ms=2000.0)
    # Clamped to 0 → headroom 100 → lift = 200 * 1.0 * 0.25 = 50.0
    assert result["aeo_visibility_gain"] == 100.0
    assert result["potential_traffic_lift"] == 50.0


def test_aeo_max_lift_factor_constant_is_25_percent() -> None:
    """Guards against silent re-tuning of the executive headroom cap."""
    assert AEO_MAX_LIFT_FACTOR == 0.25


def test_lift_is_always_non_negative_and_finite() -> None:
    result = calculate_executive_roi(clicks=10, aeo_score=33.3, lcp_ms=1500.0)
    assert result["potential_traffic_lift"] >= 0.0
    assert math.isfinite(result["potential_traffic_lift"])
    assert math.isfinite(result["aeo_visibility_gain"])


# ---------------------------------------------------------------------------
# Priority logic — CRITICAL truth table
# ---------------------------------------------------------------------------


def test_critical_when_high_traffic_and_low_aeo() -> None:
    result = calculate_executive_roi(clicks=600, aeo_score=30.0, lcp_ms=2000.0)
    assert result["instant_priority"] == "CRITICAL"


def test_critical_when_high_traffic_and_bad_lcp() -> None:
    result = calculate_executive_roi(clicks=600, aeo_score=80.0, lcp_ms=3000.0)
    assert result["instant_priority"] == "CRITICAL"


def test_critical_when_both_signals_at_risk() -> None:
    result = calculate_executive_roi(clicks=600, aeo_score=20.0, lcp_ms=4000.0)
    assert result["instant_priority"] == "CRITICAL"


def test_standard_when_traffic_below_threshold_even_if_signals_bad() -> None:
    """Low-traffic pages never escalate, regardless of AEO/LCP."""
    result = calculate_executive_roi(clicks=100, aeo_score=10.0, lcp_ms=9999.0)
    assert result["instant_priority"] == "Standard"


def test_standard_when_traffic_at_exact_threshold() -> None:
    """Threshold is strict ``>`` 500 — equality stays Standard."""
    result = calculate_executive_roi(
        clicks=CRITICAL_CLICKS_THRESHOLD,
        aeo_score=10.0,
        lcp_ms=9999.0,
    )
    assert result["instant_priority"] == "Standard"


def test_standard_when_aeo_at_exact_threshold_and_lcp_clean() -> None:
    """AEO == 50 is NOT 'below 50'; clean LCP keeps it Standard."""
    result = calculate_executive_roi(
        clicks=600,
        aeo_score=CRITICAL_AEO_THRESHOLD,
        lcp_ms=2000.0,
    )
    assert result["instant_priority"] == "Standard"


def test_standard_when_lcp_at_exact_threshold_and_aeo_clean() -> None:
    """LCP == 2500 is NOT 'above 2500'; healthy AEO keeps it Standard."""
    result = calculate_executive_roi(
        clicks=600,
        aeo_score=80.0,
        lcp_ms=CRITICAL_LCP_MS_THRESHOLD,
    )
    assert result["instant_priority"] == "Standard"


def test_standard_when_both_signals_healthy() -> None:
    result = calculate_executive_roi(clicks=10_000, aeo_score=90.0, lcp_ms=1500.0)
    assert result["instant_priority"] == "Standard"


def test_none_lcp_alone_does_not_trigger_critical() -> None:
    """Missing field LCP must not escalate priority on its own."""
    result = calculate_executive_roi(clicks=600, aeo_score=80.0, lcp_ms=None)
    assert result["instant_priority"] == "Standard"


def test_none_aeo_blanks_aeo_branch_but_bad_lcp_still_escalates() -> None:
    """Missing AEO drops the AEO-at-risk leg; LCP can still trigger CRITICAL."""
    clean_lcp = calculate_executive_roi(clicks=600, aeo_score=None, lcp_ms=2000.0)
    assert clean_lcp["instant_priority"] == "Standard"

    bad_lcp = calculate_executive_roi(clicks=600, aeo_score=None, lcp_ms=3000.0)
    assert bad_lcp["instant_priority"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Failsafe — None / negative / junk / NaN / Inf / bool / numeric strings
# ---------------------------------------------------------------------------


def test_all_none_returns_neutral_zeros_and_standard() -> None:
    result = calculate_executive_roi(clicks=None, aeo_score=None, lcp_ms=None)
    assert result["potential_traffic_lift"] == 0.0
    assert result["aeo_visibility_gain"] == 0.0
    assert result["instant_priority"] == "Standard"


def test_negative_clicks_clamped_to_zero_lift() -> None:
    result = calculate_executive_roi(clicks=-100, aeo_score=20.0, lcp_ms=2000.0)
    assert result["potential_traffic_lift"] == 0.0
    # Headroom is independent of clicks and stays correct.
    assert result["aeo_visibility_gain"] == 80.0


def test_junk_string_inputs_return_neutral_defaults() -> None:
    result = calculate_executive_roi(
        clicks="not-a-number",  # type: ignore[arg-type]
        aeo_score="garbage",  # type: ignore[arg-type]
        lcp_ms="oops",  # type: ignore[arg-type]
    )
    assert result["potential_traffic_lift"] == 0.0
    assert result["aeo_visibility_gain"] == 0.0
    assert result["instant_priority"] == "Standard"


def test_boolean_inputs_treated_as_invalid_not_as_one_or_zero() -> None:
    """Bool subclasses int in Python; the helper must reject it explicitly."""
    result = calculate_executive_roi(
        clicks=True,  # type: ignore[arg-type]
        aeo_score=True,  # type: ignore[arg-type]
        lcp_ms=False,  # type: ignore[arg-type]
    )
    assert result["potential_traffic_lift"] == 0.0
    assert result["aeo_visibility_gain"] == 0.0
    assert result["instant_priority"] == "Standard"


def test_nan_and_inf_inputs_collapse_to_neutral() -> None:
    result = calculate_executive_roi(
        clicks=float("inf"),
        aeo_score=float("nan"),
        lcp_ms=float("inf"),
    )
    assert result["potential_traffic_lift"] == 0.0
    assert result["aeo_visibility_gain"] == 0.0
    assert result["instant_priority"] == "Standard"


def test_numeric_strings_are_parsed() -> None:
    """``"1000"`` is a legitimate metric serialisation — must be honoured."""
    result = calculate_executive_roi(
        clicks="1000",  # type: ignore[arg-type]
        aeo_score="80.0",  # type: ignore[arg-type]
        lcp_ms="2000",  # type: ignore[arg-type]
    )
    assert result["potential_traffic_lift"] == 50.0
    assert result["aeo_visibility_gain"] == 20.0


def test_zero_clicks_yields_zero_lift_but_preserves_visibility_gain() -> None:
    result = calculate_executive_roi(clicks=0, aeo_score=40.0, lcp_ms=2000.0)
    assert result["potential_traffic_lift"] == 0.0
    assert result["aeo_visibility_gain"] == 60.0
    # 0 clicks cannot exceed CRITICAL_CLICKS_THRESHOLD → never CRITICAL
    assert result["instant_priority"] == "Standard"


def test_result_is_typed_dict_with_expected_keys() -> None:
    result = calculate_executive_roi(clicks=10, aeo_score=10.0, lcp_ms=10.0)
    assert set(result.keys()) == {
        "potential_traffic_lift",
        "aeo_visibility_gain",
        "instant_priority",
    }
    assert result["instant_priority"] in {"CRITICAL", "Standard"}
