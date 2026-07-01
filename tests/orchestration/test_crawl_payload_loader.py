"""Tests for chunked crawl payload loading."""

from __future__ import annotations

from hype_frog.checkpoint.cache import AuditCache
from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.orchestration.crawl_payload_loader import (
    iter_crawl_payload_chunks,
    load_enrichment_row_pairs,
)


class _CacheResult:
    def __init__(self, cache: AuditCache) -> None:
        self.crawl_rows: list[CrawlRowPayload] = []
        self.audit_cache = cache
        self.crawl_row_count = 0


def _seed_cache(tmp_path, count: int) -> AuditCache:
    cache = AuditCache(str(tmp_path / "audit.sqlite"))
    batch = []
    for index in range(count):
        url = f"https://example.com/page-{index}/"
        batch.append(
            {
                "main": {"URL": url, "Title": f"Page {index}"},
                "extra": {"URL": url, "Extraction State": "complete", "Status Code": 200},
            }
        )
    cache.upsert_results(batch)
    return cache


def test_load_enrichment_row_pairs_syncs_main_extraction_to_extra(tmp_path) -> None:
    cache = AuditCache(str(tmp_path / "desync.sqlite"))
    cache.upsert_results(
        [
            {
                "main": {
                    "URL": "https://example.com/a/",
                    "Extraction State": "partial",
                },
                "extra": {
                    "URL": "https://example.com/a/",
                    "Extraction State": "skipped",
                    "Status Code": 200,
                },
            }
        ]
    )
    result = _CacheResult(cache)
    result.crawl_row_count = cache.row_count()

    _main_rows, extra_rows = load_enrichment_row_pairs(result)

    assert extra_rows[0].values["Extraction State"] == "partial"
    cache.close(cleanup_file=True)


def test_load_enrichment_row_pairs_streams_from_cache(tmp_path) -> None:
    cache = _seed_cache(tmp_path, 5)
    result = _CacheResult(cache)
    result.crawl_row_count = cache.row_count()

    main_rows, extra_rows = load_enrichment_row_pairs(result, chunk_size=2)

    assert len(main_rows) == 5
    assert len(extra_rows) == 5
    assert all(isinstance(row, MainRowPayload) for row in main_rows)
    assert all(isinstance(row, ExtraRowPayload) for row in extra_rows)
    cache.close(cleanup_file=True)


def test_iter_crawl_payload_chunks_yields_bounded_batches(tmp_path) -> None:
    cache = _seed_cache(tmp_path, 5)
    result = _CacheResult(cache)
    sizes = [len(chunk) for chunk in iter_crawl_payload_chunks(result, chunk_size=2)]
    cache.close(cleanup_file=True)

    assert sizes == [2, 2, 1]
