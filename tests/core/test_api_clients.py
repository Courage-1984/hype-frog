"""Unit tests for the LLM intent classifier in :mod:`hype_frog.core.api_clients`.

Verifies the seven-way fallback contract documented in the module docstring
and the AI/LLM operational governance section of ``architecture.mdc``: the
async classifier must return ``"Unknown"`` and never raise when the LLM
stack is missing, broken, slow, or returning garbage. This keeps the crawl
async loop unblocked when external enrichment degrades.

* Rule #2 (No Live Network): every test injects a fully mocked
  ``aiohttp``-shaped session; ``aiohttp.ClientSession()`` is never
  constructed.
* Rule #3 (Extraction State): no crawl-row payloads are constructed in
  this module, so the three-way ``Extraction State`` contract is not in
  scope here.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.core.api_clients import (
    SEARCH_INTENT_LABELS,
    _format_validation_failure,
    _normalise_search_intent,
    classify_search_intent_heuristic,
    classify_search_intent_with_llm,
    parse_gsc_row,
    parse_http_crawl_result,
    parse_psi_response,
)

_FAKE_KEY = "sk-test-fake-key-not-a-real-secret"


# ---------------------------------------------------------------------------
# Mock builders
# ---------------------------------------------------------------------------


def _build_mock_post_cm(response: MagicMock) -> MagicMock:
    """Wrap a response in an async-context-manager-shaped mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_mock_session(
    *,
    status: int = 200,
    json_data: dict[str, Any] | None = None,
    text_data: str = "",
    json_side_effect: BaseException | None = None,
    post_side_effect: BaseException | None = None,
) -> MagicMock:
    """Construct a session double that never touches the network.

    ``post_side_effect`` raises on the synchronous ``client.post(...)``
    call (covers ``TimeoutError`` / connection-reset paths).
    ``json_side_effect`` raises from inside the body parser (covers the
    malformed-JSON path).
    """
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text_data)
    if json_side_effect is not None:
        response.json = AsyncMock(side_effect=json_side_effect)
    else:
        response.json = AsyncMock(return_value=json_data or {})

    session = MagicMock()
    session.close = AsyncMock(return_value=None)
    if post_side_effect is not None:
        session.post = MagicMock(side_effect=post_side_effect)
    else:
        session.post = MagicMock(return_value=_build_mock_post_cm(response))
    return session


def _ok_chat_completion(content: str) -> dict[str, Any]:
    """Mirror the OpenAI chat-completions success envelope."""
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# Sanity baseline (NOT one of the seven fallbacks)
# ---------------------------------------------------------------------------


async def test_happy_path_returns_canonical_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(
        status=200,
        json_data=_ok_chat_completion("Informational"),
    )
    result = await classify_search_intent_with_llm(
        "How do I bake sourdough bread?", session=session
    )
    assert result == "Informational"
    session.post.assert_called_once()
    # Caller-owned session must NOT be closed by the function.
    session.close.assert_not_awaited()


# ---------------------------------------------------------------------------
# Seven-way fallback contract
# ---------------------------------------------------------------------------


async def test_fallback_1_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = _make_mock_session()
    result = await classify_search_intent_with_llm(
        "buy running shoes", session=session
    )
    assert result == "Unknown"
    # Early return must short-circuit BEFORE any HTTP call is attempted.
    session.post.assert_not_called()


