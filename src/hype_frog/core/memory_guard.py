"""Crawl memory estimation and RSS guardrails (D1)."""

from __future__ import annotations

import gc
import sys
from typing import Any

from hype_frog.core import get_logger

logger = get_logger(__name__)

_BYTES_PER_URL_ESTIMATE = 512 * 1024  # ~0.5 MiB per URL (link inventory + row payloads)
_WARN_ESTIMATE_MB = 2048
_MEMORY_CIRCUIT_BREAKER_MB = 2048


def estimate_crawl_memory_mb(url_count: int) -> float:
    """Rough RSS estimate before a crawl starts."""
    return round(max(0, url_count) * (_BYTES_PER_URL_ESTIMATE / (1024 * 1024)), 1)


def warn_if_large_crawl(url_count: int) -> None:
    """Log a warning when estimated memory exceeds the enterprise threshold."""
    estimated = estimate_crawl_memory_mb(url_count)
    if estimated >= _WARN_ESTIMATE_MB:
        logger.warning(
            "Estimated crawl memory ~%.0f MB for %s URLs (threshold %s MB). "
            "Consider --mode fast, a URL cap, or --streaming for cache-first writes.",
            estimated,
            url_count,
            _WARN_ESTIMATE_MB,
        )


def get_process_rss_mb() -> float | None:
    """Best-effort current process RSS in megabytes."""
    if sys.platform == "win32":
        try:
            import ctypes
            import os
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            process_query_information = 0x0400
            process_vm_read = 0x0010
            handle = kernel32.OpenProcess(
                process_query_information | process_vm_read,
                False,
                os.getpid(),
            )
            if not handle:
                return None
            try:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                if not psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    return None
                return counters.WorkingSetSize / (1024 * 1024)
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = float(usage.ru_maxrss)
        if sys.platform == "darwin":
            return rss / (1024 * 1024)
        return rss / 1024
    except Exception:
        return None


class MemoryLimitExceeded(RuntimeError):
    """Raised when RSS exceeds ``max_memory_mb``."""


def check_memory_limit(max_memory_mb: int | None) -> None:
    """Abort the crawl when RSS exceeds the configured cap."""
    if max_memory_mb is None or max_memory_mb <= 0:
        return
    rss = get_process_rss_mb()
    if rss is None:
        return
    if rss > float(max_memory_mb):
        raise MemoryLimitExceeded(
            f"Process RSS {rss:.0f} MB exceeds --max-memory-mb={max_memory_mb}"
        )


def memory_circuit_breaker(
    threshold_mb: float = _MEMORY_CIRCUIT_BREAKER_MB,
) -> float | None:
    """Log and run ``gc.collect()`` when RSS crosses the soft threshold."""
    rss = get_process_rss_mb()
    if rss is None or rss < threshold_mb:
        return rss
    logger.warning(
        "Process RSS %.0f MB exceeds soft threshold %.0f MB; running gc.collect()",
        rss,
        threshold_mb,
    )
    gc.collect()
    return get_process_rss_mb()


def payload_rows_from_cache(cache: Any) -> list[dict[str, dict[str, Any]]]:
    """Materialise crawl rows from SQLite cache (streaming-friendly reload)."""
    return list(cache.iter_results())


__all__ = [
    "MemoryLimitExceeded",
    "check_memory_limit",
    "estimate_crawl_memory_mb",
    "get_process_rss_mb",
    "memory_circuit_breaker",
    "payload_rows_from_cache",
    "warn_if_large_crawl",
]
