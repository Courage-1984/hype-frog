"""Unit tests for ``pipeline.assemble`` composite score helpers.

``Technical Health`` must be an independent delivery-signal score (status class,
indexability, canonical, mobile CWV, broken links, redirects) — NOT derived from
``SEO Health Score``. Regression for the export where rule-penalty saturation
drove SEO Health to 0 and dragged Technical Health to 0 on every URL.

Note on Rule #3 (Extraction State): these helpers consume already-enriched extra
rows; extraction-state gating happens upstream in ``rules.scoring``, so no
``Extraction State`` field is asserted here.
"""

from __future__ import annotations

from hype_frog.pipeline.assemble import (
    _technical_health_from_signals,
    compute_seo_technical_copy_scores,
)


def _clean_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Status Code": 200,
        "Indexability Reason": "Indexable",
        "Canonical Type": "self",
        "Mobile LCP (s)": 1.5,
        "Mobile CLS": 0.02,
        "Broken Internal Links Count": 0,
        "Redirect Chain Length": 0,
        "SEO Health Score": 0.0,
        "Word Count": 500,
    }
    row.update(overrides)
    return row


def test_technical_health_independent_of_seo_health_score() -> None:
    """A technically clean page scores 100 even when rule scoring floors at 0."""
    row = _clean_row(**{"SEO Health Score": 0.0})
    assert _technical_health_from_signals(row) == 100.0
    technical, _copy, _seo = compute_seo_technical_copy_scores(row)
    assert technical == 100.0


def test_technical_health_hard_zero_for_error_status() -> None:
    assert _technical_health_from_signals(_clean_row(**{"Status Code": 404})) == 0.0
    assert _technical_health_from_signals(_clean_row(**{"Status Code": 500})) == 0.0


def test_technical_health_penalises_each_delivery_signal() -> None:
    assert _technical_health_from_signals(_clean_row(**{"Status Code": 301})) == 85.0
    assert (
        _technical_health_from_signals(_clean_row(**{"Indexability Reason": "Noindex"}))
        == 75.0
    )
    assert (
        _technical_health_from_signals(
            _clean_row(**{"Canonical Type": "cross-canonical"})
        )
        == 85.0
    )
    assert (
        _technical_health_from_signals(_clean_row(**{"Mobile LCP (s)": 5.0})) == 85.0
    )
    assert _technical_health_from_signals(_clean_row(**{"Mobile CLS": 0.3})) == 90.0
    assert (
        _technical_health_from_signals(
            _clean_row(**{"Broken Internal Links Count": 2})
        )
        == 90.0
    )
    assert (
        _technical_health_from_signals(_clean_row(**{"Redirect Chain Length": 3}))
        == 95.0
    )


def test_technical_health_stacks_penalties_and_clamps_at_zero() -> None:
    row = _clean_row(
        **{
            "Status Code": 302,
            "Indexability Reason": "Noindex",
            "Canonical Type": "missing",
            "Mobile LCP (s)": 6.0,
            "Mobile CLS": 0.4,
            "Broken Internal Links Count": 5,
            "Redirect Chain Length": 4,
        }
    )
    # 100 - 15 - 25 - 15 - 15 - 10 - 10 - 5 = 5
    assert _technical_health_from_signals(row) == 5.0


def test_seo_score_blend_and_broken_page_clamp() -> None:
    row = _clean_row(**{"SEO Health Score": 80.0})
    technical, copy_score, seo = compute_seo_technical_copy_scores(row)
    assert seo == round(0.5 * 80.0 + 0.25 * technical + 0.25 * copy_score, 2)
    broken = _clean_row(**{"Status Code": 404, "SEO Health Score": 80.0})
    _tech, _copy, broken_seo = compute_seo_technical_copy_scores(broken)
    assert broken_seo <= 5.0
