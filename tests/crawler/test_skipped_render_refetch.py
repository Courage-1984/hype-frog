"""Unit tests for :mod:`hype_frog.crawler.skipped_render_refetch`.

Covers the candidate-selection contract (skip already-scorable rows, apply
the skip contract directly to non-200 rows without a Playwright re-fetch),
the Playwright re-fetch outcome handling (no-html fallback, successful
re-render marking a row scorable again, exceptions being caught so one bad
URL never aborts the batch), and the aggregated attempted/rescored counts.

Playwright and HTML re-assembly are mocked — no live browser, no real HTML
parsing — matching the project convention of driving async code with
``asyncio.run`` inside plain ``def test_...`` functions (see
``tests/crawler/test_network_engine.py``).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.crawler import skipped_render_refetch as module
from hype_frog.crawler.skipped_render_refetch import (
    _refetch_row_with_playwright,
    refetch_skipped_render_urls,
)


class _FakeSessionManager:
    """Async context manager stand-in for ``PlaywrightSessionManager``."""

    entered = False

    async def __aenter__(self) -> "_FakeSessionManager":
        _FakeSessionManager.entered = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def _row_pair(*, status_code: object, extraction_state: str, url: str = "https://example.com/a") -> tuple[MainRowPayload, ExtraRowPayload]:
    main_row = MainRowPayload(values={"URL": url, "Extraction State": extraction_state, "Title": "Existing Title"})
    extra_row = ExtraRowPayload(
        values={
            "URL": url,
            "Extraction State": extraction_state,
            "Status Code": status_code,
            "Title": "Existing Title",
        }
    )
    return main_row, extra_row


def test_scorable_rows_are_never_candidates_for_refetch() -> None:
    """Rows already ``complete``/``partial`` must not trigger a Playwright session."""
    main_row, extra_row = _row_pair(status_code=200, extraction_state="complete")
    _FakeSessionManager.entered = False
    with patch.object(module, "PlaywrightSessionManager", _FakeSessionManager):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))
    assert result == {"attempted": 0, "rescored": 0}
    assert _FakeSessionManager.entered is False


def test_non_200_skipped_row_applies_skip_contract_without_fetching() -> None:
    """A skipped row that never even returned HTTP 200 is not fetch-worthy —
    the skip contract nulls it out directly and Playwright is never opened."""
    main_row, extra_row = _row_pair(status_code=404, extraction_state="skipped")
    _FakeSessionManager.entered = False
    with patch.object(module, "PlaywrightSessionManager", _FakeSessionManager):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))
    assert result == {"attempted": 0, "rescored": 0}
    assert _FakeSessionManager.entered is False
    # Skip contract nulls HTML-derived fields but preserves URL/Status Code/state.
    assert main_row.values["Title"] is None
    assert extra_row.values["Status Code"] == 404


def test_successful_rerender_marks_row_scorable_and_clears_skip_reason() -> None:
    main_row, extra_row = _row_pair(status_code=200, extraction_state="skipped")
    extra_row.values["skip_reason"] = "render_crash"

    diagnostics = {
        "html": "<html><body>ok</body></html>",
        "response_headers": {"Content-Type": "text/html"},
        "extraction_source": "rendered_browser",
        "extraction_state": "complete",
        "is_js_dependent": True,
        "raw_word_count": 10,
        "rendered_word_count": 42,
        "field_lcp_ms": 1800.0,
        "field_cls": 0.05,
    }

    with (
        patch.object(module, "PlaywrightSessionManager", _FakeSessionManager),
        patch.object(module, "fetch_rendered_with_diagnostics", new=AsyncMock(return_value=diagnostics)),
        patch.object(module, "_assemble_row_from_html_sync") as mock_assemble,
        patch.object(module, "finalize_row_state") as mock_finalize,
        patch.object(module, "backfill_extra_content_hub_metrics") as mock_backfill,
    ):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))

    assert result == {"attempted": 1, "rescored": 1}
    assert main_row.values["Extraction State"] == "complete"
    assert extra_row.values["Extraction State"] == "complete"
    assert extra_row.values["Extraction Source"] == "rendered_browser"
    assert extra_row.values["Extraction Source Fallback"] is False
    assert "skip_reason" not in extra_row.values
    assert extra_row.values["JS Dependent"] is True
    assert extra_row.values["Raw Words"] == 10
    assert extra_row.values["Rendered Words"] == 42
    mock_assemble.assert_called_once()
    mock_finalize.assert_called_once()
    mock_backfill.assert_called_once()


def test_rerender_still_skipped_is_not_counted_as_rescored() -> None:
    """A re-render that still yields ``skipped`` (e.g. render crash again)
    must not be counted as a win, even though HTML came back."""
    main_row, extra_row = _row_pair(status_code=200, extraction_state="skipped")
    diagnostics = {
        "html": "<html></html>",
        "response_headers": {},
        "extraction_source": "rendered_browser",
        "extraction_state": "skipped",
    }
    with (
        patch.object(module, "PlaywrightSessionManager", _FakeSessionManager),
        patch.object(module, "fetch_rendered_with_diagnostics", new=AsyncMock(return_value=diagnostics)),
        patch.object(module, "_assemble_row_from_html_sync"),
        patch.object(module, "finalize_row_state"),
        patch.object(module, "backfill_extra_content_hub_metrics"),
    ):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))
    assert result == {"attempted": 1, "rescored": 0}


def test_no_html_in_diagnostics_falls_back_to_skip_contract() -> None:
    main_row, extra_row = _row_pair(status_code=200, extraction_state="skipped")
    diagnostics: dict[str, Any] = {"html": None}
    with (
        patch.object(module, "PlaywrightSessionManager", _FakeSessionManager),
        patch.object(module, "fetch_rendered_with_diagnostics", new=AsyncMock(return_value=diagnostics)),
    ):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))
    assert result == {"attempted": 1, "rescored": 0}
    assert main_row.values["Title"] is None


def test_exception_during_refetch_is_caught_and_row_marked_skipped() -> None:
    """One URL blowing up (e.g. a Playwright crash) must not abort the batch
    — the row falls back to the skip contract and the loop continues."""
    main_row, extra_row = _row_pair(status_code=200, extraction_state="skipped")
    with (
        patch.object(module, "PlaywrightSessionManager", _FakeSessionManager),
        patch.object(
            module,
            "fetch_rendered_with_diagnostics",
            new=AsyncMock(side_effect=RuntimeError("browser crashed")),
        ),
    ):
        result = asyncio.run(refetch_skipped_render_urls([main_row], [extra_row]))
    assert result == {"attempted": 1, "rescored": 0}
    assert main_row.values["Title"] is None


def test_rescored_count_aggregates_across_multiple_candidates() -> None:
    main_a, extra_a = _row_pair(status_code=200, extraction_state="skipped", url="https://example.com/a")
    main_b, extra_b = _row_pair(status_code=200, extraction_state="skipped", url="https://example.com/b")

    ok_diagnostics = {
        "html": "<html></html>",
        "response_headers": {},
        "extraction_source": "rendered_browser",
        "extraction_state": "complete",
    }

    async def _fake_diagnostics(target_url: str, **_kwargs: Any) -> dict[str, Any]:
        if target_url.endswith("/b"):
            raise RuntimeError("boom")
        return ok_diagnostics

    with (
        patch.object(module, "PlaywrightSessionManager", _FakeSessionManager),
        patch.object(module, "fetch_rendered_with_diagnostics", new=_fake_diagnostics),
        patch.object(module, "_assemble_row_from_html_sync"),
        patch.object(module, "finalize_row_state"),
        patch.object(module, "backfill_extra_content_hub_metrics"),
    ):
        result = asyncio.run(
            refetch_skipped_render_urls([main_a, main_b], [extra_a, extra_b])
        )
    assert result == {"attempted": 2, "rescored": 1}


def test_refetch_row_returns_false_for_blank_url() -> None:
    """Direct unit test of the per-row helper: a blank URL must short-circuit
    before any fetch is attempted."""
    main_row = MainRowPayload(values={"URL": "", "Extraction State": "skipped"})
    extra_row = ExtraRowPayload(values={"URL": "", "Extraction State": "skipped"})
    _FakeSessionManager.entered = False
    with patch.object(
        module, "fetch_rendered_with_diagnostics", new=AsyncMock(side_effect=AssertionError("should not fetch"))
    ):
        result = asyncio.run(
            _refetch_row_with_playwright(
                main_row=main_row,
                extra_row=extra_row,
                render_wait_ms=1,
                selector_wait_ms=1,
                playwright_session_manager=_FakeSessionManager(),
            )
        )
    assert result is False
