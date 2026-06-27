"""Sitemap QA row builder enhancements (C5)."""

from __future__ import annotations

from hype_frog.orchestration.export_registry import build_sitemapqa_rows


def test_build_sitemapqa_rows_skips_non_success_transport_status() -> None:
    """Transport failures (e.g. Timeout) must not crash export or count as crawled-missing."""
    rows = build_sitemapqa_rows(
        sitemap_meta={
            "https://example.com/timeout-page": {
                "lastmod": "",
                "changefreq": "",
                "priority": "",
                "source_sitemap": "https://example.com/sitemap.xml",
                "sitemap_kind": "urlset",
            },
            "https://example.com/in-sitemap": {
                "lastmod": "2026-06-01",
                "changefreq": "weekly",
                "priority": "0.8",
                "source_sitemap": "https://example.com/sitemap.xml",
                "sitemap_kind": "urlset",
            },
        },
        sitemap_files_meta={
            "https://example.com/sitemap.xml": {
                "kind": "urlset",
                "url_count": 2,
                "size_bytes": 1024,
                "is_index": False,
            }
        },
        extra_rows=[
            {
                "URL": "https://example.com/timeout-page",
                "Final URL": "https://example.com/timeout-page",
                "Status Code": "Timeout",
            },
            {
                "URL": "https://example.com/in-sitemap",
                "Final URL": "https://example.com/in-sitemap",
                "Status Code": 200,
            },
            {
                "URL": "https://example.com/not-listed",
                "Final URL": "https://example.com/not-listed",
                "Status Code": 200,
            },
        ],
    )
    timeout_row = next(
        row for row in rows if row.get("Sitemap URL") == "https://example.com/timeout-page"
    )
    assert timeout_row["In Sitemap but Non-200"] is True
    crawled_missing = [
        row for row in rows if row.get("Crawled but Missing from Sitemap") is True
    ]
    assert len(crawled_missing) == 1
    assert crawled_missing[0]["Sitemap URL"] == "https://example.com/not-listed"


def test_build_sitemapqa_rows_flags_crawled_missing_from_sitemap() -> None:
    rows = build_sitemapqa_rows(
        sitemap_meta={
            "https://example.com/in-sitemap": {
                "lastmod": "2026-06-01",
                "changefreq": "weekly",
                "priority": "0.8",
                "source_sitemap": "https://example.com/sitemap.xml",
                "sitemap_kind": "urlset",
            }
        },
        sitemap_files_meta={
            "https://example.com/sitemap.xml": {
                "kind": "urlset",
                "url_count": 1,
                "size_bytes": 2048,
                "is_index": False,
            }
        },
        extra_rows=[
            {
                "URL": "https://example.com/in-sitemap",
                "Final URL": "https://example.com/in-sitemap",
                "Status Code": 200,
                "HTTP Last-Modified": "2026-06-01",
                "Canonical URL": "https://example.com/in-sitemap",
            },
            {
                "URL": "https://example.com/not-listed",
                "Final URL": "https://example.com/not-listed",
                "Status Code": 200,
            },
        ],
    )
    crawled_missing = [
        row for row in rows if row.get("Crawled but Missing from Sitemap") is True
    ]
    assert len(crawled_missing) == 1
    assert crawled_missing[0]["Sitemap URL"] == "https://example.com/not-listed"
    file_rows = [row for row in rows if row.get("Record Type") == "Sitemap File"]
    assert file_rows[0]["Sitemap Size (KB)"] == 2.0
