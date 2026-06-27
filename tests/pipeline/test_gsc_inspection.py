"""B4 GSC URL Inspection field projection tests."""
from __future__ import annotations

from hype_frog.pipeline.gsc_inspection import (
    parse_gsc_inspection_payload,
    select_gsc_inspection_urls,
)


def test_parse_inspection_payload_maps_b4_columns() -> None:
    payload = {
        "inspectionResult": {
            "indexStatusResult": {
                "verdict": "FAIL",
                "coverageState": "Crawled - currently not indexed",
                "lastCrawlTime": "2026-06-01T12:00:00Z",
            },
            "mobileUsabilityResult": {"verdict": "FAIL"},
            "richResultsResult": {"verdict": "FAIL"},
        }
    }
    fields = parse_gsc_inspection_payload(payload)
    assert fields["GSC Index Status"] == "NOT_INDEXED"
    assert fields["GSC Mobile Usability"] == "NOT_MOBILE_FRIENDLY"
    assert fields["GSC Rich Result Status"] == "INVALID"
    assert fields["GSC Coverage Reason"] == "Crawled - currently not indexed"
    assert fields["GSC Last Crawl Date"] == "2026-06-01"
    assert isinstance(fields["Days Since Last Crawl"], int)


def test_select_gsc_inspection_urls_limited_cap() -> None:
    urls = [f"https://example.com/{index}" for index in range(100)]
    limited = select_gsc_inspection_urls(urls, mode="limited", limit=50)
    assert len(limited) == 50
    assert select_gsc_inspection_urls(urls, mode="full") == urls
    assert select_gsc_inspection_urls(urls, mode="") == []
