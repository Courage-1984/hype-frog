"""Synthetic sitemap-scale fixtures for ``--full-smoke-test`` (offline crawl, real export)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.core.run_config import (
    FULL_SMOKE_SITEMAP_URL,
    FULL_SMOKE_SYNTHETIC_URL_COUNT,
    _full_smoke_url_count,
)
from hype_frog.core.url_normalization import normalize_url
from hype_frog.crawler.psi_engine import _merge_url_results

_OFF_SITEMAP_DISCOVERY_COUNT = 3


@dataclass(frozen=True)
class FullSmokeFixture:
    """Deterministic uncapped-sitemap simulation at representative scale."""

    sitemap_url: str
    urls: tuple[str, ...]
    off_sitemap_urls: tuple[str, ...]
    sitemap_meta: dict[str, dict[str, Any]]
    sitemap_files_meta: dict[str, dict[str, Any]]
    url_index_by_key: dict[str, int]

    @property
    def sitemap_url_count(self) -> int:
        return len(self.urls)


def _status_for_index(index: int) -> int | str:
    if index % 17 == 0:
        return "Timeout"
    if index % 13 == 0:
        return 404
    if index % 11 == 0:
        return 301
    return 200


def _extraction_state_for_index(index: int) -> str:
    if index % 19 == 0:
        return "partial"
    return "complete"


def build_full_smoke_fixture(
    *,
    sitemap_url: str = FULL_SMOKE_SITEMAP_URL,
    url_count: int | None = None,
) -> FullSmokeFixture:
    """Build a synthetic page sitemap at production-like volume (no ``max_urls`` cap)."""
    resolved_count = url_count if url_count is not None else _full_smoke_url_count()
    parsed = urlparse(sitemap_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    urls: list[str] = []
    sitemap_meta: dict[str, dict[str, Any]] = {}
    url_index_by_key: dict[str, int] = {}

    for index in range(resolved_count):
        if index == 0:
            url = f"{base}/"
        else:
            url = f"{base}/smoke-archive/page-{index}/"
        urls.append(url)
        sitemap_meta[url] = {
            "lastmod": "2026-06-01" if index % 3 == 0 else "",
            "changefreq": "weekly" if index % 5 == 0 else "",
            "priority": "0.8" if index % 7 == 0 else "",
            "source_sitemap": sitemap_url,
            "sitemap_kind": "urlset",
        }
        url_index_by_key[normalize_url(url)] = index

    off_sitemap_urls = tuple(
        f"{base}/discovered-via-bfs-{slot}/" for slot in range(1, _OFF_SITEMAP_DISCOVERY_COUNT + 1)
    )
    for off_url in off_sitemap_urls:
        url_index_by_key[normalize_url(off_url)] = resolved_count + int(
            off_url.rstrip("/").split("-")[-1]
        )

    sitemap_files_meta = {
        sitemap_url: {
            "kind": "urlset",
            "url_count": resolved_count,
            "size_bytes": resolved_count * 140,
            "is_index": False,
        }
    }
    return FullSmokeFixture(
        sitemap_url=sitemap_url,
        urls=tuple(urls),
        off_sitemap_urls=off_sitemap_urls,
        sitemap_meta=sitemap_meta,
        sitemap_files_meta=sitemap_files_meta,
        url_index_by_key=url_index_by_key,
    )


def build_smoke_crawl_payload(fixture: FullSmokeFixture, url: str) -> CrawlRowPayload:
    """Return a typed crawl row with transport and extraction edge cases."""
    key = normalize_url(url)
    index = fixture.url_index_by_key.get(key, 0)
    status = _status_for_index(index)
    extraction_state = _extraction_state_for_index(index)
    final_url = url
    redirect_chain_length = 0
    if status == 301:
        final_url = f"{url.rstrip('/')}-canonical/"
        redirect_chain_length = 1

    internal_links: list[str] = []
    if index == 1:
        internal_links.extend(fixture.off_sitemap_urls)
    elif index > 1 and index % 23 == 0:
        internal_links.append(fixture.urls[index - 1])

    indexability = "Indexable"
    if status in {404, "Timeout"}:
        indexability = "Non-Indexable"

    main_values: dict[str, Any] = {
        "URL": url,
        "Final URL": final_url,
        "Title": f"Smoke title {index}",
        "Meta Description": f"Smoke meta description for page {index}.",
        "Word Count (Body)": 320 + (index % 50),
        "Indexability": indexability,
        "Extraction State": extraction_state,
        "Extraction Source": "rendered_browser",
    }
    extra_values: dict[str, Any] = {
        "URL": url,
        "Final URL": final_url,
        "Status Code": status,
        "Status Class": "Success" if status == 200 else "Error",
        "Extraction State": extraction_state,
        "Extraction Source": "rendered_browser",
        "Redirect Chain Length": redirect_chain_length,
        "Canonical URL": final_url if status == 200 else url,
        "Canonical Type": "self" if status == 200 else "",
        "Internal Links List Full": internal_links,
        "Link Details": [
            {
                "Target URL": internal_links[0] if internal_links else f"{urlparse(url).scheme}://{urlparse(url).netloc}/",
                "Anchor Text": "Smoke anchor",
                "Status Code": 200,
            }
        ],
        "OG Image URL": f"{urlparse(url).scheme}://{urlparse(url).netloc}/og-{index}.jpg"
        if index % 4 == 0
        else "",
        "HTTP Last-Modified": "2026-06-01" if index % 3 == 0 else "",
        "Current H-Tag Structure": "H1: Smoke heading",
        "Current Page Copy Snippet": "Smoke body copy for intent classification.",
    }
    return CrawlRowPayload(
        main=MainRowPayload.model_validate({"values": main_values}),
        extra=ExtraRowPayload.model_validate({"values": extra_values}),
    )


def _sample_lighthouse_result() -> dict[str, Any]:
    return {
        "categories": {
            "performance": {"score": 0.88},
            "accessibility": {"score": 0.85},
            "best-practices": {"score": 0.78},
            "seo": {"score": 0.92},
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": 2400.0, "score": 0.6},
            "cumulative-layout-shift": {"numericValue": 0.04, "score": 0.9},
            "interaction-to-next-paint": {"numericValue": 120.0, "score": 0.8},
            "total-blocking-time": {"numericValue": 180.0, "score": 0.7},
            "first-contentful-paint": {"numericValue": 1800.0, "score": 0.75},
            "speed-index": {"numericValue": 3200.0, "score": 0.65},
            "interactive": {"numericValue": 4100.0, "score": 0.6},
            "server-response-time": {"numericValue": 400.0, "score": 0.8},
            "total-byte-weight": {"numericValue": 512000.0, "score": 0.5},
            "dom-size": {"numericValue": 842.0, "score": 0.7},
            "bootup-time": {"numericValue": 1250.0, "score": 0.6},
            "network-requests": {
                "details": {"items": [{"url": "https://example.com/a"}]}
            },
            "uses-text-compression": {"score": 1.0},
            "uses-long-cache-ttl": {"score": 0.5},
            "render-blocking-resources": {"score": 0.0},
            "uses-webp-images": {"score": 0.0},
            "modern-image-formats": {"score": 1.0},
        },
    }


async def _fake_psi_batch(
    _session: Any,
    urls: list[str],
    max_parallel: int = 8,
    max_urls: int | None = None,
) -> dict[str, dict[str, Any]]:
    del max_parallel
    unique = [u for u in dict.fromkeys(urls) if u]
    if max_urls is not None and max_urls > 0:
        unique = unique[:max_urls]
    lighthouse = _sample_lighthouse_result()
    mobile = {"lighthouseResult": lighthouse}
    desktop = {"lighthouseResult": lighthouse}
    results: dict[str, dict[str, Any]] = {}
    for url in unique:
        merged = _merge_url_results(url, mobile, desktop)
        results[url] = merged
        results[normalize_url(url)] = merged
    return results


@contextmanager
def full_smoke_network_patches(fixture: FullSmokeFixture) -> Iterator[None]:
    """Patch crawl/enrichment network collaborators for a fast full-pipeline run."""

    async def fake_parse_sitemap(
        _url: str, _session: Any
    ) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        return list(fixture.urls), dict(fixture.sitemap_meta), dict(fixture.sitemap_files_meta)

    async def fake_fetch_and_parse(url: str, *_args: Any, **_kwargs: Any) -> CrawlRowPayload:
        return build_smoke_crawl_payload(fixture, url)

    @asynccontextmanager
    async def fake_create_session() -> AsyncIterator[Any]:
        yield MagicMock(name="aiohttp_session_double")

    fake_playwright = MagicMock(name="PlaywrightSessionManager_double")
    fake_playwright.get_context = AsyncMock(return_value=MagicMock(name="browser_context"))
    fake_playwright.aclose = AsyncMock(return_value=None)

    async def fake_intent(_self: Any, _text: str | None) -> str:
        return "Informational"

    async def fake_link_status(_session: Any, _target: str, _sem: Any) -> int:
        return 200

    async def fake_external_sniff(_session: Any, _rows: Any) -> dict[str, int | None]:
        return {"example.com": 200, "cdn.example.com": 200}

    async def fake_og_validation(*_args: Any, **_kwargs: Any) -> None:
        return None

    with (
        patch(
            "hype_frog.orchestration.crawl_runner.parse_sitemap",
            new=fake_parse_sitemap,
        ),
        patch(
            "hype_frog.orchestration.crawl_runner.fetch_and_parse",
            new=fake_fetch_and_parse,
        ),
        patch(
            "hype_frog.orchestration.crawl_runner.create_session",
            new=fake_create_session,
        ),
        patch(
            "hype_frog.orchestration.crawl_runner.PlaywrightSessionManager",
            return_value=fake_playwright,
        ),
        patch(
            "hype_frog.extractors.semantic_engine.IntentAnalyzer.analyze_intent",
            new=fake_intent,
        ),
        patch(
            "hype_frog.orchestration.enrichment_flow.fetch_psi_metrics_batch",
            new=_fake_psi_batch,
        ),
        patch(
            "hype_frog.orchestration.enrichment_flow.check_url_status_light_limited",
            new=fake_link_status,
        ),
        patch(
            "hype_frog.orchestration.enrichment_flow.sniff_external_domains_head",
            new=fake_external_sniff,
        ),
        patch(
            "hype_frog.orchestration.enrichment_flow.enrich_og_image_validation",
            new=fake_og_validation,
        ),
    ):
        yield


__all__ = [
    "FullSmokeFixture",
    "build_full_smoke_fixture",
    "build_smoke_crawl_payload",
    "full_smoke_network_patches",
]
