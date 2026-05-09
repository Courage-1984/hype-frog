"""Per-link inventory annotations and external link sniff helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

import aiohttp

from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.url_normalization import normalize_url
from hype_frog.crawler.link_checks import check_url_status_light

_EXTERNAL_HEAD_DELAY_SECONDS = 2.0


async def sniff_external_domains_head(
    session: aiohttp.ClientSession,
    extra_rows: list[ExtraRowPayload],
) -> dict[str, int | None]:
    """One HEAD per unique external hostname; 2s delay between attempts after the first."""
    domain_first_url: dict[str, str] = {}
    for row in extra_rows:
        for item in row.values.get("Link Details") or []:
            if str(item.get("Link Type") or "") != "External":
                continue
            raw_target = str(item.get("Target URL") or "").strip()
            if not raw_target:
                continue
            host = urlparse(raw_target).netloc.lower()
            if not host:
                continue
            if host not in domain_first_url:
                domain_first_url[host] = raw_target
    results: dict[str, int | None] = {}
    items = sorted(domain_first_url.items())
    for i, (host, url) in enumerate(items):
        if i > 0:
            await asyncio.sleep(_EXTERNAL_HEAD_DELAY_SECONDS)
        results[host] = await check_url_status_light(session, url)
    return results


def annotate_link_details_with_status(
    extra_rows: list[ExtraRowPayload],
    *,
    status_by_url: Mapping[str, object],
    external_status_by_netloc: Mapping[str, int | None] | None,
    sniff_external: bool,
    normalize_url_key_fn: Callable[[object], str],
) -> None:
    """Fill Status Code on each Link Details row; normalize Rel Attribute key."""
    norm = normalize_url_key_fn
    for row in extra_rows:
        details = row.values.get("Link Details")
        if not details:
            continue
        updated: list[dict[str, Any]] = []
        for raw in details:
            item: dict[str, Any] = dict(raw)
            target = str(item.get("Target URL") or "").strip()
            link_type = str(item.get("Link Type") or "")
            if link_type == "Internal":
                code = status_by_url.get(norm(target))
                item["Status Code"] = code if code is not None else ""
            elif link_type == "External":
                if sniff_external and external_status_by_netloc is not None:
                    host = urlparse(target).netloc.lower()
                    ext_code = external_status_by_netloc.get(host)
                    item["Status Code"] = ext_code if ext_code is not None else ""
                else:
                    item["Status Code"] = ""
            else:
                item.setdefault("Status Code", "")
            if "Rel Attribute" not in item and item.get("Rel"):
                item["Rel Attribute"] = item.get("Rel")
            updated.append(item)
        row.values["Link Details"] = updated


def unique_external_health_counts(
    flat_link_rows: list[Mapping[str, Any]],
) -> tuple[int, int]:
    """Return (unique_external_200_ok, unique_external_total) by normalized target URL."""
    per_target: dict[str, Any] = {}
    for r in flat_link_rows:
        if str(r.get("Link Type") or "") != "External":
            continue
        raw_t = str(r.get("Target URL") or "").strip()
        if not raw_t:
            continue
        t = normalize_url(raw_t, keep_query=True)
        if not t:
            continue
        if t not in per_target:
            per_target[t] = r.get("Status Code")
    total = len(per_target)
    ok = sum(1 for code in per_target.values() if code == 200)
    return ok, total


__all__ = [
    "annotate_link_details_with_status",
    "sniff_external_domains_head",
    "unique_external_health_counts",
]