async def test_fallback_1b_blank_api_key_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only env var must collapse to the missing-key fallback."""
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    session = _make_mock_session()
    result = await classify_search_intent_with_llm(
        "looking for running shoes", session=session
    )
    assert result == "Unknown"
    session.post.assert_not_called()


async def test_fallback_2_blank_input_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session()
    for blank in ("", "   ", None, "\t\n"):
        result = await classify_search_intent_with_llm(blank, session=session)
        assert result == "Unknown", f"blank input {blank!r} should fall back"
    session.post.assert_not_called()


async def test_fallback_3a_http_401_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(status=401, text_data="invalid api key")
    result = await classify_search_intent_with_llm(
        "checkout cart page", session=session
    )
    assert result == "Unknown"


async def test_fallback_3b_http_502_bad_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(status=502, text_data="upstream unavailable")
    result = await classify_search_intent_with_llm("login portal", session=session)
    assert result == "Unknown"


async def test_fallback_4_timeout_during_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``asyncio.TimeoutError`` is the canonical aiohttp timeout exception."""
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(
        post_side_effect=asyncio.TimeoutError("LLM took too long"),
    )
    result = await classify_search_intent_with_llm(
        "how to compost at home", session=session
    )
    assert result == "Unknown"


async def test_fallback_5_malformed_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``response.json()`` raising must be caught by the broad ``except``."""
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(
        status=200,
        json_side_effect=ValueError("Expecting value: line 1 column 1 (char 0)"),
    )
    result = await classify_search_intent_with_llm(
        "guide to mortgages", session=session
    )
    assert result == "Unknown"


async def test_fallback_5b_well_formed_json_missing_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Body parses fine but is missing ``choices`` → ``KeyError`` path."""
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(status=200, json_data={"unexpected": "shape"})
    result = await classify_search_intent_with_llm(
        "how to invest", session=session
    )
    assert result == "Unknown"


async def test_fallback_6_unexpected_label_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM hallucinates an out-of-vocab label → normaliser returns Unknown."""
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(
        status=200,
        json_data=_ok_chat_completion("Pizza"),
    )
    result = await classify_search_intent_with_llm(
        "a tasty pepperoni page", session=session
    )
    assert result == "Unknown"


async def test_fallback_7_generic_connection_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any non-timeout transport error (peer reset, DNS, etc.) → Unknown."""
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    session = _make_mock_session(post_side_effect=ConnectionResetError("peer reset"))
    result = await classify_search_intent_with_llm(
        "contact support", session=session
    )
    assert result == "Unknown"


# ---------------------------------------------------------------------------
# Normaliser unit checks (covers the docstring-promised "Commercial" alias)
# ---------------------------------------------------------------------------


def test_normalise_search_intent_canonical_labels_passthrough() -> None:
    for label in SEARCH_INTENT_LABELS:
        assert _normalise_search_intent(label) == label


def test_normalise_search_intent_terse_commercial_alias() -> None:
    assert _normalise_search_intent("commercial") == "Commercial Investigation"


def test_normalise_search_intent_blank_and_none_return_unknown() -> None:
    assert _normalise_search_intent(None) == "Unknown"
    assert _normalise_search_intent("") == "Unknown"
    assert _normalise_search_intent("   ") == "Unknown"


def test_normalise_search_intent_substring_match_in_chatty_output() -> None:
    """LLMs often pad: ``'Intent: Informational.'`` should still classify."""
    assert _normalise_search_intent("Intent: Informational.") == "Informational"
    assert _normalise_search_intent("Navigational search") == "Navigational"


# ---------------------------------------------------------------------------
# Local OpenAI-compatible server (Ollama / LM Studio) via OPENAI_BASE_URL
# ---------------------------------------------------------------------------


async def test_local_base_url_bypasses_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured local server must not require OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    session = _make_mock_session(
        status=200,
        json_data=_ok_chat_completion("Informational"),
    )
    result = await classify_search_intent_with_llm("how to compost", session=session)
    assert result == "Informational"
    called_url = session.post.call_args.args[0]
    assert called_url == "http://localhost:11434/v1/chat/completions"


async def test_local_base_url_still_returns_unknown_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    session = _make_mock_session(status=500, text_data="model not loaded")
    result = await classify_search_intent_with_llm("buy shoes", session=session)
    assert result == "Unknown"


async def test_no_key_and_no_base_url_still_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    session = _make_mock_session()
    result = await classify_search_intent_with_llm("buy shoes", session=session)
    assert result == "Unknown"
    session.post.assert_not_called()


