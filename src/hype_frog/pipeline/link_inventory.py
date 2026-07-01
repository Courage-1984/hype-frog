"""Per-link inventory annotations and external link sniff helpers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import urlparse

import aiohttp

from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.url_normalization import normalize_url
from hype_frog.crawler.link_checks import check_url_status_light_limited

_EXTERNAL_HEAD_CONCURRENCY = 75
_EXTERNAL_HEAD_TIMEOUT_SECONDS = 5.0
_EXTERNAL_HEAD_CACHE_TTL_SECONDS = 3600.0

_external_head_cache: dict[str, tuple[float, int | None]] = {}


def clear_external_head_cache() -> None:
    """Reset the process-wide external HEAD TTL cache (tests and long-lived workers)."""
    _external_head_cache.clear()


def collect_external_domain_probe_urls(
    extra_rows: Iterable[ExtraRowPayload],
) -> dict[str, str]:
    """Map each external hostname to one representative target URL."""
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
    return domain_first_url


async def sniff_external_domains_head(
    session: aiohttp.ClientSession,
    extra_rows: Iterable[ExtraRowPayload],
    *,
    max_concurrency: int = _EXTERNAL_HEAD_CONCURRENCY,
    timeout_seconds: float = _EXTERNAL_HEAD_TIMEOUT_SECONDS,
    cache_ttl_seconds: float = _EXTERNAL_HEAD_CACHE_TTL_SECONDS,
) -> dict[str, int | None]:
    """Probe unique external hostnames concurrently with aggressive timeouts."""
    domain_first_url = collect_external_domain_probe_urls(extra_rows)
    if not domain_first_url:
        return {}

    semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 100)))
    now = time.monotonic()

    async def _probe_host(host: str, url: str) -> tuple[str, int | None]:
        cached = _external_head_cache.get(host)
        if cached is not None:
            cached_at, status = cached
            if now - cached_at < cache_ttl_seconds:
                return host, status

        status = await check_url_status_light_limited(
            session,
            url,
            semaphore,
            timeout_seconds=timeout_seconds,
        )
        _external_head_cache[host] = (time.monotonic(), status)
        return host, status

    pairs = await asyncio.gather(
        *[
            _probe_host(host, url)
            for host, url in sorted(domain_first_url.items())
        ]
    )
    return dict(pairs)


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
    flat_link_rows: list[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
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
    "clear_external_head_cache",
    "collect_external_domain_probe_urls",
    "sniff_external_domains_head",
    "unique_external_health_counts",
]
