"""D7 crawl log collector tests."""
from __future__ import annotations

from hype_frog.core.crawl_log import (
    CRAWL_LOG_COLUMNS,
    CrawlLogCollector,
    CrawlLogEntry,
    crawl_log_sheet_rows,
)


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


def test_crawl_log_collector_multiple_entries_to_row_dicts() -> None:
    collector = CrawlLogCollector()
    collector.record(
        url="https://example.com/a",
        phase="fetch",
        error_type="Timeout",
        error_detail="Request timed out",
    )
    collector.record(
        url="https://example.com/b",
        phase="extract",
        error_type="ParseError",
        error_detail="Malformed HTML",
    )
    rows = collector.to_row_dicts()
    assert len(rows) == 2
    assert rows[0]["URL"] == "https://example.com/a"
    assert rows[1]["URL"] == "https://example.com/b"


def test_crawl_log_sheet_rows_empty_summary() -> None:
    rows = crawl_log_sheet_rows([])
    assert len(rows) == 1
    assert rows[0]["Phase"] == "Summary"


def test_crawl_log_collector_skips_empty_detail_and_type() -> None:
    collector = CrawlLogCollector()
    collector.record(url="https://example.com/", phase="fetch", error_type="", error_detail="")
    assert collector.entries == []


def test_crawl_log_collector_records_with_explicit_timestamp() -> None:
    collector = CrawlLogCollector()
    collector.record(
        url="https://example.com/",
        phase="extract",
        error_type="ParseError",
        error_detail="Bad HTML",
        timestamp="2026-01-01 00:00:00 UTC",
    )
    assert collector.entries[0].timestamp == "2026-01-01 00:00:00 UTC"


def test_crawl_log_collector_recovery_action_none_in_row() -> None:
    collector = CrawlLogCollector()
    collector.record(
        url="https://example.com/",
        phase="fetch",
        error_type="Timeout",
        error_detail="timed out",
        recovery_action="",
    )
    rows = collector.to_row_dicts()
    assert rows[0]["Recovery Action Taken"] is None


def test_crawl_log_sheet_rows_with_real_entries() -> None:
    entry = CrawlLogEntry(
        timestamp="2026-01-01 00:00:00 UTC",
        url="https://example.com/",
        phase="fetch",
        error_type="Timeout",
        error_detail="Request timed out",
    )
    rows = crawl_log_sheet_rows([entry])
    assert len(rows) == 1
    assert rows[0]["Error Type"] == "Timeout"


def test_crawl_log_columns_tuple_covers_expected_headers() -> None:
    assert "Timestamp" in CRAWL_LOG_COLUMNS
    assert "URL" in CRAWL_LOG_COLUMNS
    assert "Error Type" in CRAWL_LOG_COLUMNS
