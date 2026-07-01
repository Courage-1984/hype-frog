"""Unit tests for the BFS crawl orchestrator (Sprint 1).

Covers ``hype_frog.orchestration.crawl_runner``:

* ``_max_depth_from_env`` env-var parsing with the four documented
  fallback paths (unset, blank, invalid, negative).
* ``_candidate_internal_links`` link extraction from a typed
  ``CrawlRowPayload`` (list / non-list / empty values).
* ``execute_crawl`` end-to-end against a fully mocked
  fetcher / session / cache / intent-analyzer stack — no live network,
  no real workbook I/O. Asserts:

  - **BFS frontier ordering:** all depth-1 siblings are scheduled before
    any depth-2 grandchild (workers=1 keeps the schedule deterministic).
  - **HF_MAX_DEPTH respect:** beyond-depth URLs are never enqueued.
  - **Visited-set deduplication:** a URL discovered on multiple parents
    is only crawled once.

Rule #2 (No Network): every external collaborator (``aiohttp``,
``Playwright``, ``AuditCache``, ``IntentAnalyzer``, file paths) is
mocked.
Rule #3 (Extraction State): every mocked ``CrawlRowPayload`` carries an
explicit ``Extraction State`` (``"complete"``) and the BFS test asserts
the state survives end-to-end on every emitted row.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.core.models import (
    CrawlRowPayload,
    ExtraRowPayload,
    MainRowPayload,
)
from hype_frog.orchestration.crawl_runner import (
    _is_crawlable_html_candidate,
    _candidate_internal_links,
    _max_depth_from_env,
    cms_action_exclusion_keys,
    execute_crawl,
)
from hype_frog.orchestration.crawl_payload_loader import load_crawl_row_payloads
from hype_frog.orchestration.run_setup import RunSetup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(url: str, *, links: Iterable[str] = ()) -> CrawlRowPayload:
    """Build a typed crawl payload that the runner can hand to the BFS loop."""
    main = MainRowPayload.model_validate(
        {"values": {"URL": url, "Extraction State": "complete"}}
    )
    extra = ExtraRowPayload.model_validate(
        {
            "values": {
                "URL": url,
                "Extraction State": "complete",
                "Internal Links List Full": list(links),
            }
        }
    )
    return CrawlRowPayload(main=main, extra=extra)


def _build_run_setup(
    *,
    target: str,
    max_urls: int | None = None,
    workers: int = 1,
) -> RunSetup:
    """Construct a fully-preset RunSetup so ``execute_crawl`` skips ``input()``."""
    return RunSetup(
        target_input=target,
        max_urls=max_urls,
        max_psi_urls=None,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers_preset=workers,
        request_delay_preset=0.0,
        full_suite_preset=False,
        previous_audit_path_preset="",
        checkpoint_every_preset=0,
        resume_checkpoint_mode="no",
        check_external_link_status=False,
    )


def _install_runner_mocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    link_graph: dict[str, list[str]],
) -> list[tuple[str, int]]:
    """Wire all of ``crawl_runner``'s collaborators with offline doubles.

    Returns a ``call_order`` list; each entry is ``(url, depth)`` for one
    invocation of the mocked ``fetch_and_parse``. Reading this list after
    ``execute_crawl`` returns reveals the BFS schedule.
    """
    call_order: list[tuple[str, int]] = []

    async def fake_fetch_and_parse(
        url: str,
        _session: Any,
        _semaphore: Any,
        _robots_cache: Any,
        _delay: float,
        _sitemap_meta: Any,
        *,
        depth: int = 0,
        **_kwargs: Any,
    ) -> CrawlRowPayload:
        call_order.append((url, depth))
        children = link_graph.get(url, [])
        return _make_payload(url, links=children)

    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.fetch_and_parse",
        fake_fetch_and_parse,
    )

    @asynccontextmanager
    async def fake_create_session() -> Any:
        yield MagicMock(name="aiohttp_session_double")

    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.create_session",
        fake_create_session,
    )

    stored_results: list[dict[str, Any]] = []

    def _upsert_results(batch: list[Any]) -> None:
        stored_results.extend(batch)
        cache_stub.row_count.return_value = len(stored_results)

    def _iter_results() -> Any:
        for item in stored_results:
            yield item

    def _iter_results_chunked(chunk_size: int = 500) -> Any:
        for index in range(0, len(stored_results), chunk_size):
            yield stored_results[index : index + chunk_size]

    cache_stub = MagicMock(name="AuditCache_stub")
    cache_stub.upsert_results = _upsert_results
    cache_stub.iter_results = _iter_results
    cache_stub.iter_results_chunked = _iter_results_chunked
    cache_stub.row_count = MagicMock(return_value=0)
    cache_stub.all_results = MagicMock(return_value=list(stored_results))
    cache_stub.close = MagicMock()

    def _refresh_row_count() -> int:
        cache_stub.row_count.return_value = len(stored_results)
        return len(stored_results)

    cache_stub._refresh_row_count = _refresh_row_count
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.AuditCache",
        lambda *_a, **_k: cache_stub,
    )

    intent_stub = MagicMock(name="IntentAnalyzer_stub")
    intent_stub.analyze_intent = AsyncMock(return_value="Unknown")
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.IntentAnalyzer",
        lambda *_a, **_k: intent_stub,
    )

    output_path = str(tmp_path / "audit.xlsx")
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.build_output_filename",
        lambda *_a, **_k: output_path,
    )
    # ``HF_OUTPUT_FILENAME`` would otherwise short-circuit the mock above.
    monkeypatch.delenv("HF_OUTPUT_FILENAME", raising=False)

    return call_order


# ---------------------------------------------------------------------------
# _max_depth_from_env — env-var parsing
# ---------------------------------------------------------------------------


def test_max_depth_from_env_returns_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_MAX_DEPTH", raising=False)
    assert _max_depth_from_env(default=3) == 3


def test_max_depth_from_env_returns_default_when_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "   ")
    assert _max_depth_from_env(default=4) == 4


def test_max_depth_from_env_parses_valid_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "5")
    assert _max_depth_from_env(default=3) == 5


def test_max_depth_from_env_clamps_negative_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "-2")
    assert _max_depth_from_env(default=3) == 0


def test_max_depth_from_env_invalid_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "deep")
    assert _max_depth_from_env(default=7) == 7


# ---------------------------------------------------------------------------
# _candidate_internal_links — payload extraction
# ---------------------------------------------------------------------------


def test_candidate_internal_links_returns_normalised_strings() -> None:
    payload = _make_payload(
        "https://example.com/seed",
        links=[
            "https://Example.com/page-A/",  # mixed case + trailing slash
            "https://example.com/page-b",
        ],
    )
    out = _candidate_internal_links(payload)
    assert out == [
        "https://example.com/page-A",
        "https://example.com/page-b",
    ]


def test_candidate_internal_links_handles_non_list_value() -> None:
    payload = _make_payload("https://example.com/seed")
    # Force a non-list value through the model's underlying dict.
    payload.extra.values["Internal Links List Full"] = "not-a-list"  # type: ignore[assignment]
    assert _candidate_internal_links(payload) == []


def test_candidate_internal_links_filters_empty_strings() -> None:
    payload = _make_payload(
        "https://example.com/seed",
        links=["", "   ", "https://example.com/keep"],
    )
    assert _candidate_internal_links(payload) == ["https://example.com/keep"]


def test_candidate_internal_links_skips_binary_asset_urls() -> None:
    payload = _make_payload(
        "https://example.com/seed",
        links=[
            "https://example.com/page",
            "https://example.com/wp-content/uploads/hero.jpg",
            "https://example.com/assets/site.css",
            "https://example.com/files/report.pdf",
        ],
    )
    assert _candidate_internal_links(payload) == ["https://example.com/page"]


def test_is_crawlable_html_candidate_allows_html_like_routes() -> None:
    assert _is_crawlable_html_candidate("https://example.com/")
    assert _is_crawlable_html_candidate("https://example.com/about-us")
    assert _is_crawlable_html_candidate("https://example.com/blog/post-1?utm=1")


def test_is_crawlable_html_candidate_rejects_common_non_html_assets() -> None:
    assert not _is_crawlable_html_candidate("https://example.com/photo.webp")
    assert not _is_crawlable_html_candidate("https://example.com/docs/file.pdf")
    assert not _is_crawlable_html_candidate("https://example.com/sitemap.xml")
    assert not _is_crawlable_html_candidate("https://example.com/app.js")


def test_is_crawlable_html_candidate_rejects_woocommerce_action_params() -> None:
    assert not _is_crawlable_html_candidate(
        "https://example.com/product/widget?add-to-cart=123"
    )
    assert not _is_crawlable_html_candidate(
        "https://example.com/?wc-ajax=get_refreshed_fragments"
    )


def test_is_crawlable_html_candidate_allows_pagination_and_filter_params() -> None:
    assert _is_crawlable_html_candidate("https://example.com/blog?page=2")
    assert _is_crawlable_html_candidate("https://example.com/shop?product_cat=books")
    assert _is_crawlable_html_candidate("https://example.com/?s=marketing")


def test_cms_action_exclusion_keys_is_case_insensitive() -> None:
    keys = cms_action_exclusion_keys(
        "https://example.com/item?Add-To-Cart=99&page=2"
    )
    assert keys == frozenset({"add-to-cart"})


def test_candidate_internal_links_records_cms_action_urls() -> None:
    payload = _make_payload(
        "https://example.com/seed",
        links=[
            "https://example.com/product/widget?add-to-cart=42",
            "https://example.com/blog?page=2",
        ],
    )
    registry: dict[str, object] = {}
    out = _candidate_internal_links(payload, registry)  # type: ignore[arg-type]
    assert out == ["https://example.com/blog?page=2"]
    assert len(registry) == 1
    entry = next(iter(registry.values()))
    assert entry.url.endswith("add-to-cart=42")
    assert entry.discovered_on_url == "https://example.com/seed"
    assert "add-to-cart" in entry.excluded_query_params


async def test_execute_crawl_withholds_cms_action_urls_from_bfs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed = "https://example.com/seed"
    cart = "https://example.com/product/widget?add-to-cart=7"
    child = "https://example.com/about"
    link_graph = {
        seed: [cart, child],
        child: [],
    }

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    setup = _build_run_setup(target=seed)
    result = await execute_crawl(setup)

    visited = [url for url, _depth in call_order]
    assert cart not in visited
    assert child in visited
    assert any(item.url == cart for item in result.excluded_cms_action_urls)


# ---------------------------------------------------------------------------
# execute_crawl — BFS frontier ordering
# ---------------------------------------------------------------------------


async def test_execute_crawl_bfs_visits_depth_1_before_depth_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """All depth-1 siblings must be scheduled before any depth-2 grandchild."""
    seed = "https://example.com/seed"
    a = "https://example.com/a"
    b = "https://example.com/b"
    c = "https://example.com/c"
    a1 = "https://example.com/a1"
    a2 = "https://example.com/a2"
    b1 = "https://example.com/b1"

    link_graph: dict[str, list[str]] = {
        seed: [a, b, c],
        a: [a1, a2],
        b: [b1],
        c: [],
        a1: [],
        a2: [],
        b1: [],
    }

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    setup = _build_run_setup(target=seed)
    result = await execute_crawl(setup)

    urls = [url for url, _depth in call_order]
    depths = [depth for _url, depth in call_order]

    # Seed first, then all depth-1, then all depth-2.
    assert urls[0] == seed
    assert depths == [0, 1, 1, 1, 2, 2, 2]
    assert set(urls[1:4]) == {a, b, c}
    assert set(urls[4:]) == {a1, a2, b1}

    # Depth never goes backward across the schedule.
    for prev, nxt in zip(depths, depths[1:]):
        assert prev <= nxt, f"BFS invariant violated: {prev} → {nxt}"

    assert result.crawl_duration_seconds >= 0.0

    # Rule #3: every emitted payload carries an explicit Extraction State.
    crawl_rows = load_crawl_row_payloads(result)
    assert len(crawl_rows) == 7
    for row in crawl_rows:
        assert row.main.values["Extraction State"] == "complete"
        assert row.extra.values["Extraction State"] in {
            "complete",
            "partial",
            "skipped",
        }


# ---------------------------------------------------------------------------
# execute_crawl — HF_MAX_DEPTH stops the frontier
# ---------------------------------------------------------------------------


async def test_execute_crawl_respects_hf_max_depth_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``HF_MAX_DEPTH=1`` stops grandchildren from being enqueued."""
    seed = "https://example.com/seed"
    a = "https://example.com/a"
    a1 = "https://example.com/a1"
    a1_grandchild = "https://example.com/a1-grandchild"

    link_graph = {
        seed: [a],
        a: [a1],
        a1: [a1_grandchild],
        a1_grandchild: [],
    }

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "1")

    setup = _build_run_setup(target=seed)
    await execute_crawl(setup)

    visited = [url for url, _depth in call_order]
    assert visited == [seed, a]
    assert a1 not in visited
    assert a1_grandchild not in visited
    # No call ever exceeded depth 1.
    assert max(depth for _url, depth in call_order) == 1


