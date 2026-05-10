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

from pydantic import BaseModel, ValidationError

from hype_frog.core.logger import get_logger
from hype_frog.core.models import (
    GSCMetricsModel,
    HttpCrawlResultModel,
    PSIMetricsModel,
)

logger = get_logger(__name__)


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


__all__ = [
    "parse_gsc_row",
    "parse_http_crawl_result",
    "parse_psi_response",
]
