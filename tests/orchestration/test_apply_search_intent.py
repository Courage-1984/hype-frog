"""Unit tests for ``orchestration.crawl_runner_bfs.apply_search_intent``.

Covers the LLM-then-heuristic fallback chain and the ``Search Intent Source``
provenance field: regression for the export where ``Search Intent`` was
"Unknown" on every URL because only the (unconfigured) LLM path existed.

Rule #2 (No Live Network): the ``IntentAnalyzer`` is a stand-in double;
no ``aiohttp`` session is constructed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload

# Import crawl_runner first: crawl_runner_bfs and crawl_runner import each
# other, and importing crawl_runner_bfs directly first hits the module while
# crawl_runner (which it also imports) is only partially initialised.
import hype_frog.orchestration.crawl_runner  # noqa: F401
from hype_frog.orchestration.crawl_runner_bfs import apply_search_intent


def _row(url: str, title: str = "", meta: str = "") -> CrawlRowPayload:
    return CrawlRowPayload(
        main=MainRowPayload(values={"URL": url, "Title": title, "Meta Description": meta}),
        extra=ExtraRowPayload(values={}),
    )


class _StubAnalyzer:
    def __init__(self, result: str) -> None:
        self._result = result
        self.analyze_intent = AsyncMock(return_value=result)


async def test_llm_hit_is_recorded_as_llm_source() -> None:
    row = _row("https://example.com/anything")
    await apply_search_intent(row, analyzer=_StubAnalyzer("Transactional"))
    assert row.extra.values["Search Intent"] == "Transactional"
    assert row.extra.values["Search Intent Source"] == "LLM"


async def test_llm_unknown_falls_back_to_heuristic() -> None:
    row = _row("https://example.com/pricing")
    await apply_search_intent(row, analyzer=_StubAnalyzer("Unknown"))
    assert row.extra.values["Search Intent"] == "Transactional"
    assert row.extra.values["Search Intent Source"] == "Heuristic"


async def test_llm_unknown_and_heuristic_unknown_stays_unknown() -> None:
    row = _row("https://example.com/random-slug-xyz")
    await apply_search_intent(row, analyzer=_StubAnalyzer("Unknown"))
    assert row.extra.values["Search Intent"] == "Unknown"
    assert row.extra.values["Search Intent Source"] == "Unknown"


async def test_analyzer_exception_sets_unknown_source_and_intent() -> None:
    row = _row("https://example.com/pricing")
    analyzer = _StubAnalyzer("Transactional")
    analyzer.analyze_intent = AsyncMock(side_effect=RuntimeError("boom"))
    await apply_search_intent(row, analyzer=analyzer)
    assert row.extra.values["Search Intent"] == "Unknown"
    assert row.extra.values["Search Intent Source"] == "Unknown"
