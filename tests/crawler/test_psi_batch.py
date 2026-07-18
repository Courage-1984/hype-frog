"""Unit tests for :mod:`hype_frog.crawler.psi_batch`.

Covers the pacing/retry/fallback contract documented in
``.cursor/rules/crawler_engine.mdc``: ``PsiRequestPacer`` serialises minimum
spacing between requests; ``fetch_strategy_raw`` retries retryable statuses
with exponential backoff up to 6 attempts, caps HTTP-400 "retryable message"
client errors at a *separate*, lower 3-attempt cap, short-circuits the whole
batch the instant the API key is rejected, and never re-fetches a cached
(url, strategy) pair. Also covers the small pure classifiers
(``is_api_key_error``, ``is_retryable_psi_error``, ``extract_api_error_message``,
``classify_psi_status``) that drive those decisions.

No live network: ``aiohttp.ClientSession`` is a ``MagicMock`` whose
``.get()`` returns a fake async-context-manager response (same pattern as
``tests/crawler/test_link_checks.py``); the cache is a real in-memory SQLite
connection (cheap, avoids reimplementing ``psi_cache``'s schema as a mock);
``_jittered_delay`` is patched to a no-op so retry/backoff tests run
instantly instead of sleeping for real.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hype_frog.crawler import psi_batch as module
from hype_frog.crawler.psi_batch import (
    PsiRequestPacer,
    _BatchAbortState,
    classify_psi_status,
    extract_api_error_message,
    fetch_strategy_raw,
    is_api_key_error,
    is_retryable_psi_error,
)


# ---------------------------------------------------------------------------
# Pure classifiers
# ---------------------------------------------------------------------------


def test_extract_api_error_message_reads_nested_error_block() -> None:
    payload = {"error": {"code": 400, "message": "API key not valid"}}
    assert extract_api_error_message(payload) == "API key not valid"


def test_extract_api_error_message_handles_non_dict_and_missing_error() -> None:
    assert extract_api_error_message(None) is None
    assert extract_api_error_message("not a dict") is None
    assert extract_api_error_message({}) is None
    assert extract_api_error_message({"error": "not a dict either"}) is None
    assert extract_api_error_message({"error": {"message": "  "}}) is None


def test_is_api_key_error_403_is_always_key_error() -> None:
    assert is_api_key_error(403, None) is True
    assert is_api_key_error(403, "unrelated message") is True


def test_is_api_key_error_400_requires_matching_message() -> None:
    assert is_api_key_error(400, "API key not valid") is True
    assert is_api_key_error(400, "permission denied for this project") is True
    assert is_api_key_error(400, "Invalid URL supplied") is False
    assert is_api_key_error(400, None) is False


def test_is_api_key_error_other_statuses_are_never_key_errors() -> None:
    assert is_api_key_error(500, "API key not valid") is False
    assert is_api_key_error(200, "API key not valid") is False


def test_is_retryable_psi_error_known_retry_statuses() -> None:
    for status in (429, 500, 502, 503, 504):
        assert is_retryable_psi_error(status, None) is True


def test_is_retryable_psi_error_400_requires_matching_message() -> None:
    assert is_retryable_psi_error(400, "Lighthouse returned error: FAILED_DOCUMENT_REQUEST") is True
    assert is_retryable_psi_error(400, "quota exceeded") is True
    assert is_retryable_psi_error(400, "Invalid URL supplied") is False


def test_is_retryable_psi_error_non_retryable_status_is_false() -> None:
    assert is_retryable_psi_error(404, "quota exceeded") is False
    assert is_retryable_psi_error(200, None) is False


@pytest.mark.parametrize(
    ("status", "expected_bucket"),
    [
        ("PSI + CrUX (mobile field data)", "complete"),
        ("CrUX Field Data (desktop)", "complete"),
        ("PSI Lab", "lab_only"),
        ("Complete", "complete"),
        ("Partial (mobile only)", "partial"),
        ("Lab only", "lab_only"),
        ("Unavailable", "unavailable"),
        ("", "unavailable"),
    ],
)
def test_classify_psi_status_buckets(status: str, expected_bucket: str) -> None:
    assert classify_psi_status(status) == expected_bucket


# ---------------------------------------------------------------------------
# PsiRequestPacer
# ---------------------------------------------------------------------------


def test_pacer_first_call_does_not_sleep() -> None:
    pacer = PsiRequestPacer(base_seconds=5.0, jitter_fraction=0.0)
    with patch.object(module.asyncio, "sleep", new=AsyncMock()) as mock_sleep:
        asyncio.run(pacer.wait())
    mock_sleep.assert_not_called()


def test_pacer_second_call_sleeps_for_remaining_spacing() -> None:
    """A second request arriving before ``base_seconds`` has elapsed must be
    delayed for the remaining spacing (the pacing contract this class exists
    to enforce)."""
    pacer = PsiRequestPacer(base_seconds=5.0, jitter_fraction=0.0)
    # wait() reads the clock once when _last_request_at is unset (sets it to
    # 100.0), then twice on the next call: once for the elapsed check, once
    # to stamp the new _last_request_at after sleeping.
    fake_clock = iter([100.0, 101.0, 101.0])

    async def _run_twice() -> None:
        with (
            patch.object(module.time, "monotonic", side_effect=fake_clock),
            patch.object(module.asyncio, "sleep", new=AsyncMock()) as mock_sleep,
        ):
            await pacer.wait()  # sets _last_request_at = 100.0, no prior call -> no sleep
            await pacer.wait()  # elapsed = 101.0 - 100.0 = 1.0s < 5.0s base -> must sleep ~4.0s
            mock_sleep.assert_awaited_once()
            (slept_for,) = mock_sleep.await_args.args
            assert slept_for == pytest.approx(4.0, abs=0.01)

    asyncio.run(_run_twice())


# ---------------------------------------------------------------------------
# fetch_strategy_raw: cache / abort short-circuits
# ---------------------------------------------------------------------------


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE psi_cache (
            url TEXT NOT NULL,
            strategy TEXT NOT NULL,
            response_body TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            PRIMARY KEY (url, strategy)
        )
        """
    )
    conn.commit()
    return conn


