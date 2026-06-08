"""Broken internal link metrics — single source of truth."""

from hype_frog.pipeline.assemble import row_with_canonical_and_internal_links
from hype_frog.pipeline.broken_links import (
    count_broken_internal_from_link_details,
    count_broken_internal_instances,
    link_inventory_broken_internal_total_formula,
    summarize_broken_internal_links,
)
from hype_frog.core.models import ExtraRowPayload


def test_anchor_level_count_not_unique_target_dedup() -> None:
    """Two anchors to the same broken URL must count as two instances."""
    rows = [
        {
            "Source URL": "https://example.com/a",
            "Target URL": "https://example.com/missing",
            "Link Type": "Internal",
            "Status Code": 404,
        },
        {
            "Source URL": "https://example.com/a",
            "Target URL": "https://example.com/missing",
            "Link Type": "Internal",
            "Status Code": 404,
        },
    ]
    assert count_broken_internal_instances(rows) == 2
    metrics = summarize_broken_internal_links(rows)
    assert metrics.instances == 2
    assert metrics.affected_urls == 1


def test_counts_all_4xx_not_only_404() -> None:
    rows = [
        {
            "Source URL": "https://example.com/a",
            "Target URL": "https://example.com/gone",
            "Link Type": "Internal",
            "Status Code": 410,
        },
    ]
    assert count_broken_internal_instances(rows) == 1


def test_assemble_uses_link_details_anchor_count() -> None:
    payload = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/page",
            "Internal Links List Full": ["https://example.com/missing"],
            "Link Details": [
                {
                    "Target URL": "https://example.com/missing",
                    "Link Type": "Internal",
                    "Status Code": 404,
                },
                {
                    "Target URL": "https://example.com/missing",
                    "Link Type": "Internal",
                    "Status Code": 404,
                },
            ],
        }
    )
    status_by_url = {"https://example.com/missing": 404}
    enriched = row_with_canonical_and_internal_links(
        payload,
        crawled_finals=set(),
        status_by_url=status_by_url,
    )
    assert enriched.values["Broken Internal Links Count"] == 2
    assert count_broken_internal_from_link_details(payload.values["Link Details"]) == 2


def test_dashboard_formula_uses_sumproduct_on_inventory() -> None:
    formula = link_inventory_broken_internal_total_formula()
    assert "SUMPRODUCT" in formula
    assert "Link Inventory" in formula
    assert ">=400" in formula
