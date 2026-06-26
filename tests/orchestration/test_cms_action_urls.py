"""CMS Action URLs export tab builder."""

from __future__ import annotations

from hype_frog.orchestration.crawl_runner import ExcludedCmsActionUrl
from hype_frog.orchestration.export_registry import (
    CMS_ACTION_URLS_COLUMNS,
    build_cms_action_url_rows,
)


def test_build_cms_action_url_rows_merges_crawl_and_internal_links() -> None:
    crawl_exclusions = (
        ExcludedCmsActionUrl(
            url="https://example.com/sitemap-cart?add-to-cart=1",
            excluded_query_params=("add-to-cart",),
            discovered_on_url="Sitemap",
        ),
    )
    extra_rows = [
        {
            "URL": "https://example.com/shop",
            "Internal Links List Full": [
                "https://example.com/product/a?add-to-cart=2",
                "https://example.com/blog?page=2",
            ],
        }
    ]
    rows = build_cms_action_url_rows(crawl_exclusions, extra_rows)
    assert len(rows) == 2
    assert list(rows[0].keys()) == CMS_ACTION_URLS_COLUMNS
    urls = {str(row["URL"]) for row in rows}
    assert "https://example.com/sitemap-cart?add-to-cart=1" in urls
    assert "https://example.com/product/a?add-to-cart=2" in urls
    shop_row = next(
        row for row in rows if "product/a" in str(row["URL"])
    )
    assert shop_row["Discovered On URL"] == "https://example.com/shop"
    assert shop_row["Excluded Query Parameters"] == "add-to-cart"
