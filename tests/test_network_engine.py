"""Unit tests for :mod:`hype_frog.crawler.network_engine` Sprint 2 surface.

Covers:

* The Poisson jitter helper — proves that ``mean_seconds=0`` short-circuits
  to ``0.0`` so the test suite (and any caller that opts out) never sleeps.
* The raw-vs-rendered diff helpers — proves ``None`` / empty inputs do not
  raise ``NoneType`` errors and that the JS-dependence heuristic behaves
  monotonically on the obvious cases.
* The ``PerformanceObserver`` field-metric coercion — proves we accept JS
  numbers, reject ``NaN``/``inf``/``None``/non-numerics.
* ``fetch_rendered_with_diagnostics`` end-to-end against a fully mocked
  ``PlaywrightSessionManager`` so we exercise the full pipeline without
  launching Chromium and without needing ``pytest-asyncio``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hype_frog.crawler.network_engine import (  # noqa: E402
    PlaywrightSessionManager,
    RenderedFetchDiagnostics,
    _apply_jitter_delay,
    _coerce_field_metric,
    _compute_is_js_dependent,
    _compute_render_diagnostics,
    _empty_diagnostics,
    _poisson_jitter_seconds,
    _strip_html_to_text,
    _word_count,
    fetch_rendered,
    fetch_rendered_with_diagnostics,
)


# ---------------------------------------------------------------------------
# Poisson jitter — bypass guarantees
# ---------------------------------------------------------------------------


def test_poisson_jitter_zero_returns_zero() -> None:
    assert _poisson_jitter_seconds(0.0) == 0.0


def test_poisson_jitter_negative_returns_zero() -> None:
    assert _poisson_jitter_seconds(-1.5) == 0.0


def test_poisson_jitter_non_numeric_returns_zero() -> None:
    assert _poisson_jitter_seconds("not-a-number") == 0.0  # type: ignore[arg-type]
    assert _poisson_jitter_seconds(None) == 0.0  # type: ignore[arg-type]


def test_poisson_jitter_positive_is_finite_positive() -> None:
    samples = [_poisson_jitter_seconds(0.5) for _ in range(50)]
    assert all(sample > 0.0 for sample in samples)
    assert all(sample == sample for sample in samples)  # not NaN
    assert all(sample != float("inf") for sample in samples)


def test_apply_jitter_zero_does_not_sleep() -> None:
    with patch(
        "hype_frog.crawler.network_engine.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock:
        delay = asyncio.run(_apply_jitter_delay(0.0))
    assert delay == 0.0
    sleep_mock.assert_not_awaited()


def test_apply_jitter_positive_invokes_sleep() -> None:
    with patch(
        "hype_frog.crawler.network_engine.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock:
        delay = asyncio.run(_apply_jitter_delay(0.25))
    assert delay > 0.0
    sleep_mock.assert_awaited_once()
    awaited_with = sleep_mock.await_args.args[0]
    assert awaited_with == delay


# ---------------------------------------------------------------------------
# Raw-vs-rendered helpers — NoneType safety
# ---------------------------------------------------------------------------


def test_strip_html_handles_none_and_empty() -> None:
    assert _strip_html_to_text(None) == ""
    assert _strip_html_to_text("") == ""


def test_strip_html_drops_script_and_style() -> None:
    html = "<p>visible</p><script>var x = 1;</script><style>.x{color:red}</style>"
    assert _strip_html_to_text(html) == "visible"


def test_word_count_handles_none_and_empty() -> None:
    assert _word_count(None) == 0
    assert _word_count("") == 0
    assert _word_count("   ") == 0


def test_word_count_basic() -> None:
    assert _word_count("<p>Hello world from Hype Frog</p>") == 5


def test_compute_is_js_dependent_handles_none() -> None:
    assert _compute_is_js_dependent(None, None) is False
    assert _compute_is_js_dependent(0, None) is False
    assert _compute_is_js_dependent(None, 0) is False


def test_compute_is_js_dependent_obvious_case() -> None:
    assert _compute_is_js_dependent(raw_count=10, rendered_count=200) is True


def test_compute_is_js_dependent_no_change() -> None:
    assert _compute_is_js_dependent(raw_count=120, rendered_count=120) is False


def test_compute_is_js_dependent_relative_threshold() -> None:
    # raw=100, rendered=160 -> delta=60, ratio=0.6 -> JS-dependent
    assert _compute_is_js_dependent(raw_count=100, rendered_count=160) is True
    # raw=100, rendered=140 -> delta=40, ratio=0.4 -> NOT JS-dependent
    assert _compute_is_js_dependent(raw_count=100, rendered_count=140) is False


def test_compute_is_js_dependent_empty_raw_floor() -> None:
    # raw=0, rendered>=50 -> JS-only page heuristic trips
    assert _compute_is_js_dependent(raw_count=0, rendered_count=51) is True
    assert _compute_is_js_dependent(raw_count=0, rendered_count=10) is False


# ---------------------------------------------------------------------------
# Field-metric coercion
# ---------------------------------------------------------------------------


def test_coerce_field_metric_accepts_numbers() -> None:
    assert _coerce_field_metric(0) == 0.0
    assert _coerce_field_metric(123.4) == 123.4


def test_coerce_field_metric_rejects_invalid() -> None:
    assert _coerce_field_metric(None) is None
    assert _coerce_field_metric("oops") is None
    assert _coerce_field_metric(True) is None  # bool is not a numeric metric
    assert _coerce_field_metric(float("nan")) is None
    assert _coerce_field_metric(float("inf")) is None


# ---------------------------------------------------------------------------
# Aggregator: _compute_render_diagnostics never raises on None inputs
# ---------------------------------------------------------------------------


def test_compute_render_diagnostics_all_none_inputs() -> None:
    diag = _compute_render_diagnostics(
        raw_html=None,
        rendered_html=None,
        field_metrics=None,
        extraction_source="raw_http",
        extraction_state="partial",
        response_headers=None,
    )
    assert diag["html"] is None
    assert diag["raw_html"] is None
    assert diag["raw_word_count"] == 0
    assert diag["rendered_word_count"] == 0
    assert diag["is_js_dependent"] is False
    assert diag["field_lcp_ms"] is None
    assert diag["field_cls"] is None
    assert diag["response_headers"] == {}
    assert diag["extraction_source"] == "raw_http"
    assert diag["extraction_state"] == "partial"


def test_compute_render_diagnostics_happy_path() -> None:
    raw = "<html><body><p>" + ("word " * 20).strip() + "</p></body></html>"
    rendered = "<html><body><p>" + ("word " * 200).strip() + "</p></body></html>"
    diag = _compute_render_diagnostics(
        raw_html=raw,
        rendered_html=rendered,
        field_metrics={"lcp": 2400.5, "cls": 0.07},
        extraction_source="rendered_browser",
        extraction_state="complete",
        response_headers={"Content-Type": "text/html"},
    )
    assert diag["raw_word_count"] == 20
    assert diag["rendered_word_count"] == 200
    assert diag["is_js_dependent"] is True
    assert diag["field_lcp_ms"] == 2400.5
    assert diag["field_cls"] == 0.07
    assert diag["response_headers"] == {"Content-Type": "text/html"}


def test_compute_render_diagnostics_partial_metrics() -> None:
    diag = _compute_render_diagnostics(
        raw_html="<p>hi</p>",
        rendered_html="<p>hi</p>",
        field_metrics={"lcp": float("nan"), "cls": None},
        extraction_source="rendered_browser",
        extraction_state="partial",
        response_headers={},
    )
    assert diag["field_lcp_ms"] is None
    assert diag["field_cls"] is None
    assert diag["is_js_dependent"] is False


def test_empty_diagnostics_returns_safe_defaults() -> None:
    diag = _empty_diagnostics("partial")
    assert diag["html"] is None
    assert diag["raw_html"] is None
    assert diag["extraction_source"] == "raw_http"
    assert diag["extraction_state"] == "partial"
    assert diag["raw_word_count"] == 0
    assert diag["rendered_word_count"] == 0
    assert diag["is_js_dependent"] is False


# ---------------------------------------------------------------------------
# fetch_rendered_with_diagnostics: full pipeline against a mocked manager
# ---------------------------------------------------------------------------


def _make_mock_session_manager(
    *,
    rendered_html: str | None = "<html><body><p>rendered word " * 80 + "</p></body></html>",
    raw_html: str | None = "<html><body><p>raw</p></body></html>",
    field_metrics: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Construct a mock session manager whose context yields a mock page."""
    nav_response = MagicMock()
    nav_response.headers = headers or {"content-type": "text/html"}
    nav_response.text = AsyncMock(return_value=raw_html)

    page = MagicMock()
    page.goto = AsyncMock(return_value=nav_response)
    page.wait_for_load_state = AsyncMock(return_value=None)
    page.wait_for_timeout = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock(return_value=None)
    page.content = AsyncMock(return_value=rendered_html)
    page.evaluate = AsyncMock(return_value=field_metrics or {"lcp": 1800.0, "cls": 0.04})
    page.close = AsyncMock(return_value=None)

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)

    manager = MagicMock(spec=PlaywrightSessionManager)
    manager.get_context = AsyncMock(return_value=context)
    manager.aclose = AsyncMock(return_value=None)
    return manager


