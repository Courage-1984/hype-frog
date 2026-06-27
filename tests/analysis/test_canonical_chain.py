"""B1 canonical chain resolution tests."""
from __future__ import annotations

from hype_frog.analysis.canonical_chain import (
    enrich_extra_rows_canonical_chains,
    resolve_canonical_chain_fields,
)


def test_self_canonical_depth_zero() -> None:
    fields = resolve_canonical_chain_fields(
        source_url="https://example.com/a",
        canonical_url="https://example.com/a",
        target_map={},
        status_by_url={"https://example.com/a": 200},
        extra_by_url={},
    )
    assert fields["Canonical Chain Depth"] == 0
    assert fields["Canonical Loop Detected"] is False


def test_multi_hop_chain_and_loop() -> None:
    target_map = {
        "https://example.com/a": "https://example.com/b",
        "https://example.com/b": "https://example.com/c",
        "https://example.com/c": "https://example.com/a",
    }
    fields = resolve_canonical_chain_fields(
        source_url="https://example.com/a",
        canonical_url="https://example.com/b",
        target_map=target_map,
        status_by_url={
            "https://example.com/b": 200,
            "https://example.com/c": 301,
        },
        extra_by_url={
            "https://example.com/c": {"Redirect Chain Length": 1, "Status Code": 301},
        },
    )
    assert fields["Canonical Chain Depth"] >= 2
    assert fields["Canonical Loop Detected"] is True
    assert fields["Canonical Points to Redirect"] is True


def test_enrich_extra_rows_in_place() -> None:
    rows = [
        {
            "URL": "https://example.com/a",
            "Final URL": "https://example.com/a",
            "Canonical URL": "https://example.com/b",
            "Status Code": 200,
        },
        {
            "URL": "https://example.com/b",
            "Final URL": "https://example.com/b",
            "Canonical URL": "https://example.com/b",
            "Status Code": 404,
        },
    ]
    status_by_url = {
        "https://example.com/a": 200,
        "https://example.com/b": 404,
    }
    enrich_extra_rows_canonical_chains(rows, status_by_url=status_by_url)
    assert rows[0]["Canonical Chain Depth"] == 1
    assert rows[0]["Canonical Points to Non-200"] is True
