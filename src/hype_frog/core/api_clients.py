"""Strict raw-response parsers for upstream API payloads.

Thin parsing layer that funnels Google PSI, Google Search Console, and HTTP
fetch results through the Pydantic v2 validators in :mod:`hype_frog.core.models`.
Each parser catches :class:`pydantic.ValidationError`, logs the failing
fields, and returns ``None`` so callers can degrade gracefully without
crashing the active crawl loop.

These helpers are deliberately additive: they do **not** mutate any existing
``main_data`` keys, ``CrawlResult`` TypedDict shapes, or pipeline contracts.
Callers may opt in by validating raw payloads here before merging them into
their existing dictionaries.
"""

from __future__ import annotations

from typing import Any

import aiohttp
from pydantic import BaseModel, ValidationError

from hype_frog.core.env_vars import (
    get_openai_api_key,
    get_openai_base_url,
    get_openai_model,
)
from hype_frog.core.logger import get_logger
from hype_frog.core.models import (
    GSCMetricsModel,
    HttpCrawlResultModel,
    PSIMetricsModel,
)

logger = get_logger(__name__)

SEARCH_INTENT_LABELS: tuple[str, ...] = (
    "Informational",
    "Transactional",
    "Navigational",
    "Commercial Investigation",
)

_OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

# Ordered keyword rules for the zero-config, zero-cost intent fallback. Each
# entry is (label, substrings) checked against the URL path + title/meta text;
# first match wins. Used whenever the LLM path returns "Unknown" (no API key
# or base URL configured, or a live call failed).
_INTENT_URL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Transactional",
        (
            "buy", "pricing", "price", "quote", "order", "shop", "cart",
            "checkout", "book", "contact", "hire", "get-started", "signup",
            "sign-up", "demo",
        ),
    ),
    (
        "Commercial Investigation",
        ("best", "vs", "versus", "review", "compare", "comparison", "alternative", "top-"),
    ),
    (
        "Navigational",
        ("login", "log-in", "sign-in", "about", "account"),
    ),
    (
        "Informational",
        ("how", "what", "why", "guide", "/blog", "faq", "tips", "learn", "tutorial"),
    ),
)


def classify_search_intent_heuristic(
    url: str | None,
    title: str | None = None,
    meta_description: str | None = None,
) -> str:
    """Zero-config, zero-cost search-intent guess from URL/title/meta keywords.

    Used as the fallback when no LLM (hosted or local) is configured, so
    ``Search Intent`` need not collapse to "Unknown" on every URL. Ordered
    rules: first matching label wins; no match returns "Unknown". A bare "/"
    path (site home) is treated as Navigational.
    """
    from urllib.parse import urlsplit

    if not url or not str(url).strip():
        return "Unknown"
    path = urlsplit(str(url)).path.lower()
    haystack = " ".join(
        part.lower() for part in (path, title or "", meta_description or "") if part
    )
    if path in ("", "/"):
        return "Navigational"
    for label, keywords in _INTENT_URL_RULES:
        if any(keyword in haystack for keyword in keywords):
            return label
    return "Unknown"


def _format_validation_failure(error: ValidationError) -> str:
    """Render a compact ``field=reason`` summary for log output."""
    parts: list[str] = []
    for issue in error.errors():
        loc = ".".join(str(part) for part in issue.get("loc", ())) or "<root>"
        msg = str(issue.get("msg", "invalid"))
        parts.append(f"{loc}={msg}")
    return "; ".join(parts) if parts else "no detail"


def _safe_validate[T: BaseModel](
    model_cls: type[T],
    payload: Any,
    *,
    source: str,
    identifier: str | None,
) -> T | None:
    """Run ``model_cls.model_validate`` and log + swallow ``ValidationError``."""
    if payload is None:
        logger.debug("%s payload is None for %s; skipping validation.", source, identifier)
        return None
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "%s payload failed validation for %s: %s",
            source,
            identifier or "<unknown>",
            _format_validation_failure(exc),
        )
        return None
    except (TypeError, ValueError) as exc:
        logger.warning(
            "%s payload could not be parsed for %s: %s",
            source,
            identifier or "<unknown>",
            exc,
        )
        return None


def parse_http_crawl_result(payload: dict[str, Any] | None) -> HttpCrawlResultModel | None:
    """Validate a raw HTTP fetch result envelope.

    Expected keys (additional keys are ignored): ``url``, ``status_code``,
    ``response_time_ms``. The payload from
    :func:`hype_frog.crawler.network_engine.fetch_http` exposes
    ``status_code`` and ``ttfb_ms``/``total_request_ms`` — callers should map
    those onto ``response_time_ms`` before invoking this function. Returns
    ``None`` on any validation failure (already logged).
    """
    identifier = None
    if isinstance(payload, dict):
        identifier = str(payload.get("url") or payload.get("final_url") or "")
    return _safe_validate(
        HttpCrawlResultModel,
        payload,
        source="HTTP",
        identifier=identifier or None,
    )


