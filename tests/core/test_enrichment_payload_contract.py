"""Ensure enrichment fields survive Pydantic row whitelist validation."""

from __future__ import annotations

from hype_frog.analysis.link_equity import enrich_link_equity_fields
from hype_frog.analysis.snippet_opportunities import enrich_snippet_opportunity_fields
from hype_frog.analysis.third_party_scripts import enrich_third_party_script_fields
from hype_frog.analysis.topical_authority import enrich_topical_authority_fields
from hype_frog.core.models import ENRICHMENT_PIPELINE_DEFAULTS, ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.assemble import assemble_enriched_row


def test_enrichment_pipeline_defaults_cover_post_crawl_merge_keys() -> None:
    from hype_frog.pipeline.assemble import (
        A2_MAIN_MERGE_KEYS,
        A4_MAIN_MERGE_KEYS,
        A6_MAIN_MERGE_KEYS,
        B2_MAIN_MERGE_KEYS,
        B3_MAIN_MERGE_KEYS,
        B6_MAIN_MERGE_KEYS,
    )

    merge_keys = set(
        A2_MAIN_MERGE_KEYS
        + A4_MAIN_MERGE_KEYS
        + A6_MAIN_MERGE_KEYS
        + B2_MAIN_MERGE_KEYS
        + B3_MAIN_MERGE_KEYS
        + B6_MAIN_MERGE_KEYS
    )
    missing = sorted(
        key
        for key in merge_keys
        if key not in ENRICHMENT_PIPELINE_DEFAULTS and key not in ExtraRowPayload.model_validate({}).values
    )
    assert not missing, f"Extra row contract missing post-crawl merge keys: {missing}"


def test_extra_row_preserves_psi_and_enrichment_fields_after_validation() -> None:
    raw = {
        "URL": "https://example.com/",
        "Extraction State": "complete",
        "PSI Network Items": [
            {"url": "https://www.googletagmanager.com/gtm.js", "transfer_kb": 12.5}
        ],
        "PSI Render Blocking URLs": ["https://www.googletagmanager.com/gtm.js"],
        "Content Images": [{"url": "https://example.com/a.png", "alt": "Hero"}],
        "Has HTML Table": True,
        "Hreflang Declared Languages": "en-GB",
        "Hreflang Alternate URLs": "https://example.com/fr/",
        "Hreflang Code Valid": True,
        "GSC Avg Position": 8.5,
        "Question Heading Count": 2,
        "QAPage/FAQ Schema Present": True,
        "Paragraphs 40-60 Words Count": 1,
        "Current Page Copy Snippet": "Widget is a compact device used daily.",
        "Title": "Widget guide",
        "Primary H1 Content": "Widget guide",
    }
    row = ExtraRowPayload.model_validate(raw)
    enrich_third_party_script_fields([row])
    enrich_topical_authority_fields([row])
    enrich_link_equity_fields(
        [row],
        {
            "https://example.com/": {
                "Internal PageRank": 0.04,
                "Internal Inlinks": 3,
            }
        },
    )
    enrich_snippet_opportunity_fields([row])
    validated = ExtraRowPayload.model_validate(row.values)

    assert validated.values.get("Third Party Script Count", 0) > 0
    assert validated.values.get("PSI Network Items")
    assert validated.values.get("Content Images")
    assert validated.values.get("Top TF-IDF Terms")
    assert validated.values.get("Featured Snippet Type") not in (None, "None")
    assert validated.values.get("Equity Tier") is not None


def test_main_row_receives_enrichment_merge_from_extra() -> None:
    main = MainRowPayload.model_validate({"URL": "https://example.com/"})
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/",
            "Third Party Script Count": 2,
            "Has Google Analytics": True,
            "Broken Image Count": 1,
            "Hreflang Declared Languages": "en",
            "PageRank Percentile": 88.0,
            "Featured Snippet Readiness": 7,
            "Top TF-IDF Terms": "widget, guide",
        }
    )
    merged_main = assemble_enriched_row(main, extra, sitemap_url_keys=set())
    values = merged_main.values
    assert values["Third Party Script Count"] == 2
    assert values["Has Google Analytics"] is True
    assert values["Broken Image Count"] == 1
    assert values["Hreflang Declared Languages"] == "en"
    assert values["PageRank Percentile"] == 88.0
    assert values["Featured Snippet Readiness"] == 7
    assert values["Top TF-IDF Terms"] == "widget, guide"