def _fake_response(status: int, payload: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value={} if payload is None else payload)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


async def _fetch(
    session: MagicMock,
    *,
    conn: sqlite3.Connection | None = None,
    abort_state: _BatchAbortState | None = None,
) -> tuple[dict, str | None]:
    return await fetch_strategy_raw(
        session,
        asyncio.Semaphore(1),
        conn if conn is not None else _cache_conn(),
        threading.Lock(),
        "https://example.com/",
        "test-api-key",
        "mobile",
        abort_state if abort_state is not None else _BatchAbortState(),
    )


@pytest.mark.asyncio
async def test_fetch_strategy_raw_returns_cached_payload_without_http_call() -> None:
    from hype_frog.crawler.psi_cache import cache_put

    conn = _cache_conn()
    cache_put(conn, "https://example.com/", "mobile", {"lighthouseResult": {"cached": True}})
    session = MagicMock()
    session.get = MagicMock(side_effect=AssertionError("should not hit the network on a cache hit"))

    payload, error = await _fetch(session, conn=conn)

    assert error is None
    assert payload == {"lighthouseResult": {"cached": True}}
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_strategy_raw_short_circuits_when_api_key_already_rejected() -> None:
    session = MagicMock()
    session.get = MagicMock(side_effect=AssertionError("must not call the network once aborted"))
    abort_state = _BatchAbortState(api_key_rejected=True, reject_reason="key dead")

    payload, error = await _fetch(session, abort_state=abort_state)

    assert payload == {}
    assert error == "key dead"
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_strategy_raw_success_caches_the_payload() -> None:
    from hype_frog.crawler.psi_cache import cache_get

    conn = _cache_conn()
    session = MagicMock()
    session.get = MagicMock(
        return_value=_fake_response(200, {"lighthouseResult": {"ok": True}})
    )

    payload, error = await _fetch(session, conn=conn)

    assert error is None
    assert payload == {"lighthouseResult": {"ok": True}}
    assert cache_get(conn, "https://example.com/", "mobile") == {"lighthouseResult": {"ok": True}}