# ---------------------------------------------------------------------------
# Zero-config heuristic fallback (classify_search_intent_heuristic)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/pricing", "Transactional"),
        ("https://example.com/buy-now", "Transactional"),
        ("https://example.com/contact", "Transactional"),
        ("https://example.com/best-running-shoes", "Commercial Investigation"),
        ("https://example.com/widgets-vs-gadgets", "Commercial Investigation"),
        ("https://example.com/login", "Navigational"),
        ("https://example.com/about", "Navigational"),
        ("https://example.com/", "Navigational"),
        ("https://example.com/blog/how-to-bake-bread", "Informational"),
        ("https://example.com/faq", "Informational"),
        ("https://example.com/random-slug-xyz", "Unknown"),
    ],
)
def test_classify_search_intent_heuristic_url_rules(url: str, expected: str) -> None:
    assert classify_search_intent_heuristic(url) == expected


def test_classify_search_intent_heuristic_uses_title_and_meta() -> None:
    assert (
        classify_search_intent_heuristic(
            "https://example.com/p/123", title="Buy our best pricing plans"
        )
        == "Transactional"
    )
    assert (
        classify_search_intent_heuristic(
            "https://example.com/p/456",
            meta_description="A complete guide on how to compost at home",
        )
        == "Informational"
    )


def test_classify_search_intent_heuristic_blank_input_is_unknown() -> None:
    assert classify_search_intent_heuristic(None) == "Unknown"
    assert classify_search_intent_heuristic("") == "Unknown"
    assert classify_search_intent_heuristic("not-a-url-at-all") == "Unknown"


# ---------------------------------------------------------------------------
# _format_validation_failure
# ---------------------------------------------------------------------------


def test_format_validation_failure_renders_field_and_reason() -> None:
    from pydantic import BaseModel as _BM

    class _Probe(_BM):
        clicks: int

    try:
        _Probe.model_validate({"clicks": "not-a-number"})
        raise AssertionError("expected ValidationError")
    except Exception as exc:  # pydantic.ValidationError
        message = _format_validation_failure(exc)
        assert "clicks=" in message


# ---------------------------------------------------------------------------
# parse_http_crawl_result
# ---------------------------------------------------------------------------


def test_parse_http_crawl_result_valid_payload() -> None:
    result = parse_http_crawl_result(
        {"url": "https://example.com/", "status_code": 200, "response_time_ms": 123.4}
    )
    assert result is not None
    assert result.status_code == 200
    assert result.response_time_ms == 123.4


def test_parse_http_crawl_result_none_payload_returns_none() -> None:
    assert parse_http_crawl_result(None) is None


def test_parse_http_crawl_result_missing_url_returns_none() -> None:
    assert parse_http_crawl_result({"status_code": 200, "response_time_ms": 1.0}) is None


def test_parse_http_crawl_result_status_code_out_of_range_returns_none() -> None:
    result = parse_http_crawl_result(
        {"url": "https://example.com/", "status_code": 999, "response_time_ms": 1.0}
    )
    assert result is None


def test_parse_http_crawl_result_negative_response_time_returns_none() -> None:
    result = parse_http_crawl_result(
        {"url": "https://example.com/", "status_code": 200, "response_time_ms": -5.0}
    )
    assert result is None


def test_parse_http_crawl_result_ignores_unknown_extra_keys() -> None:
    result = parse_http_crawl_result(
        {
            "url": "https://example.com/",
            "status_code": 200,
            "response_time_ms": 10.0,
            "some_future_field": "unrecognised",
        }
    )
    assert result is not None


# ---------------------------------------------------------------------------
# parse_psi_response
# ---------------------------------------------------------------------------


def test_parse_psi_response_valid_payload() -> None:
    result = parse_psi_response({"performance_score": 90, "lcp_seconds": 1.2})
    assert result is not None
    assert result.performance_score == 90
    assert result.lcp_seconds == 1.2


