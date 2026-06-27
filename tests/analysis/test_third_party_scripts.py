"""Unit tests for third-party script inventory (A2)."""

from __future__ import annotations

from hype_frog.analysis.third_party_scripts import (
    build_script_inventory_rows,
    summarise_page_third_party_scripts,
)


def test_summarise_page_third_party_scripts_detects_known_services() -> None:
    summary = summarise_page_third_party_scripts(
        [
            {
                "url": "https://www.googletagmanager.com/gtm.js?id=G-1",
                "transferSize": 2048,
                "resourceType": "Script",
            },
            {
                "url": "https://connect.facebook.net/en_US/fbevents.js",
                "transferSize": 4096,
                "resourceType": "Script",
            },
        ],
        render_blocking_urls=["https://connect.facebook.net/en_US/fbevents.js"],
    )
    assert summary["Third Party Script Count"] == 2
    assert summary["Has Tag Manager"] is True
    assert summary["Has Meta Pixel"] is True
    assert summary["Third Party JS Blocking"] is True
    assert "Google Tag Manager" in str(summary["Third Party Scripts"])


def test_build_script_inventory_rows_aggregates_domains() -> None:
    rows = build_script_inventory_rows(
        [
            {
                "URL": "https://example.com/a",
                "PSI Network Items": [
                    {
                        "url": "https://static.hotjar.com/c/hotjar.js",
                        "transferSize": 1024,
                    }
                ],
                "PSI Render Blocking URLs": [],
            },
            {
                "URL": "https://example.com/b",
                "PSI Network Items": [
                    {
                        "url": "https://static.hotjar.com/c/hotjar.js",
                        "transferSize": 2048,
                    }
                ],
                "PSI Render Blocking URLs": [],
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["Service Name"] == "Hotjar"
    assert rows[0]["Pages Found On"] == 2
