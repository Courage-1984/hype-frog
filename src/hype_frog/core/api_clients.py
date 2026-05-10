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

import os
from typing import Any

import aiohttp
from pydantic import BaseModel, ValidationError

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
    timeout_seconds: float = 12.0,
) -> str:
    """Classify page search intent with an OpenAI-compatible LLM.

    Graceful fallback contract: missing API key, blank text, HTTP errors,
    malformed responses, and unexpected labels all return ``"Unknown"``.
    This keeps crawl workers moving even when LLM enrichment is unavailable.
    """
    snippet = " ".join(str(text or "").split())
    if not snippet:
        return "Unknown"
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return "Unknown"

    prompt = (
        "Analyze this text and return one word for the search intent. "
        "Allowed outputs: Informational, Transactional, Navigational, "
        "Commercial Investigation.\n\n"
        f"Text: {snippet[:4000]}"
    )
    payload = {
        "model": model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
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
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    owns_session = session is None
    client = session or aiohttp.ClientSession()
    try:
        async with client.post(
            _OPENAI_CHAT_COMPLETIONS_URL,
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