def test_parse_psi_response_none_payload_returns_none() -> None:
    assert parse_psi_response(None) is None


def test_parse_psi_response_no_recognisable_signal_returns_none() -> None:
    """All Lighthouse/CrUX fields absent must fail the model's
    ``_require_some_signal`` guard rather than validate as an empty shell."""
    assert parse_psi_response({}) is None


def test_parse_psi_response_nan_metric_returns_none() -> None:
    assert parse_psi_response({"lcp_seconds": float("nan")}) is None


def test_parse_psi_response_inf_metric_returns_none() -> None:
    assert parse_psi_response({"cls": float("inf")}) is None


def test_parse_psi_response_out_of_range_score_returns_none() -> None:
    assert parse_psi_response({"performance_score": 150}) is None


def test_parse_psi_response_injects_url_when_missing() -> None:
    result = parse_psi_response({"performance_score": 80}, url="https://example.com/page")
    assert result is not None
    assert result.url == "https://example.com/page"


def test_parse_psi_response_does_not_override_existing_url() -> None:
    result = parse_psi_response(
        {"performance_score": 80, "url": "https://example.com/original"},
        url="https://example.com/override",
    )
    assert result is not None
    assert result.url == "https://example.com/original"


# ---------------------------------------------------------------------------
# parse_gsc_row
# ---------------------------------------------------------------------------


def test_parse_gsc_row_native_gsc_shape() -> None:
    row = parse_gsc_row(
        {
            "keys": ["https://example.com/page"],
            "clicks": 10,
            "impressions": 100,
            "ctr": 0.1,
            "position": 5.5,
        }
    )
    assert row is not None
    assert row.url == "https://example.com/page"
    assert row.clicks == 10


def test_parse_gsc_row_flattened_shape() -> None:
    row = parse_gsc_row(
        {
            "GSC Clicks": 3,
            "GSC Impressions": 50,
            "GSC CTR": 0.06,
            "GSC Average Position": 12.3,
        }
    )
    assert row is not None
    assert row.clicks == 3
    assert row.impressions == 50
    assert row.position == 12.3


def test_parse_gsc_row_flattened_shape_uses_avg_position_alias() -> None:
    row = parse_gsc_row(
        {
            "GSC Clicks": 1,
            "GSC Impressions": 10,
            "GSC CTR": 0.1,
            "GSC Avg Position": 3.0,
        }
    )
    assert row is not None
    assert row.position == 3.0


def test_parse_gsc_row_none_row_returns_none() -> None:
    assert parse_gsc_row(None) is None


def test_parse_gsc_row_missing_clicks_returns_none() -> None:
    row = parse_gsc_row({"impressions": 10, "ctr": 0.1, "position": 1.0})
    assert row is None


def test_parse_gsc_row_nan_clicks_returns_none() -> None:
    row = parse_gsc_row(
        {"clicks": float("nan"), "impressions": 10, "ctr": 0.1, "position": 1.0}
    )
    assert row is None


def test_parse_gsc_row_ctr_out_of_range_returns_none() -> None:
    row = parse_gsc_row({"clicks": 1, "impressions": 10, "ctr": 1.5, "position": 1.0})
    assert row is None


def test_parse_gsc_row_url_kwarg_used_when_row_has_no_url() -> None:
    row = parse_gsc_row(
        {"clicks": 1, "impressions": 10, "ctr": 0.1, "position": 1.0},
        url="https://example.com/fallback",
    )
    assert row is not None
    assert row.url == "https://example.com/fallback"


def test_parse_gsc_row_empty_keys_list_falls_back_to_url_kwarg() -> None:
    row = parse_gsc_row(
        {"keys": [], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 1.0},
        url="https://example.com/fallback",
    )
    assert row is not None
    assert row.url == "https://example.com/fallback"
