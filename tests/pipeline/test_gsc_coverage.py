"""GSC coverage notes and URL lookup for Search Analytics enrichment."""

from __future__ import annotations

from datetime import date

from hype_frog.pipeline.gsc_coverage import (
    apply_gsc_coverage_fields,
    format_gsc_data_freshness,
    lookup_gsc_metrics,
    resolve_gsc_coverage_note,
)


def test_format_gsc_data_freshness() -> None:
    label = format_gsc_data_freshness(date(2026, 5, 1), date(2026, 5, 30))
    assert label is not None
    assert "2026-05-01" in label
    assert "2026-05-30" in label


def test_lookup_gsc_metrics_uses_final_url_variant() -> None:
    gsc_map = {
        "https://example.com/page": {
            "GSC Impressions": 120.0,
            "GSC Clicks": 4.0,
            "GSC CTR": 0.03,
            "GSC Average Position": 8.2,
        }
    }
    found = lookup_gsc_metrics(
        gsc_map,
        url_key="https://example.com/old",
        normalized_key="https://example.com/old",
        seed_url="https://example.com/old",
        final_url="https://example.com/page/",
    )
    assert found is not None
    assert found["GSC Impressions"] == 120.0


def test_resolve_gsc_coverage_note_low_volume() -> None:
    note = resolve_gsc_coverage_note(
        analytics_succeeded=True,
        matched=True,
        impressions=3.0,
        clicks=0.0,
    )
    assert "low impressions" in note.lower()


def test_apply_gsc_coverage_fields_unmatched_sets_note() -> None:
    row: dict[str, object] = {
        "URL": "https://example.com/missing",
        "Final URL": "https://example.com/missing",
    }
    apply_gsc_coverage_fields(
        row,
        gsc_map={},
        url_key="https://example.com/missing",
        normalized_key="https://example.com/missing",
        analytics_succeeded=True,
        gsc_data_freshness="2026-05-01 to 2026-05-30",
    )
    assert "No Search Analytics row matched" in str(row["GSC Coverage Note"])
    assert row["GSC Impressions"] == 0.0
