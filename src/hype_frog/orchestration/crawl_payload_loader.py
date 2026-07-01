"""Load crawl row payloads from in-memory lists or the SQLite audit cache."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from hype_frog.core.memory_guard import memory_circuit_breaker
from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.rules.scoring import align_extraction_state_from_main

_DEFAULT_CHUNK_SIZE = 500


class _CrawlResultLike(Protocol):
    crawl_rows: list[CrawlRowPayload]
    audit_cache: Any | None
    crawl_row_count: int


def crawl_row_count(crawl_result: _CrawlResultLike) -> int:
    if crawl_result.crawl_rows:
        return len(crawl_result.crawl_rows)
    if crawl_result.crawl_row_count:
        return crawl_result.crawl_row_count
    if crawl_result.audit_cache is not None:
        return crawl_result.audit_cache.row_count()
    return 0


def _payload_from_cached(cached: dict[str, object]) -> CrawlRowPayload:
    return CrawlRowPayload.model_validate(
        {"main": cached.get("main", {}), "extra": cached.get("extra", {})}
    )


def iter_crawl_payload_chunks(
    crawl_result: _CrawlResultLike,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> Iterator[list[CrawlRowPayload]]:
    """Yield crawl payloads in bounded batches without materialising the full crawl set."""
    if crawl_result.crawl_rows:
        rows = crawl_result.crawl_rows
        for start in range(0, len(rows), chunk_size):
            yield list(rows[start : start + chunk_size])
        return
    cache = crawl_result.audit_cache
    if cache is None:
        return
    for raw_chunk in cache.iter_results_chunked(chunk_size):
        chunk = [_payload_from_cached(cached) for cached in raw_chunk]
        raw_chunk.clear()
        memory_circuit_breaker()
        yield chunk


def iter_enrichment_row_chunks(
    crawl_result: _CrawlResultLike,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> Iterator[tuple[list[MainRowPayload], list[ExtraRowPayload]]]:
    """Yield aligned main/extra row batches for chunked enrichment passes."""
    for chunk in iter_crawl_payload_chunks(crawl_result, chunk_size=chunk_size):
        main_chunk = [row.main for row in chunk]
        extra_chunk = [row.extra for row in chunk]
        chunk.clear()
        yield main_chunk, extra_chunk


def sync_enrichment_row_extraction_states(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
) -> None:
    """Align extra ``Extraction State`` with main when crawl payloads desync."""
    for main_row, extra_row in zip(main_rows, extra_rows, strict=False):
        align_extraction_state_from_main(extra_row.values, main_row.values)


def load_enrichment_row_pairs(
    crawl_result: _CrawlResultLike,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> tuple[list[MainRowPayload], list[ExtraRowPayload]]:
    """Stream crawl rows into main/extra lists without a ``crawl_rows`` intermediate."""
    main_rows: list[MainRowPayload] = []
    extra_rows: list[ExtraRowPayload] = []
    for main_chunk, extra_chunk in iter_enrichment_row_chunks(
        crawl_result, chunk_size=chunk_size
    ):
        main_rows.extend(main_chunk)
        extra_rows.extend(extra_chunk)
        main_chunk.clear()
        extra_chunk.clear()
    sync_enrichment_row_extraction_states(main_rows, extra_rows)
    return main_rows, extra_rows


def load_crawl_row_payloads(
    crawl_result: _CrawlResultLike,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> list[CrawlRowPayload]:
    if crawl_result.crawl_rows:
        return list(crawl_result.crawl_rows)
    rows: list[CrawlRowPayload] = []
    for chunk in iter_crawl_payload_chunks(crawl_result, chunk_size=chunk_size):
        rows.extend(chunk)
        chunk.clear()
    return rows


def release_audit_cache(crawl_result: _CrawlResultLike) -> None:
    if crawl_result.audit_cache is None:
        return
    crawl_result.audit_cache.close(cleanup_file=True)


__all__ = [
    "crawl_row_count",
    "iter_crawl_payload_chunks",
    "iter_enrichment_row_chunks",
    "load_crawl_row_payloads",
    "load_enrichment_row_pairs",
    "sync_enrichment_row_extraction_states",
    "release_audit_cache",
]
