"""Resolve Content Hub Metrics from crawl, render, and PSI enrichment rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# Mirrors ``network_engine._JS_DEPENDENT_*`` thresholds.
_JS_DEPENDENT_ABS_DELTA = 50
_JS_DEPENDENT_REL_DELTA = 0.15
_JS_DEPENDENT_RAW_EMPTY_FLOOR = 80


@dataclass(frozen=True)
class ContentHubMetricsSnapshot:
    js_dependent: bool
    raw_words: int
    rendered_words: int
    field_lcp_ms: float | None
    field_cls: float | None


def _to_int(value: object, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_positive_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out <= 0:
        return None
    return out


def compute_js_dependent_flag(raw_words: int, rendered_words: int) -> bool:
    """True when rendered DOM word count materially exceeds the raw HTTP payload."""
    raw = max(0, raw_words)
    rendered = max(0, rendered_words)
    if rendered <= 0:
        return False
    if raw <= 0:
        return rendered >= _JS_DEPENDENT_RAW_EMPTY_FLOOR
    delta = rendered - raw
    if delta <= 0:
        return False
    return delta >= _JS_DEPENDENT_ABS_DELTA or (delta / raw) >= _JS_DEPENDENT_REL_DELTA


def _body_word_count(
    extra: Mapping[str, Any],
    main: Mapping[str, Any],
) -> int:
    return _to_int(
        extra.get("Word Count") or main.get("Word Count (Body)"),
        0,
    )


def _resolve_word_counts(
    extra: Mapping[str, Any],
    main: Mapping[str, Any],
) -> tuple[int, int]:
    body_words = _body_word_count(extra, main)
    raw_words = _to_int(extra.get("Raw Words"), 0)
    rendered_words = _to_int(extra.get("Rendered Words"), 0)

    if raw_words <= 0 and body_words > 0:
        raw_words = body_words
    if rendered_words <= 0:
        rendered_words = raw_words if raw_words > 0 else body_words
    return raw_words, rendered_words


def _resolve_field_lcp_ms(
    extra: Mapping[str, Any],
    main: Mapping[str, Any],
) -> float | None:
    direct = _to_positive_float(extra.get("Field LCP (ms)"))
    if direct is not None:
        return round(direct, 2)

    for key in ("CWV LCP (s)", "Mobile LCP (s)"):
        seconds = _to_positive_float(extra.get(key) or main.get(key))
        if seconds is not None:
            return round(seconds * 1000.0, 2)
    return None


def _resolve_field_cls(
    extra: Mapping[str, Any],
    main: Mapping[str, Any],
) -> float | None:
    direct = extra.get("Field CLS")
    if direct is not None and str(direct).strip() != "":
        try:
            return round(float(direct), 4)
        except (TypeError, ValueError):
            pass

    for key in ("CWV CLS", "Mobile CLS"):
        value = extra.get(key) or main.get(key)
        if value is not None and str(value).strip() != "":
            try:
                return round(float(value), 4)
            except (TypeError, ValueError):
                continue
    return None


def resolve_content_hub_metrics(
    main: Mapping[str, Any] | None,
    extra: Mapping[str, Any] | None,
) -> ContentHubMetricsSnapshot:
    """Single resolver for Content Hub Metrics export and enrichment backfill."""
    m = main or {}
    e = extra or {}
    raw_words, rendered_words = _resolve_word_counts(e, m)
    js_dependent = compute_js_dependent_flag(raw_words, rendered_words)
    if e.get("JS Dependent") is True:
        js_dependent = True
    return ContentHubMetricsSnapshot(
        js_dependent=js_dependent,
        raw_words=raw_words,
        rendered_words=rendered_words,
        field_lcp_ms=_resolve_field_lcp_ms(e, m),
        field_cls=_resolve_field_cls(e, m),
    )


def backfill_extra_content_hub_metrics(
    extra_values: dict[str, Any],
    main_values: Mapping[str, Any] | None = None,
) -> None:
    """Persist resolved metrics on the extra row dict (additive, idempotent)."""
    snapshot = resolve_content_hub_metrics(main_values, extra_values)
    extra_values["Raw Words"] = snapshot.raw_words
    extra_values["Rendered Words"] = snapshot.rendered_words
    extra_values["JS Dependent"] = snapshot.js_dependent
    if snapshot.field_lcp_ms is not None:
        extra_values["Field LCP (ms)"] = snapshot.field_lcp_ms
    if snapshot.field_cls is not None:
        extra_values["Field CLS"] = snapshot.field_cls


__all__ = [
    "ContentHubMetricsSnapshot",
    "backfill_extra_content_hub_metrics",
    "compute_js_dependent_flag",
    "resolve_content_hub_metrics",
]
