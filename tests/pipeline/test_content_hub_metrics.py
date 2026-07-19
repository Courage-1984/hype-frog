"""Content Hub Metrics resolver and enrichment backfill."""

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.content_hub_metrics import (
    backfill_extra_content_hub_metrics,
    compute_js_dependent_flag,
    resolve_content_hub_metrics,
)
from hype_frog.reporter.engine_rows import (
    build_content_hub_metrics_for_all_urls,
    build_content_optimisation_hub_rows,
)


def test_word_count_fallback_when_render_metrics_missing() -> None:
    snapshot = resolve_content_hub_metrics(
        {"Word Count (Body)": 420},
        {"Word Count": 420},
    )
    assert snapshot.raw_words == 420
    assert snapshot.rendered_words == 420
    assert snapshot.js_dependent is False


def test_psi_cwv_fallback_for_field_lcp_and_cls() -> None:
    snapshot = resolve_content_hub_metrics(
        {},
        {
            "CWV LCP (s)": 2.5,
            "CWV CLS": 0.08,
        },
    )
    assert snapshot.field_lcp_ms == 2500.0
    assert snapshot.field_cls == 0.08


def test_playwright_metrics_preferred_over_psi() -> None:
    snapshot = resolve_content_hub_metrics(
        {},
        {
            "Field LCP (ms)": 1800.0,
            "Field CLS": 0.03,
            "CWV LCP (s)": 4.0,
            "CWV CLS": 0.2,
        },
    )
    assert snapshot.field_lcp_ms == 1800.0
    assert snapshot.field_cls == 0.03


def test_js_dependent_when_rendered_exceeds_raw() -> None:
    assert compute_js_dependent_flag(100, 200) is True
    assert compute_js_dependent_flag(500, 510) is False


def test_backfill_persists_on_extra_row_payload() -> None:
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/",
            "Word Count": 300,
            "Mobile LCP (s)": 3.2,
            "CWV CLS": 0.11,
        }
    )
    main = MainRowPayload.model_validate(
        {"URL": "https://example.com/", "Word Count (Body)": 300}
    )
    backfill_extra_content_hub_metrics(extra.values, main.values)
    assert extra.values["Raw Words"] == 300
    assert extra.values["Rendered Words"] == 300
    assert extra.values["Field LCP (ms)"] == 3200.0
    assert extra.values["Field CLS"] == 0.11


def test_hub_metrics_sheet_uses_resolver_not_stale_zeros() -> None:
    main = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/page",
            "Word Count (Body)": 512,
            "GSC Clicks": 10,
        }
    )
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/page",
            "Word Count": 512,
            "SEO Health Score": 40.0,
            "Mobile LCP (s)": 2.1,
            "CWV CLS": 0.05,
            "Search Intent": "Informational",
            "Anchor Text Diversity": "12 unique / 40 total",
        }
    )
    _hub_rows, metrics_rows = build_content_optimisation_hub_rows(
        [main],
        [extra],
        [],
    )
    assert len(metrics_rows) == 1
    row = metrics_rows[0]
    assert row["Raw Words"] == 512
    assert row["Rendered Words"] == 512
    assert row["Field LCP (ms)"] == 2100.0
    assert row["Field CLS"] == 0.05
    assert row["Search Intent"] == "Informational"


def test_build_content_hub_metrics_for_all_urls_covers_every_url_not_just_curated() -> None:
    """Content & AI Readiness needs metrics for every URL, computed unconditionally —
    unlike build_content_optimisation_hub_rows, which only computes metrics for its
    curated "manual content" subset (see its manual_content_urls selection logic)."""
    main = MainRowPayload.model_validate(
        {"URL": "https://example.com/clean", "Word Count (Body)": 900, "GSC Clicks": 5}
    )
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/clean",
            "Word Count": 900,
            "SEO Health Score": 98.0,
            "Matched Issues": "",
            "Search Intent": "Transactional",
        }
    )
    all_rows = build_content_hub_metrics_for_all_urls([main], [extra])
    assert len(all_rows) == 1
    assert all_rows[0]["URL"] == "https://example.com/clean"
    assert all_rows[0]["Raw Words"] == 900
    assert all_rows[0]["Search Intent"] == "Transactional"