def test_fetch_rendered_with_diagnostics_happy_path() -> None:
    manager = _make_mock_session_manager()
    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = True
        diag = asyncio.run(
            fetch_rendered_with_diagnostics(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert diag["extraction_source"] == "rendered_browser"
    assert diag["extraction_state"] == "complete"
    assert diag["raw_word_count"] >= 1
    assert diag["rendered_word_count"] > diag["raw_word_count"]
    assert diag["is_js_dependent"] is True
    assert diag["field_lcp_ms"] == 1800.0
    assert diag["field_cls"] == 0.04
    # session_manager passed in -> caller owns lifecycle, aclose NOT called
    manager.aclose.assert_not_awaited()


def test_fetch_rendered_with_diagnostics_handles_missing_raw() -> None:
    """``nav_response.text()`` failure must NOT raise NoneType errors."""
    manager = _make_mock_session_manager(raw_html=None)
    # Force the .text() coroutine itself to raise.
    page_context = manager.get_context.return_value  # type: ignore[attr-defined]
    page = asyncio.run(page_context.new_page())
    page.goto.return_value.text = AsyncMock(side_effect=RuntimeError("body unavailable"))
    # Reset new_page to return the same primed page (not a fresh one).
    page_context.new_page = AsyncMock(return_value=page)

    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = True
        diag = asyncio.run(
            fetch_rendered_with_diagnostics(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert diag["raw_html"] is None
    assert diag["raw_word_count"] == 0
    assert diag["html"] is not None
    assert diag["rendered_word_count"] > 0


def test_fetch_rendered_with_diagnostics_handles_observer_failure() -> None:
    """``page.evaluate`` failure (CSP block) yields ``None`` field metrics, no crash."""
    manager = _make_mock_session_manager()
    page_context = manager.get_context.return_value  # type: ignore[attr-defined]
    page = asyncio.run(page_context.new_page())
    page.evaluate = AsyncMock(side_effect=RuntimeError("CSP blocked PerformanceObserver"))
    page_context.new_page = AsyncMock(return_value=page)

    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = True
        diag = asyncio.run(
            fetch_rendered_with_diagnostics(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert diag["field_lcp_ms"] is None
    assert diag["field_cls"] is None
    assert diag["html"] is not None  # rendered HTML still captured


def test_fetch_rendered_with_diagnostics_returns_fallback_when_probe_fails() -> None:
    manager = _make_mock_session_manager()
    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = False
        diag = asyncio.run(
            fetch_rendered_with_diagnostics(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert diag == _empty_diagnostics("partial")
    manager.get_context.assert_not_awaited()


def test_fetch_rendered_with_diagnostics_returns_fallback_when_context_unavailable() -> None:
    manager = MagicMock(spec=PlaywrightSessionManager)
    manager.get_context = AsyncMock(return_value=None)
    manager.aclose = AsyncMock(return_value=None)
    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = True
        diag = asyncio.run(
            fetch_rendered_with_diagnostics(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert diag["html"] is None
    assert diag["extraction_source"] == "raw_http"
    assert diag["extraction_state"] == "partial"


def test_fetch_rendered_jitter_zero_does_not_sleep() -> None:
    """``fetch_rendered`` with ``jitter_mean_seconds=0`` must skip the sleep."""
    manager = _make_mock_session_manager()
    with (
        patch(
            "hype_frog.crawler.network_engine._probe_subprocess_supported",
            new_callable=AsyncMock,
        ) as probe,
        patch(
            "hype_frog.crawler.network_engine.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep_mock,
    ):
        probe.return_value = True
        html, source, state, headers = asyncio.run(
            fetch_rendered(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    sleep_mock.assert_not_awaited()
    assert source == "rendered_browser"
    assert state in {"complete", "partial"}
    assert isinstance(headers, dict)
    assert html is not None


def test_fetch_rendered_returns_tuple_shape() -> None:
    """Backward-compat: the 4-tuple shape used by ``fetcher.py`` is preserved."""
    manager = _make_mock_session_manager()
    with patch(
        "hype_frog.crawler.network_engine._probe_subprocess_supported",
        new_callable=AsyncMock,
    ) as probe:
        probe.return_value = True
        result = asyncio.run(
            fetch_rendered(
                "https://example.com/",
                render_wait_ms=1000,
                selector_wait_ms=500,
                jitter_mean_seconds=0.0,
                session_manager=manager,
            )
        )
    assert isinstance(result, tuple) and len(result) == 4


def test_rendered_fetch_diagnostics_typed_dict_keys() -> None:
    """Smoke check the TypedDict keys are stable for downstream consumers."""
    expected = {
        "html",
        "raw_html",
        "extraction_source",
        "extraction_state",
        "response_headers",
        "field_lcp_ms",
        "field_cls",
        "raw_word_count",
        "rendered_word_count",
        "is_js_dependent",
    }
    assert set(RenderedFetchDiagnostics.__annotations__.keys()) == expected