def parse_psi_response(
    payload: dict[str, Any] | None,
    *,
    url: str | None = None,
) -> PSIMetricsModel | None:
    """Validate a flattened PageSpeed Insights metrics dict.

    The accepted shape mirrors
    :func:`hype_frog.crawler.psi_engine._lab_strategy_metrics`
    (``performance_score``, ``seo_score``, ``lcp_seconds``, ``cls``,
    ``inp_ms``, ``ttfb_seconds``). Pass the optional CrUX field map through
    the same validator — unknown keys are ignored and missing optional
    fields default to ``None``.
    """
    if payload is None:
        return None
    candidate: dict[str, Any] = dict(payload)
    if url and "url" not in candidate:
        candidate["url"] = url
    return _safe_validate(
        PSIMetricsModel,
        candidate,
        source="PSI",
        identifier=url or candidate.get("url"),
    )


def parse_gsc_row(
    row: dict[str, Any] | None,
    *,
    url: str | None = None,
) -> GSCMetricsModel | None:
    """Validate a single Google Search Console searchanalytics row.

    Accepts either the GSC native shape (``{"keys": [...], "clicks": n,
    "impressions": n, "ctr": f, "position": f}``) or the flattened payload
    produced by :func:`hype_frog.crawler.gsc_engine._rows_to_page_metrics`.
    Returns ``None`` on missing required counters or out-of-range values.
    """
    if row is None:
        return None

    candidate: dict[str, Any] = {}
    if isinstance(row, dict):
        keys = row.get("keys")
        if isinstance(keys, (list, tuple)) and keys:
            candidate["url"] = str(keys[0]) if keys[0] is not None else None
        elif "url" in row:
            candidate["url"] = row.get("url")

        candidate["clicks"] = row.get("clicks", row.get("GSC Clicks"))
        candidate["impressions"] = row.get(
            "impressions", row.get("GSC Impressions")
        )
        candidate["ctr"] = row.get("ctr", row.get("GSC CTR"))
        candidate["position"] = row.get(
            "position", row.get("GSC Average Position", row.get("GSC Avg Position"))
        )

    if url and not candidate.get("url"):
        candidate["url"] = url

    return _safe_validate(
        GSCMetricsModel,
        candidate,
        source="GSC",
        identifier=url or candidate.get("url"),
    )


def _normalise_search_intent(raw: object) -> str:
    """Return a canonical search-intent label, or ``"Unknown"``."""
    text = str(raw or "").strip()
    if not text:
        return "Unknown"
    cleaned = " ".join(text.replace(".", " ").replace(",", " ").split())
    lowered = cleaned.casefold()
    for label in SEARCH_INTENT_LABELS:
        if lowered == label.casefold() or label.casefold() in lowered:
            return label
    # Let common terse LLM outputs like "commercial" map cleanly.
    if lowered == "commercial":
        return "Commercial Investigation"
    return "Unknown"


async def classify_search_intent_with_llm(
    text: str | None,
    *,
    session: aiohttp.ClientSession | None = None,
    model: str | None = None,
    timeout_seconds: float = 5.0,
) -> str:
    """Classify page search intent with an OpenAI-compatible LLM.

    Supports local OpenAI-compatible servers (Ollama, LM Studio, llama.cpp)
    via ``OPENAI_BASE_URL`` — free, private, zero external cost. When a base
    URL is set, a missing API key no longer short-circuits (local servers
    typically ignore the bearer token); a placeholder is sent instead.

    Graceful fallback contract: missing API key/base URL, blank text, HTTP
    errors, malformed responses, and unexpected labels all return
    ``"Unknown"``. This keeps crawl workers moving even when LLM enrichment
    is unavailable.
    """
    snippet = " ".join(str(text or "").split())
    if not snippet:
        return "Unknown"
    base_url = get_openai_base_url()
    api_key = get_openai_api_key() or ""
    if not api_key and not base_url:
        return "Unknown"
    endpoint = f"{base_url}/chat/completions" if base_url else _OPENAI_CHAT_COMPLETIONS_URL

    prompt = (
        "Analyze this text and return one word for the search intent. "
        "Allowed outputs: Informational, Transactional, Navigational, "
        "Commercial Investigation.\n\n"
        f"Text: {snippet[:4000]}"
    )
    payload = {
        "model": model or get_openai_model(),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify web page search intent. Return only one "
                    "allowed label and no explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 8,
    }
    headers = {
        "Authorization": f"Bearer {api_key or 'local'}",
        "Content-Type": "application/json",
    }

    owns_session = session is None
    client = session or aiohttp.ClientSession()
    try:
        async with client.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as response:
            if response.status >= 400:
                body = await response.text()
                logger.warning(
                    "LLM intent classifier returned HTTP %s: %s",
                    response.status,
                    body[:200],
                )
                return "Unknown"
            data = await response.json()
    except Exception as exc:
        logger.warning("LLM intent classifier failed: %s", exc)
        return "Unknown"
    finally:
        if owns_session:
            await client.close()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "Unknown"
    return _normalise_search_intent(content)


__all__ = [
    "SEARCH_INTENT_LABELS",
    "classify_search_intent_with_llm",
    "parse_gsc_row",
    "parse_http_crawl_result",
    "parse_psi_response",
]
