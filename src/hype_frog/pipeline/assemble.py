from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

from hype_frog.models import CrawlResultModel, harden_page_row_metrics
from hype_frog.pipeline.content_cluster import compute_content_cluster_id
from hype_frog.pipeline.enrich import value_or_default
from hype_frog.pipeline.graph_engine import build_inlinks_map
from hype_frog.rules import (
    get_summary_rules,
    owner_for_issue,
    score_url_health,
    stable_issue_id,
)
from hype_frog.utils import normalize_text_hash, normalize_url_key


def compute_seo_technical_copy_scores(
    row: Mapping[str, Any],
) -> tuple[float, float, float]:
    """Return (Technical Health, Copy Score, SEO Score) from an enriched extra row."""
    base_score = value_or_default(row.get("SEO Health Score"), 0.0)
    lcp_value = value_or_default(row.get("Mobile LCP (s)"), 0.0)
    technical_health = max(
        0.0,
        min(
            100.0,
            base_score
            - (
                15
                if str(row.get("Canonical Type") or "")
                in {"missing", "cross-canonical"}
                else 0
            )
            - (10 if lcp_value > 4.0 else 5 if lcp_value > 2.5 else 0),
        ),
    )
    copy_score = max(
        0.0,
        min(
            100.0,
            100.0
            - (30 if bool(row.get("Missing H1 Flag")) else 0)
            - (20 if bool(row.get("Meta Description Missing")) else 0)
            - (25 if value_or_default(row.get("Word Count"), 0.0) < 300 else 0),
        ),
    )
    seo_score = max(
        0.0,
        min(
            100.0,
            (0.5 * base_score)
            + (0.25 * technical_health)
            + (0.25 * copy_score),
        ),
    )
    return technical_health, copy_score, seo_score