async def test_execute_crawl_zero_max_depth_only_visits_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``HF_MAX_DEPTH=0`` keeps the crawl strictly to the seed URL."""
    seed = "https://example.com/seed"
    link_graph = {seed: ["https://example.com/never"]}

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "0")

    setup = _build_run_setup(target=seed)
    await execute_crawl(setup)

    assert call_order == [(seed, 0)]


# ---------------------------------------------------------------------------
# execute_crawl — visited-set deduplication
# ---------------------------------------------------------------------------


async def test_execute_crawl_deduplicates_urls_across_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A URL referenced by multiple parents is crawled at most once."""
    seed = "https://example.com/seed"
    a = "https://example.com/a"
    b = "https://example.com/b"
    shared = "https://example.com/shared"

    link_graph = {
        seed: [a, b],
        a: [shared],
        b: [shared],  # ← duplicate reference to ``shared``
        shared: [],
    }

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    setup = _build_run_setup(target=seed)
    await execute_crawl(setup)

    visited = [url for url, _depth in call_order]
    assert visited.count(shared) == 1, (
        f"duplicate-URL guard failed; visited={visited}"
    )
    assert sorted(visited) == sorted([seed, a, b, shared])


async def test_execute_crawl_deduplicates_when_seed_links_to_itself(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Self-referential links (canonical, sitemap echoes) must not loop."""
    seed = "https://example.com/seed"
    link_graph = {seed: [seed, seed, seed]}

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    setup = _build_run_setup(target=seed)
    await execute_crawl(setup)

    assert call_order == [(seed, 0)]


async def test_execute_crawl_max_urls_seed_cap_truncates_frontier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``setup.max_urls`` enforces a hard ceiling on the BFS frontier."""
    seed = "https://example.com/seed"
    children = [f"https://example.com/child-{i}" for i in range(10)]
    link_graph: dict[str, list[str]] = {seed: children}
    for child in children:
        link_graph[child] = []

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    setup = _build_run_setup(target=seed, max_urls=4)
    await execute_crawl(setup)

    # Seed (1) plus at most three children, totalling four URLs.
    assert len(call_order) <= 4
    assert call_order[0] == (seed, 0)


async def test_execute_crawl_sitemap_seed_phase_completes_before_bfs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sitemap_url = "https://example.com/page-sitemap.xml"
    s1 = "https://example.com/s1"
    s2 = "https://example.com/s2"
    child = "https://example.com/child"
    link_graph = {
        s1: [child],
        s2: [],
        child: [],
    }

    call_order = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    async def fake_parse_sitemap(
        _url: str, _session: Any
    ) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        return [s1, s2], {s1: {}, s2: {}}, {}

    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.parse_sitemap",
        fake_parse_sitemap,
    )

    setup = _build_run_setup(target=sitemap_url)
    await execute_crawl(setup)

    visited = [url for url, _depth in call_order]
    assert visited[:2] == [s1, s2]
    assert visited[2:] == [child]


async def test_execute_crawl_sets_discovered_on_url_for_non_sitemap_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sitemap_url = "https://example.com/page-sitemap.xml"
    s1 = "https://example.com/s1"
    child = "https://example.com/child"
    link_graph = {
        s1: [child],
        child: [],
    }

    _ = _install_runner_mocks(monkeypatch, tmp_path, link_graph=link_graph)
    monkeypatch.setenv("HF_MAX_DEPTH", "5")

    async def fake_parse_sitemap(
        _url: str, _session: Any
    ) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        return [s1], {s1: {}}, {}

    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner.parse_sitemap",
        fake_parse_sitemap,
    )

    setup = _build_run_setup(target=sitemap_url)
    result = await execute_crawl(setup)
    by_url = {
        str(row.main.values.get("URL")): row
        for row in load_crawl_row_payloads(result)
    }

    assert by_url[s1].main.values.get("Discovered On URL") == ""
    assert by_url[child].main.values.get("Discovered On URL") == s1
    assert by_url[child].extra.values.get("Discovered On URL") == s1
