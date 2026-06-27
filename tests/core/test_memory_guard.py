"""D1 memory guard tests."""
from __future__ import annotations

import pytest

from hype_frog.core.memory_guard import (
    MemoryLimitExceeded,
    check_memory_limit,
    estimate_crawl_memory_mb,
)


def test_estimate_crawl_memory_scales_with_url_count() -> None:
    assert estimate_crawl_memory_mb(0) == 0.0
    assert estimate_crawl_memory_mb(1000) == 500.0


def test_check_memory_limit_no_op_when_unset() -> None:
    check_memory_limit(None)
    check_memory_limit(0)


def test_check_memory_limit_raises_when_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hype_frog.core.memory_guard.get_process_rss_mb",
        lambda: 3000.0,
    )
    with pytest.raises(MemoryLimitExceeded):
        check_memory_limit(2048)