def assemble_enriched_row(
    main_data: dict[str, object],
    extra_data: dict[str, object],
    *,
    sitemap_url_keys: set[str],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> dict[str, object]:
    """
    Merge main tab fields from extra telemetry and attach composite scores.

    ``extra_data`` must already include ``SEO Health Score``, ``Severity Badge``,
    and related fields from ``row_with_seo_health_enrichment`` (same row dicts
    written to the Technical sheet). Returns a new dict; inputs are not mutated.
    """
    norm = normalize_url_key_fn or normalize_url_key
    technical_health, copy_score, seo_score = compute_seo_technical_copy_scores(
        extra_data
    )
    url_norm = norm(main_data.get("URL"))
    found_via_sitemap = bool(url_norm and url_norm in sitemap_url_keys)
    found_via_crawl = bool(url_norm)
    merged_row = {
        **main_data,
        "SEO Health Score": extra_data.get("SEO Health Score"),
        "Severity Badge": extra_data.get("Severity Badge"),
        "Health Icon": extra_data.get("Health Icon"),
        "Extraction State": main_data.get("Extraction State")
        or extra_data.get("Extraction State", "skipped"),
        "Extraction Source": main_data.get("Extraction Source")
        or extra_data.get("Extraction Source", "raw_http"),
        "CWV LCP (s)": extra_data.get("CWV LCP (s)"),
        "CWV CLS": extra_data.get("CWV CLS"),
        "Field vs Lab": extra_data.get("Field vs Lab"),
        "Regional Authority Score": extra_data.get("Regional Authority Score"),
        "Desktop PSI Score": extra_data.get("Desktop PSI Score", 0),
        "Mobile PSI Score": extra_data.get("Mobile PSI Score", 0),
        "Mobile LCP (s)": extra_data.get("Mobile LCP (s)", 0.0),
        "Mobile CLS": extra_data.get("Mobile CLS", 0.0),
        "Mobile TTFB (s)": extra_data.get("Mobile TTFB (s)", 0.0),
        "GSC Clicks": extra_data.get("GSC Clicks", 0.0),
        "GSC Impressions": extra_data.get("GSC Impressions", 0.0),
        "GSC CTR": extra_data.get("GSC CTR", 0.0),
        "GSC Avg Position": extra_data.get("GSC Avg Position", 0.0),
        "Click Depth": extra_data.get("Click Depth"),
        "Orphan Pages": extra_data.get("Orphan Pages", False),
        "Internal PageRank": extra_data.get("Internal PageRank", 0.0),
        "Found via Sitemap": found_via_sitemap,
        "Found via Crawl": found_via_crawl,
        "Discovery Source": (
            "Both"
            if found_via_sitemap and found_via_crawl
            else "Sitemap"
            if found_via_sitemap
            else "Crawl"
        ),
        "Technical Health": round(technical_health, 2),
        "Copy Score": round(copy_score, 2),
        "SEO Score": round(seo_score, 2),
    }
    validated = CrawlResultModel.model_validate({"main": merged_row, "extra": extra_data})
    return validated.main


def row_with_psi_gsc_harden(
    row: dict[str, object],
    *,
    url_key: str,
    normalized_key: str,
    psi_map: Mapping[str, Any],
    gsc_metrics: Mapping[str, Any],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> dict[str, object]:
    norm = normalize_url_key_fn or normalize_url_key
    psi = psi_map.get(url_key) or psi_map.get(normalized_key)
    if psi:
        merged: dict[str, object] = {
            **row,
            "Desktop PSI Score": psi.get("Desktop Score", 0),
            "Mobile PSI Score": psi.get("Mobile Score", 0),
            "Mobile LCP (s)": psi.get("Mobile LCP", 0.0),
            "Mobile CLS": psi.get("Mobile CLS", 0.0),
            "Mobile TTFB (s)": psi.get("Mobile TTFB", 0.0),
            "CWV LCP (s)": psi.get("Mobile LCP", 0.0),
            "CWV CLS": psi.get("Mobile CLS", 0.0),
            "CWV Data Source": "PSI API",
            "Field vs Lab": "Lab",
        }
    else:
        merged = {
            **row,
            "Desktop PSI Score": 0,
            "Mobile PSI Score": 0,
            "Mobile LCP (s)": 0.0,
            "Mobile CLS": 0.0,
            "Mobile TTFB (s)": 0.0,
        }
    gsc = gsc_metrics.get(url_key) or gsc_metrics.get(normalized_key)
    if gsc:
        merged = {
            **merged,
            "GSC Clicks": gsc.get("GSC Clicks", 0.0),
            "GSC Impressions": gsc.get("GSC Impressions", 0.0),
            "GSC CTR": gsc.get("GSC CTR", 0.0),
            "GSC Avg Position": gsc.get("GSC Average Position", 0.0),
        }
    else:
        merged = {
            **merged,
            "GSC Clicks": 0.0,
            "GSC Impressions": 0.0,
            "GSC CTR": 0.0,
            "GSC Avg Position": 0.0,
        }
    return {**merged, **harden_page_row_metrics(merged)}


def row_with_canonical_and_internal_links(
    row: dict[str, object],
    *,
    crawled_finals: set[str],
    status_by_url: Mapping[str, object],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> dict[str, object]:
    norm = normalize_url_key_fn or normalize_url_key
    canonical_url = row.get("Canonical URL")
    url_val = row.get("URL")
    out = dict(row)
    if canonical_url and url_val:
        out["Canonical in Sitemap Match"] = norm(canonical_url) == norm(url_val)
    else:
        out["Canonical in Sitemap Match"] = row.get("Canonical in Sitemap Match")
    out["Hreflang Canonical Consistency"] = (
        (
            bool(row.get("Hreflang Present"))
            and row.get("Canonical Type") in {"self", "missing"}
        )
        if row.get("Hreflang Present")
        else None
    )
    if row.get("Hreflang Present"):
        out["Hreflang Reciprocal Check"] = norm(
            row.get("Final URL", "")
        ) in crawled_finals and bool(row.get("Hreflang Self Reference"))
    broken_internal = 0
    unresolved_internal = 0
    link_statuses: list[str] = []
    for target in row.get("Internal Links List Full", []):
        status = status_by_url.get(norm(target))
        if isinstance(status, int) and status >= 400:
            broken_internal += 1
        elif status is None:
            unresolved_internal += 1
        link_statuses.append(
            f"{target} => {status if status is not None else 'Not crawled'}"
        )
    out["Broken Internal Links Count"] = broken_internal
    out["Unresolved Internal Links Count"] = unresolved_internal
    out["Internal Link Statuses"] = (
        " | ".join(link_statuses) if link_statuses else None
    )
    return out


def row_with_seo_health_enrichment(
    row: dict[str, object],
    *,
    summary_rules: list[tuple[str, str, Any]],
    sitemap_url_keys: set[str],
    graph_metrics: Mapping[str, Mapping[str, Any]],
    inlinks_map: Mapping[str, set[str]],
    title_map: Mapping[str, list[Any]],
    meta_map: Mapping[str, list[Any]],
    segment_by_url: Mapping[Any, str],
    main_by_url: Mapping[str, dict[str, object]],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> dict[str, object]:
    norm = normalize_url_key_fn or normalize_url_key
    score, badge, icon, matched = score_url_health(row, summary_rules)
    row_url_norm = norm(row.get("Final URL") or row.get("URL"))
    base: dict[str, object] = {
        **row,
        "Found via Sitemap": bool(row_url_norm and row_url_norm in sitemap_url_keys),
        "Found via Crawl": bool(row_url_norm),
    }
    found_sitemap = base["Found via Sitemap"]
    found_crawl = base["Found via Crawl"]
    base["Discovery Source"] = (
        "Both"
        if found_sitemap and found_crawl
        else "Sitemap"
        if found_sitemap
        else "Crawl"
    )
    base["SEO Health Score"] = score if score is not None else None
    base["Severity Badge"] = badge
    base["Health Icon"] = icon
    if badge == "Unmeasured":
        base["Critical Issues Count"] = None
        base["Warning Issues Count"] = None
        base["Observation Issues Count"] = None
        base["Matched Issues"] = "Unmeasured"
        base["Action Needed"] = ""
    else:
        base["Critical Issues Count"] = len(matched["Critical"])
        base["Warning Issues Count"] = len(matched["Warning"])
        base["Observation Issues Count"] = len(matched["Observation"])
        base["Matched Issues"] = " | ".join(
            matched["Critical"] + matched["Warning"] + matched["Observation"]
        )
        base["Action Needed"] = "Yes" if badge in {"Critical", "Warning"} else "No"
    top_issue = (
        (matched["Critical"] + matched["Warning"] + matched["Observation"])[0]
        if (matched["Critical"] + matched["Warning"] + matched["Observation"])
        else ""
    )
    base["Owner"] = owner_for_issue(top_issue, badge)
    base["Sprint"] = ""
    base["Status"] = "Open"
    all_issue_ids = [
        stable_issue_id(row.get("URL"), issue)
        for issue in matched["Critical"]
        + matched["Warning"]
        + matched["Observation"]
    ]
    base["Stable Issue IDs"] = " | ".join(all_issue_ids) if all_issue_ids else None
    final_norm = norm(row.get("Final URL") or row.get("URL") or "")
    inlinks_count = len(inlinks_map.get(final_norm, set()))
    graph_row = graph_metrics.get(final_norm, {})
    base["Click Depth"] = graph_row.get("Click Depth")
    base["Orphan Pages"] = bool(graph_row.get("Orphan Pages", inlinks_count == 0))
    base["Internal PageRank"] = graph_row.get("Internal PageRank", 0.0)
    base["Internal Inlinks"] = graph_row.get("Internal Inlinks", inlinks_count)
    base["Inlinks Bucket"] = (
        "0"
        if inlinks_count == 0
        else "1-2"
        if inlinks_count <= 2
        else "3-10"
        if inlinks_count <= 10
        else "10+"
    )
    if badge == "Unmeasured":
        base["Important But Underlinked"] = None
    else:
        base["Important But Underlinked"] = (
            value_or_default(score, 0.0) < 70 and inlinks_count <= 2
        )
    url_for_hint = row.get("URL")
    main_match = main_by_url.get(str(url_for_hint or "").strip(), {})
    title_key = normalize_text_hash(main_match.get("Title"))
    meta_key = normalize_text_hash(main_match.get("Meta Description"))
    hints: list[str] = []
    if title_key and len(title_map.get(title_key, [])) > 1:
        hints.append("Near-duplicate title cluster")
        seg_set = {
            segment_by_url.get(u)
            for u in title_map.get(title_key, [])
            if segment_by_url.get(u)
        }
        if len(seg_set) == 1:
            hints.append("Shared path segment pattern")
    if meta_key and len(meta_map.get(meta_key, [])) > 1:
        hints.append("Near-duplicate meta description cluster")
    if hints:
        base["Cannibalization Hint"] = " | ".join(hints)
    validated = CrawlResultModel.model_validate({"main": {}, "extra": base})
    return validated.extra


def enrich_extra_rows_with_composite_scores(
    rows: list[dict[str, object]],
    *,
    main_by_url: Mapping[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for r in rows:
        th, cs, seo = compute_seo_technical_copy_scores(r)
        merged: dict[str, object] = {
            **r,
            "Technical Health": round(th, 2),
            "Copy Score": round(cs, 2),
            "SEO Score": round(seo, 2),
        }
        if main_by_url is not None:
            m = main_by_url.get(str(r.get("URL") or "").strip(), {})
            tit = str(m.get("Title") or "").strip()
            h1ish = str(
                m.get("H1 Content") or r.get("Current H-Tag Structure") or ""
            ).strip()
            merged["Content Cluster ID"] = compute_content_cluster_id(
                r.get("URL"), title=tit, h1_or_structure=h1ish
            )
        out.append(merged)
    return out


def build_title_meta_segment_maps(
    main_rows: list[dict[str, object]],
) -> tuple[
    defaultdict[str, list[str]],
    defaultdict[str, list[str]],
    dict[str, str],
]:
    title_map: defaultdict[str, list[str]] = defaultdict(list)
    meta_map: defaultdict[str, list[str]] = defaultdict(list)
    segment_by_url: dict[str, str] = {}
    for mrow in main_rows:
        t_key = normalize_text_hash(mrow.get("Title"))
        d_key = normalize_text_hash(mrow.get("Meta Description"))
        parsed_u = urlparse(str(mrow.get("URL") or ""))
        segs = [s for s in parsed_u.path.strip("/").split("/") if s]
        u = mrow.get("URL")
        if u is not None:
            segment_by_url[str(u)] = segs[0] if segs else "(home)"
        if t_key:
            title_map[t_key].append(mrow.get("URL"))
        if d_key:
            meta_map[d_key].append(mrow.get("URL"))
    return title_map, meta_map, segment_by_url


def main_by_url_map(
    main_rows: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        str(r.get("URL") or "").strip(): r
        for r in main_rows
        if r.get("URL")
    }


def passthrough_assemble_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return rows


__all__ = [
    "assemble_enriched_row",
    "build_inlinks_map",
    "build_title_meta_segment_maps",
    "compute_seo_technical_copy_scores",
    "enrich_extra_rows_with_composite_scores",
    "main_by_url_map",
    "passthrough_assemble_rows",
    "row_with_canonical_and_internal_links",
    "row_with_psi_gsc_harden",
    "row_with_seo_health_enrichment",
]