@pytest.mark.asyncio
async def test_fetch_strategy_raw_retries_retryable_status_then_succeeds() -> None:
    responses = [
        _fake_response(503),
        _fake_response(503),
        _fake_response(200, {"lighthouseResult": {"ok": True}}),
    ]
    session = MagicMock()
    session.get = MagicMock(side_effect=responses)

    with patch.object(module, "_jittered_delay", new=AsyncMock()):
        payload, error = await _fetch(session)

    assert error is None
    assert payload == {"lighthouseResult": {"ok": True}}
    assert session.get.call_count == 3


@pytest.mark.asyncio
async def test_fetch_strategy_raw_exhausts_retries_on_persistent_5xx() -> None:
    """Bounded retries: 6 attempts, then give up cleanly (no unbounded loop,
    no exception escapes)."""
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(503))

    with patch.object(module, "_jittered_delay", new=AsyncMock()):
        payload, error = await _fetch(session)

    assert payload == {}
    assert error is not None
    assert session.get.call_count == module._MAX_RETRY_ATTEMPTS


@pytest.mark.asyncio
async def test_fetch_strategy_raw_client_error_retry_cap_is_lower_than_general_cap() -> None:
    """HTTP 400 with a retryable message caps at ``_MAX_CLIENT_ERROR_RETRIES``
    (3), a distinct and lower ceiling than the general 6-attempt retry cap —
    Google returns 400 (not 429/503) for several transient Lighthouse
    failures, so this must not retry as long as a real 5xx would."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_fake_response(400, {"error": {"message": "chrome crashed while loading"}})
    )

    with patch.object(module, "_jittered_delay", new=AsyncMock()):
        payload, error = await _fetch(session)

    assert payload == {}
    assert "chrome crashed" in (error or "")
    assert session.get.call_count == module._MAX_CLIENT_ERROR_RETRIES


@pytest.mark.asyncio
async def test_fetch_strategy_raw_403_rejects_api_key_and_sets_abort_state() -> None:
    session = MagicMock()
    session.get = MagicMock(
        return_value=_fake_response(403, {"error": {"message": "permission denied"}})
    )
    abort_state = _BatchAbortState()

    payload, error = await _fetch(session, abort_state=abort_state)

    assert payload == {}
    assert error == "permission denied"
    assert abort_state.api_key_rejected is True
    assert abort_state.reject_reason == "permission denied"
    session.get.assert_called_once()  # rejection short-circuits immediately, no retry


@pytest.mark.asyncio
async def test_fetch_strategy_raw_400_matching_key_message_also_rejects() -> None:
    """``is_api_key_error`` also matches 400 responses whose message names an
    API-key problem — Google does not always use 403 for key rejections."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_fake_response(400, {"error": {"message": "API key not valid"}})
    )
    abort_state = _BatchAbortState()

    payload, error = await _fetch(session, abort_state=abort_state)

    assert payload == {}
    assert abort_state.api_key_rejected is True
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_strategy_raw_non_retryable_4xx_returns_immediately() -> None:
    """A plain 404 (not retryable, not an API-key error) must fail fast, not
    burn through retry attempts."""
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(404, {"error": {"message": "not found"}}))

    payload, error = await _fetch(session)

    assert payload == {}
    assert error == "not found"
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_strategy_raw_missing_lighthouse_result_is_not_retried() -> None:
    """A well-formed 200 JSON body missing ``lighthouseResult`` is a
    malformed-payload failure, not a transient one — it must not consume the
    retry budget."""
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(200, {"some": "other shape"}))

    payload, error = await _fetch(session)

    assert payload == {}
    assert error is not None
    session.get.assert_called_once()
