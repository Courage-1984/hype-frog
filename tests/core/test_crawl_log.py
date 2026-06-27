"""D7 crawl log collector tests."""
from __future__ import annotations

from hype_frog.core.crawl_log import CrawlLogCollector, crawl_log_sheet_rows


def test_crawl_log_collector_records_entry() -> None:
    collector = CrawlLogCollector()
    collector.record(
        url="https://example.com/page",
        phase="fetch",
        error_type="Timeout",
        error_detail="Request timed out",
        recovery_action="Status set to Timeout.",
    )
    rows = collector.to_row_dicts()
    assert len(rows) == 1
    assert rows[0]["Phase"] == "fetch"
    assert rows[0]["Error Type"] == "Timeout"


def test_crawl_log_sheet_rows_empty_summary() -> None:
    rows = crawl_log_sheet_rows([])
    assert len(rows) == 1
    assert rows[0]["Phase"] == "Summary"
