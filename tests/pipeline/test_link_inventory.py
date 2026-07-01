"""Per-link status annotation and external health counting."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.url_normalization import normalize_url
from hype_frog.pipeline import link_inventory
from hype_frog.pipeline.link_inventory import (
    annotate_link_details_with_status,
    sniff_external_domains_head,
    unique_external_health_counts,
)


def _extra_with_links(url: str, link_details: list[dict]) -> ExtraRowPayload:
    payload = ExtraRowPayload.model_validate({})
    payload.values["URL"] = url
    payload.values["Link Details"] = link_details
    return payload


def test_unique_external_health_counts_dedupes_by_normalised_target() -> None:
    rows = [
        {"Link Type": "External", "Target URL": "https://ext.test/x", "Status Code": 200},
        {"Link Type": "External", "Target URL": "https://ext.test/x?a=1", "Status Code": 200},
        # Duplicate of the first normalised target; first status wins, not recounted.
        {"Link Type": "External", "Target URL": "https://ext.test/x", "Status Code": 404},
        {"Link Type": "Internal", "Target URL": "https://int.test/y", "Status Code": 200},
    ]
    ok, total = unique_external_health_counts(rows)
    assert (ok, total) == (2, 2)


def test_unique_external_health_counts_handles_non_200() -> None:
    rows = [
        {"Link Type": "External", "Target URL": "https://a.test/", "Status Code": 200},
        {"Link Type": "External", "Target URL": "https://b.test/", "Status Code": 500},
    ]
    assert unique_external_health_counts(rows) == (1, 2)


def test_annotate_link_details_fills_status_codes() -> None:
    row = _extra_with_links(
        "https://s.test/page",
        [
            {"Link Type": "Internal", "Target URL": "https://int.test/a", "Rel": "nofollow"},
            {"Link Type": "External", "Target URL": "https://ext.test/b"},
            {"Link Type": "Internal", "Target URL": "https://int.test/missing"},
        ],
    )
    status_by_url = {normalize_url("https://int.test/a"): 200}

    annotate_link_details_with_status(
        [row],
        status_by_url=status_by_url,
        external_status_by_netloc={"ext.test": 301},
        sniff_external=True,
        normalize_url_key_fn=normalize_url,
    )

    details = row.values["Link Details"]
    assert details[0]["Status Code"] == 200
    assert details[0]["Rel Attribute"] == "nofollow"  # legacy Rel mirrored
    assert details[1]["Status Code"] == 301
    assert details[2]["Status Code"] == ""  # unknown internal target


def test_annotate_blank_external_when_sniff_disabled() -> None:
    row = _extra_with_links(
        "https://s.test/page",
        [{"Link Type": "External", "Target URL": "https://ext.test/b"}],
    )
    annotate_link_details_with_status(
        [row],
        status_by_url={},
        external_status_by_netloc=None,
        sniff_external=False,
        normalize_url_key_fn=normalize_url,
    )
    assert row.values["Link Details"][0]["Status Code"] == ""


async def test_sniff_external_domains_head_one_probe_per_host(monkeypatch) -> None:
    probe = AsyncMock(return_value=200)
    monkeypatch.setattr(link_inventory, "check_url_status_light_limited", probe)

    row = _extra_with_links(
        "https://s.test/page",
        [{"Link Type": "External", "Target URL": "https://ext.test/landing"}],
    )
    session = MagicMock()

    link_inventory.clear_external_head_cache()
    result = await sniff_external_domains_head(session, [row])

    assert result == {"ext.test": 200}
    probe.assert_awaited_once()


async def test_sniff_external_domains_head_ttl_cache_skips_second_probe(monkeypatch) -> None:
    probe = AsyncMock(return_value=200)
    monkeypatch.setattr(link_inventory, "check_url_status_light_limited", probe)
    link_inventory.clear_external_head_cache()

    row = _extra_with_links(
        "https://s.test/page",
        [{"Link Type": "External", "Target URL": "https://ext.test/landing"}],
    )
    session = MagicMock()

    first = await sniff_external_domains_head(session, [row])
    second = await sniff_external_domains_head(session, [row])

    assert first == second == {"ext.test": 200}
    probe.assert_awaited_once()
