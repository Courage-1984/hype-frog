"""Diagnostic storytelling narratives for the executive Dashboard."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.broken_links import is_broken_http_status, is_internal_link_type

_DEFAULT_NO_CRAWL = "No data available. Please run a full crawl to generate insights."


def sanitize_cell_text(text: str) -> str:
    """Strip Excel formula injection prefixes and non-printable controls (keep newlines/tabs)."""
    s = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\t")
    s = s.lstrip()
    while s and s[0] in "=+-@":
        s = s[1:].lstrip()
    return s


# Backwards-compatible private alias (historical call sites in this module).
_sanitize_cell_text = sanitize_cell_text


def _normalize_row_seo_value(raw: float) -> float:
    """Map per-URL SEO metrics to a 0–100 scale (handles 0–1 fractions vs 0–100 points)."""
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if x <= 1.5:
        return min(100.0, max(0.0, x * 100.0))
    return min(100.0, max(0.0, x))


def average_seo_score_pct(main_rows: list[MainRowPayload]) -> float:
    """Mean SEO signal across rows (``SEO Score`` when present; else ``SEO Health Score``).

    Technical Diagnostics rows often populate ``SEO Health Score`` while ``SEO Score`` stays
    at the default zero until merged enrichment—treat literal zero as missing so averages
    reflect diagnostics health instead of zero-padding.
    """
    vals: list[float] = []
    for row in main_rows:
        v = row.values
        raw = v.get("SEO Score")
        if raw is None or str(raw).strip() == "":
            raw = v.get("SEO Health Score")
        else:
            try:
                if float(raw) == 0.0:
                    alt = v.get("SEO Health Score")
                    if alt is not None and str(alt).strip() != "":
                        raw = alt
            except (TypeError, ValueError):
                pass
            if raw is None or str(raw).strip() == "":
                raw = v.get("SEO Health Score")
        try:
            if raw is not None and str(raw).strip() != "":
                vals.append(_normalize_row_seo_value(float(raw)))
        except (TypeError, ValueError):
            continue
    return sum(vals) / len(vals) if vals else 0.0


def _avg_extractability_from_content_rows(rows: list[dict[str, Any]]) -> float:
    vals: list[float] = []
    for r in rows:
        raw = r.get("AEO Extractability Score")
        try:
            if raw is not None and str(raw).strip() != "":
                vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    return sum(vals) / len(vals) if vals else 0.0


def _has_psi_lab_data(extra_rows: list[ExtraRowPayload]) -> bool:
    """True when at least one URL has measured Mobile or Desktop PSI lab scores."""
    for row in extra_rows:
        v = row.values
        status = str(v.get("PSI Data Status") or "").strip().lower()
        if status.startswith("unavailable") or status.startswith("not measured"):
            continue
        for key in ("Mobile PSI Score", "Desktop PSI Score"):
            raw = v.get(key)
            try:
                if raw is None or str(raw).strip() == "":
                    continue
                float(raw)
                return True
            except (TypeError, ValueError):
                continue
    return False


def _break_url_for_cell_wrap(url: str, chunk: int = 52) -> str:
    """Insert newlines so Excel wraps very long URLs; works with cell wrap_text=True."""
    u = url.strip()
    if len(u) <= chunk:
        return u
    return "\n".join(u[i : i + chunk] for i in range(0, len(u), chunk))


def _psi_variance_mobile_minus_desktop(extra_rows: list[ExtraRowPayload]) -> float:
    """Match Dashboard B8: AVG(Mobile PSI) − AVG(Desktop PSI) on Technical rows."""
    mobiles: list[float] = []
    desktops: list[float] = []
    for row in extra_rows:
        v = row.values
        try:
            m = v.get("Mobile PSI Score")
            d = v.get("Desktop PSI Score")
            if m is not None and str(m).strip() != "":
                mobiles.append(float(m))
            if d is not None and str(d).strip() != "":
                desktops.append(float(d))
        except (TypeError, ValueError):
            continue
    if not mobiles or not desktops:
        return 0.0
    return sum(mobiles) / len(mobiles) - sum(desktops) / len(desktops)


def _broken_internal_stats(link_rows: list[dict[str, Any]]) -> tuple[int, str]:
    """Return (instance_count, top_broken_target_url) from Link Inventory rows."""
    targets: list[str] = []
    for row in link_rows:
        if not is_internal_link_type(row.get("Link Type")):
            continue
        if not is_broken_http_status(row.get("Status Code")):
            continue
        target = str(row.get("Target URL") or "").strip()
        if target:
            targets.append(target)
    if not targets:
        return 0, ""
    top_url, _count = Counter(targets).most_common(1)[0]
    return len(targets), top_url


def _aeo_opportunity_gap_pct(avg_extractability: float, avg_seo_decimal: float) -> float:
    """Align with Dashboard B19: extractability branch vs SEO headroom."""
    bounded = max(0.0, min(1.0, avg_seo_decimal))
    if avg_extractability > 0.0:
        return max(0.0, 100.0 - avg_extractability)
    return max(0.0, (1.0 - bounded) * 100.0)


@dataclass(frozen=True)
class NarrativeEngine:
    """Generates Business Impact and Strategic Narrative copy from crawl outputs."""

    @staticmethod
    def build_business_impact(
        *,
        total_urls: int,
        link_inventory_rows: list[dict[str, Any]],
        technical_extra_rows: list[ExtraRowPayload],
        content_ai_rows: list[dict[str, Any]],
        avg_seo_score_pct: float,
    ) -> str:
        if total_urls <= 0:
            return _DEFAULT_NO_CRAWL

        lines: list[str] = []
        broken_n, top_url = _broken_internal_stats(link_inventory_rows)
        if broken_n > 0 and top_url:
            url_display = _break_url_for_cell_wrap(top_url)
            lines.append(
                f"⚠️ Link Integrity Risk: {broken_n} broken internal link instances found. "
                f"The most impacted destination is {url_display}."
            )

        has_psi = _has_psi_lab_data(technical_extra_rows)
        if not has_psi:
            lines.append(
                "⚡ Performance Audit: PSI data was not collected in this run. "
                "A full Performance Pass is recommended to identify mobile load-time bottlenecks."
            )

        variance = _psi_variance_mobile_minus_desktop(technical_extra_rows)
        if has_psi and variance < -10.0:
            lines.append(
                f"📱 Mobile Performance Penalty: Your site is {variance:.1f} points slower "
                "on mobile than desktop, likely throttling mobile search rankings."
            )

        avg_ext = _avg_extractability_from_content_rows(content_ai_rows)
        gap = _aeo_opportunity_gap_pct(
            avg_extractability=avg_ext,
            avg_seo_decimal=max(0.0, min(1.0, avg_seo_score_pct / 100.0)),
        )
        if gap > 20.0:
            if avg_ext > 0.0:
                score_pct = max(0, min(100, round(avg_ext)))
                gap_pct = max(0, min(100, round(gap)))
                lines.append(
                    f"🤖 AEO Opportunity: Your content is currently {score_pct}% optimized "
                    f"for AI-Search, leaving a {gap_pct}% opportunity for improvement."
                )
            else:
                lines.append(
                    f"🤖 AEO Opportunity: Approximately {round(gap)}% headroom remains for "
                    "AI-Search optimization based on overall SEO signals (extractability data "
                    "was limited in this run)."
                )

        if not lines:
            return _sanitize_cell_text(
                "No high-priority storytelling gates fired for this crawl. "
                "Review executive metrics and tab drill-downs for opportunities."
            )
        return _sanitize_cell_text("\n\n".join(lines))

    @staticmethod
    def build_strategic_narrative(
        *,
        total_urls: int,
        avg_seo_score_pct: float,
        critical_url_count: int,
    ) -> str:
        if total_urls <= 0:
            return _DEFAULT_NO_CRAWL

        seo_pct = max(0.0, min(100.0, float(avg_seo_score_pct)))

        # Triage: critical mass OR average SEO below 50%. Optimization: 50–74%. Dominance: 75%+.
        if critical_url_count > 5 or seo_pct < 50.0:
            return _sanitize_cell_text(
                "Critical technical debt is the primary barrier to growth. Stabilize crawl "
                "health, critical coverage, and indexing fundamentals before optimization work."
            )
        if seo_pct < 75.0:
            return _sanitize_cell_text(
                "Technical foundations are solid. Shift focus to PageSpeed and AEO structure."
            )
        return _sanitize_cell_text(
            "The site is technically elite. Focus on advanced schema and competitive "
            "content gaps."
        )


__all__ = [
    "NarrativeEngine",
    "average_seo_score_pct",
    "sanitize_cell_text",
]
