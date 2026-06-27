"""Internal link equity distribution and anchor-text audit (B2)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from hype_frog.config_defaults import (
    GENERIC_ANCHOR_DOMINANCE_PCT,
    UNDER_LINKED_INBOUND_THRESHOLD,
)
from hype_frog.core.url_normalization import normalize_url
from hype_frog.pipeline.graph_engine import CLICK_DEPTH_UNREACHABLE

LINK_EQUITY_COLUMNS: tuple[str, ...] = (
    "URL",
    "Inbound Link Count",
    "Unique Source Pages",
    "Anchor Texts (top 5)",
    "PageRank Score",
    "PageRank Percentile",
    "Click Depth",
    "Equity Tier",
    "Recommended Action",
)

ANCHOR_TEXT_AUDIT_COLUMNS: tuple[str, ...] = (
    "Destination URL",
    "Inbound Link Count",
    "Generic Anchor Count",
    "Generic Anchor %",
    "Top Anchor Texts",
    "Generic Anchor Dominance",
    "Recommended Action",
)


def _row_values(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "values"):
        return row.values
    return {}


def _inbound_anchor_index(
    extra_rows: list[Any],
) -> dict[str, list[dict[str, Any]]]:
    inbound: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in extra_rows:
        values = _row_values(row)
        source = str(values.get("URL") or values.get("Final URL") or "").strip()
        if not source:
            continue
        for item in values.get("Link Details") or []:
            if str(item.get("Link Type") or "").lower() != "internal":
                continue
            target = str(item.get("Target URL") or "").strip()
            if not target:
                continue
            inbound[normalize_url(target)].append(
                {
                    "source": source,
                    "anchor": str(item.get("Anchor Text") or "").strip(),
                    "generic": bool(item.get("Generic Anchor")),
                }
            )
    return inbound


def _pagerank_percentiles(graph_metrics: dict[str, dict[str, object]]) -> dict[str, float]:
    scores = {
        url: float(data.get("Internal PageRank") or 0.0)
        for url, data in graph_metrics.items()
    }
    if not scores:
        return {}
    ordered = sorted(scores.items(), key=lambda item: item[1])
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 100.0}
    out: dict[str, float] = {}
    for index, (url, _score) in enumerate(ordered):
        out[url] = round((index / (n - 1)) * 100.0, 1)
    return out


def _equity_tier(
    *,
    orphan: bool,
    percentile: float,
) -> str:
    if orphan:
        return "Orphan"
    if percentile >= 75.0:
        return "High"
    if percentile < 25.0:
        return "Low"
    return "Medium"


def _recommended_action(tier: str, inbound_count: int) -> str:
    if tier == "Orphan":
        return "Add contextual internal links from hub pages and navigation."
    if tier == "Low" and inbound_count < UNDER_LINKED_INBOUND_THRESHOLD:
        return "Increase internal links from high-equity pages with descriptive anchors."
    if tier == "High":
        return "Maintain equity; ensure key CTAs are not buried below the fold."
    return "Monitor link distribution; diversify anchor text where generic."


def enrich_link_equity_fields(
    extra_rows: list[Any],
    graph_metrics: dict[str, dict[str, object]],
) -> None:
    """Add PageRank percentile, equity tier, and generic inbound share to extra rows."""
    percentiles = _pagerank_percentiles(graph_metrics)
    inbound = _inbound_anchor_index(extra_rows)

    for row in extra_rows:
        values = _row_values(row)
        url_key = normalize_url(
            str(values.get("Final URL") or values.get("URL") or "")
        )
        graph = graph_metrics.get(url_key, {})
        inbound_links = inbound.get(url_key, [])
        generic_count = sum(1 for link in inbound_links if link["generic"])
        inbound_count = len(inbound_links)
        generic_pct = (
            round((generic_count / inbound_count) * 100.0, 1) if inbound_count else 0.0
        )
        percentile = percentiles.get(url_key, 0.0)
        orphan = bool(graph.get("Orphan Pages"))
        tier = _equity_tier(orphan=orphan, percentile=percentile)
        values["PageRank Percentile"] = percentile
        values["Equity Tier"] = tier
        values["Inbound Internal Link Count"] = inbound_count
        values["Generic Inbound Anchor %"] = generic_pct
        values["Generic Anchor Dominance"] = (
            generic_pct > float(GENERIC_ANCHOR_DOMINANCE_PCT) and inbound_count > 0
        )


def build_link_equity_rows(
    extra_rows: list[dict[str, Any]],
    graph_metrics: dict[str, dict[str, object]],
) -> list[dict[str, Any]]:
    inbound = _inbound_anchor_index(extra_rows)
    percentiles = _pagerank_percentiles(graph_metrics)
    rows: list[dict[str, Any]] = []

    for row in extra_rows:
        url = str(row.get("URL") or row.get("Final URL") or "").strip()
        if not url:
            continue
        url_key = normalize_url(url)
        graph = graph_metrics.get(url_key, {})
        links = inbound.get(url_key, [])
        anchors = Counter(
            link["anchor"] or "(empty)"
            for link in links
            if link.get("anchor") is not None
        )
        top_anchors = [text for text, _ in anchors.most_common(5)]
        inbound_count = len(links)
        unique_sources = len({link["source"] for link in links})
        orphan = bool(graph.get("Orphan Pages"))
        percentile = percentiles.get(url_key, 0.0)
        tier = _equity_tier(orphan=orphan, percentile=percentile)
        depth = graph.get("Click Depth", CLICK_DEPTH_UNREACHABLE)
        rows.append(
            {
                "URL": url,
                "Inbound Link Count": inbound_count,
                "Unique Source Pages": unique_sources,
                "Anchor Texts (top 5)": " | ".join(top_anchors),
                "PageRank Score": graph.get("Internal PageRank", 0.0),
                "PageRank Percentile": percentile,
                "Click Depth": depth,
                "Equity Tier": tier,
                "Recommended Action": _recommended_action(tier, inbound_count),
            }
        )

    rows.sort(
        key=lambda item: (
            -float(item.get("PageRank Score") or 0.0),
            -int(item.get("Inbound Link Count") or 0),
        )
    )
    return rows


def build_anchor_text_audit_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inbound = _inbound_anchor_index(extra_rows)
    rows: list[dict[str, Any]] = []

    for dest, links in sorted(inbound.items(), key=lambda item: item[0]):
        if not links:
            continue
        generic_count = sum(1 for link in links if link["generic"])
        inbound_count = len(links)
        generic_pct = round((generic_count / inbound_count) * 100.0, 1)
        anchors = Counter(link["anchor"] or "(empty)" for link in links)
        dominance = generic_pct > float(GENERIC_ANCHOR_DOMINANCE_PCT)
        action = (
            "Rewrite generic anchors ('click here', 'read more') with descriptive text."
            if dominance
            else "Anchor mix looks acceptable; keep branded and partial-match variety."
        )
        rows.append(
            {
                "Destination URL": dest,
                "Inbound Link Count": inbound_count,
                "Generic Anchor Count": generic_count,
                "Generic Anchor %": generic_pct,
                "Top Anchor Texts": " | ".join(
                    text for text, _ in anchors.most_common(5)
                ),
                "Generic Anchor Dominance": dominance,
                "Recommended Action": action,
            }
        )

    rows.sort(key=lambda item: (-int(item["Inbound Link Count"]), item["Destination URL"]))
    return rows
