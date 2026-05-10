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
    _normalise_search_intent,
    classify_search_intent_with_llm,
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
