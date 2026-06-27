"""Strategic narrative tone gates (triage vs optimization vs dominance)."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.reporter.narrative_engine import NarrativeEngine, average_seo_score_pct


def _extra(**values: object) -> ExtraRowPayload:
    payload = ExtraRowPayload.model_validate({})
    payload.values.update(values)
    return payload


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


def test_business_impact_no_crawl_returns_default() -> None:
    text = NarrativeEngine.build_business_impact(
        total_urls=0,
        link_inventory_rows=[],
        technical_extra_rows=[],
        content_ai_rows=[],
        avg_seo_score_pct=0.0,
    )
    assert "No data available" in text


def test_business_impact_flags_broken_links_and_missing_psi() -> None:
    link_rows = [
        {"Link Type": "Internal", "Target URL": "https://s.test/dead", "Status Code": 404},
        {"Link Type": "Internal", "Target URL": "https://s.test/dead", "Status Code": 404},
    ]
    text = NarrativeEngine.build_business_impact(
        total_urls=5,
        link_inventory_rows=link_rows,
        technical_extra_rows=[_extra(**{"PSI Data Status": "Not measured"})],
        content_ai_rows=[],
        avg_seo_score_pct=10.0,
    )
    assert "broken internal link" in text.lower()
    assert "https://s.test/dead" in text
    assert "performance audit" in text.lower()


def test_business_impact_reports_aeo_gap_when_seo_low() -> None:
    text = NarrativeEngine.build_business_impact(
        total_urls=5,
        link_inventory_rows=[],
        technical_extra_rows=[
            _extra(
                **{
                    "PSI Data Status": "PSI Lab",
                    "Mobile PSI Score": 80.0,
                    "Desktop PSI Score": 82.0,
                }
            )
        ],
        content_ai_rows=[],
        avg_seo_score_pct=10.0,
    )
    assert "AEO Opportunity" in text


def test_business_impact_quiet_when_no_gates_fire() -> None:
    text = NarrativeEngine.build_business_impact(
        total_urls=5,
        link_inventory_rows=[],
        technical_extra_rows=[
            _extra(
                **{
                    "PSI Data Status": "PSI Lab",
                    "Mobile PSI Score": 95.0,
                    "Desktop PSI Score": 96.0,
                }
            )
        ],
        content_ai_rows=[{"AEO Extractability Score": 95.0}],
        avg_seo_score_pct=95.0,
    )
    assert "No high-priority storytelling gates" in text
