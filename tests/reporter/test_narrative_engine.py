"""Strategic narrative tone gates (triage vs optimization vs dominance)."""

from __future__ import annotations

from hype_frog.core.models import MainRowPayload
from hype_frog.reporter.narrative_engine import NarrativeEngine, average_seo_score_pct


def test_strategic_narrative_healthy_site_not_triage() -> None:
    rows = [
        MainRowPayload.model_validate({"values": {"URL": "https://a.test/x", "SEO Health Score": 72.0}})
    ]
    avg = average_seo_score_pct(rows)
    text = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=avg,
        critical_url_count=0,
    )
    assert "Critical technical debt" not in text
    assert "solid" in text.lower() or "pagespeed" in text.lower()


def test_strategic_narrative_triage_only_when_critical_mass_or_sub_50_seo() -> None:
    out_high_crit = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=80.0,
        critical_url_count=6,
    )
    assert "Critical technical debt" in out_high_crit

    out_low_seo = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=45.0,
        critical_url_count=0,
    )
    assert "Critical technical debt" in out_low_seo


def test_strategic_narrative_dominance_above_75() -> None:
    text = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=76.0,
        critical_url_count=0,
    )
    assert "elite" in text.lower()


def test_strategic_narrative_seventy_five_is_dominance() -> None:
    """Threshold is optimization when strictly below 75%; 75% and above is elite."""
    text = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=75.0,
        critical_url_count=0,
    )
    assert "elite" in text.lower()


def test_strategic_narrative_seventy_four_is_optimization() -> None:
    text = NarrativeEngine.build_strategic_narrative(
        total_urls=10,
        avg_seo_score_pct=74.0,
        critical_url_count=0,
    )
    assert "solid" in text.lower()
