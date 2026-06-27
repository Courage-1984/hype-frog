"""Unit tests for link equity analysis (B2)."""

from __future__ import annotations

from hype_frog.analysis.link_equity import (
    build_anchor_text_audit_rows,
    build_link_equity_rows,
    enrich_link_equity_fields,
)
from hype_frog.core.url_normalization import normalize_url


def test_enrich_link_equity_fields_sets_percentile_and_tier() -> None:
    class Row:
        def __init__(self) -> None:
            self.values: dict[str, object] = {
                "URL": "https://example.com/high",
                "Final URL": "https://example.com/high",
            }

    rows = [Row()]
    graph = {
        normalize_url("https://example.com/high"): {
            "Internal PageRank": 0.2,
            "Orphan Pages": False,
            "Click Depth": 1,
        },
        normalize_url("https://example.com/low"): {
            "Internal PageRank": 0.01,
            "Orphan Pages": True,
            "Click Depth": -1,
        },
    }
    enrich_link_equity_fields(rows, graph)
    assert rows[0].values["Equity Tier"] in {"High", "Medium", "Low", "Orphan"}
    assert "PageRank Percentile" in rows[0].values


def test_build_anchor_text_audit_flags_generic_dominance() -> None:
    extra_rows = [
        {
            "URL": "https://example.com/source",
            "Link Details": [
                {
                    "Link Type": "internal",
                    "Target URL": "https://example.com/target",
                    "Anchor Text": "click here",
                    "Generic Anchor": True,
                },
                {
                    "Link Type": "internal",
                    "Target URL": "https://example.com/target",
                    "Anchor Text": "read more",
                    "Generic Anchor": True,
                },
            ],
        }
    ]
    rows = build_anchor_text_audit_rows(extra_rows)
    assert rows[0]["Generic Anchor Dominance"] is True


def test_build_link_equity_rows_sorted_by_pagerank() -> None:
    extra_rows = [
        {"URL": "https://example.com/a"},
        {"URL": "https://example.com/b"},
    ]
    graph = {
        normalize_url("https://example.com/a"): {
            "Internal PageRank": 0.05,
            "Orphan Pages": False,
            "Click Depth": 1,
        },
        normalize_url("https://example.com/b"): {
            "Internal PageRank": 0.2,
            "Orphan Pages": False,
            "Click Depth": 1,
        },
    }
    rows = build_link_equity_rows(extra_rows, graph)
    assert rows[0]["URL"] == "https://example.com/b"
