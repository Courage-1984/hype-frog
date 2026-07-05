"""Direct tests for crawl_runner_frontier.py (URL eligibility, CMS exclusions, link discovery).

Previously only exercised indirectly through crawl_runner.py's BFS loop tests.
"""

from __future__ import annotations

from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.orchestration.crawl_runner_frontier import (
    ExcludedCmsActionUrl,
    candidate_internal_links,
    cms_action_exclusion_keys,
    is_crawlable_html_candidate,
    register_cms_exclusion,
)


def _payload(url: str, *, links: list[str] | None = None) -> CrawlRowPayload:
    main = MainRowPayload.model_validate({"URL": url})
    extra = ExtraRowPayload.model_validate(
        {"URL": url, "Internal Links List Full": links or []}
    )
    return CrawlRowPayload(main=main, extra=extra)


def test_cms_action_exclusion_keys_matches_known_param() -> None:
    keys = cms_action_exclusion_keys("https://example.com/cart?add-to-cart=42")
    assert "add-to-cart" in keys


def test_cms_action_exclusion_keys_empty_for_plain_url() -> None:
    assert cms_action_exclusion_keys("https://example.com/about") == frozenset()


def test_cms_action_exclusion_keys_empty_for_no_query() -> None:
    assert cms_action_exclusion_keys("https://example.com/") == frozenset()


def test_register_cms_exclusion_adds_entry() -> None:
    registry: dict[str, ExcludedCmsActionUrl] = {}
    register_cms_exclusion(
        registry, "https://example.com/cart?add-to-cart=1", "https://example.com/shop"
    )
    assert len(registry) == 1
    entry = next(iter(registry.values()))
    assert entry.excluded_query_params == ("add-to-cart",)
    assert entry.discovered_on_url == "https://example.com/shop"


def test_register_cms_exclusion_noop_for_non_cms_url() -> None:
    registry: dict[str, ExcludedCmsActionUrl] = {}
    register_cms_exclusion(registry, "https://example.com/about", "https://example.com/")
    assert registry == {}


def test_register_cms_exclusion_does_not_duplicate() -> None:
    registry: dict[str, ExcludedCmsActionUrl] = {}
    register_cms_exclusion(
        registry, "https://example.com/cart?add-to-cart=1", "https://example.com/a"
    )
    register_cms_exclusion(
        registry, "https://example.com/cart?add-to-cart=1", "https://example.com/b"
    )
    assert len(registry) == 1
    # First-registered discovered_on_url wins; not overwritten by the second call.
    assert next(iter(registry.values())).discovered_on_url == "https://example.com/a"


def test_is_crawlable_html_candidate_rejects_binary_extension() -> None:
    assert is_crawlable_html_candidate("https://example.com/report.pdf") is False
    assert is_crawlable_html_candidate("https://example.com/photo.jpg") is False


def test_is_crawlable_html_candidate_accepts_plain_page() -> None:
    assert is_crawlable_html_candidate("https://example.com/about") is True


def test_is_crawlable_html_candidate_rejects_cms_action_url() -> None:
    assert is_crawlable_html_candidate("https://example.com/cart?add-to-cart=1") is False


def test_is_crawlable_html_candidate_rejects_missing_scheme_or_host() -> None:
    assert is_crawlable_html_candidate("not-a-url") is False
    assert is_crawlable_html_candidate("") is False


def test_candidate_internal_links_filters_binary_and_cms_urls() -> None:
    row = _payload(
        "https://example.com/",
        links=[
            "https://example.com/about",
            "https://example.com/image.png",
            "https://example.com/cart?add-to-cart=1",
            "https://example.com/blog",
        ],
    )
    links = candidate_internal_links(row)
    assert links == ["https://example.com/about", "https://example.com/blog"]


def test_candidate_internal_links_registers_cms_exclusions_when_tracked() -> None:
    exclusions: dict[str, ExcludedCmsActionUrl] = {}
    row = _payload(
        "https://example.com/shop",
        links=["https://example.com/cart?add-to-cart=1"],
    )
    links = candidate_internal_links(row, exclusions)
    assert links == []
    assert len(exclusions) == 1
    assert next(iter(exclusions.values())).discovered_on_url == "https://example.com/shop"


def test_candidate_internal_links_handles_non_list_field_gracefully() -> None:
    main = MainRowPayload.model_validate({"URL": "https://example.com/"})
    extra = ExtraRowPayload.model_validate(
        {"URL": "https://example.com/", "Internal Links List Full": "not-a-list"}
    )
    row = CrawlRowPayload(main=main, extra=extra)
    assert candidate_internal_links(row) == []
