from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

from hype_frog.core.models import (
    CrawlResultModel,
    ExtraRowPayload,
    MainRowPayload,
    harden_page_row_metrics,
)
from hype_frog.pipeline.content_cluster import compute_content_cluster_id
from hype_frog.pipeline.enrich import value_or_default
from hype_frog.pipeline.graph_engine import build_inlinks_map
from hype_frog.rules import (
    get_summary_rules,
    owner_for_issue,
    score_url_health,
    stable_issue_id,
)
from hype_frog.core.text_utils import normalize_text_hash
from hype_frog.core.url_normalization import normalize_url


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


_AEO_SCORABLE_EXTRACTION: frozenset[str] = frozenset({"complete", "partial"})


def compute_aeo_readiness_score(row: Mapping[str, Any]) -> tuple[float, str]:
    """0–100 AEO readiness from on-page signals (schema, headings, extractability, answer blocks).

    Returns:
        Tuple of (score, badge). For rows without scorable HTML extraction, returns a neutral
        score that does not trigger the ``Low AEO Readiness Score`` rule threshold.
    """
    extraction = str(row.get("Extraction State") or "").strip().lower()
    if extraction not in _AEO_SCORABLE_EXTRACTION:
        return 61.0, "Unmeasured"

    base = 10.0
    schema_count = int(float(row.get("Schema Types Count") or 0))
    schema_pts = 20.0 if schema_count > 0 else 0.0

    qh = int(float(row.get("Question Heading Count") or 0))
    question_pts = min(30.0, float(qh) * 10.0)

    ext = str(row.get("AEO Extractability Score") or "").strip().lower()
    para_n = int(float(row.get("Paragraphs 40-60 Words Count") or 0))
    if ext == "high" or para_n > 0:
        extract_pts = 40.0
    elif ext == "medium":
        extract_pts = 20.0
    else:
        extract_pts = 0.0

    total = base + schema_pts + question_pts + extract_pts
    score = max(0.0, min(100.0, round(total, 2)))

    if score >= 80.0:
        badge = "Strong"
    elif score >= 60.0:
        badge = "Good"
    elif score >= 40.0:
        badge = "Fair"
    else:
        badge = "Needs Work"
    return score, badge


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
    wc = float(value_or_default(row.get("Word Count"), 0.0))
    if wc >= 300.0:
        thin_penalty = 0.0
    else:
        thin_penalty = min(25.0, ((300.0 - wc) / 300.0) * 25.0)
    copy_score = max(
        0.0,
        min(
            100.0,
            100.0
            - (30 if bool(row.get("Missing H1 Flag")) else 0)
            - (20 if bool(row.get("Meta Description Missing")) else 0)
            - thin_penalty,
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
    # Broken pages should never surface as healthy in executive scoring.
    try:
        status_code = int(float(row.get("Status Code") or 0))
    except (TypeError, ValueError):
        status_code = 0
    if status_code >= 400:
        seo_score = min(seo_score, 5.0)
    return technical_health, copy_score, seo_score


def assemble_enriched_row(
    main_data: MainRowPayload,
    extra_data: ExtraRowPayload,
    *,
    sitemap_url_keys: set[str],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> MainRowPayload:
    """
    Merge main tab fields from extra telemetry and attach composite scores.

    ``extra_data`` must already include ``SEO Health Score``, ``Severity Badge``,
    and related fields from ``row_with_seo_health_enrichment`` (same row dicts
    written to the Technical sheet). Returns a new dict; inputs are not mutated.
    """
    norm = normalize_url_key_fn or normalize_url_key
    main_values = main_data.values
    extra_values = extra_data.values
    technical_health, copy_score, seo_score = compute_seo_technical_copy_scores(
        extra_values
    )
    url_norm = norm(main_values.get("URL"))
    found_via_sitemap = bool(url_norm and url_norm in sitemap_url_keys)
    found_via_crawl = bool(url_norm)
    merged_row = {
        **main_values,
        "SEO Health Score": extra_values.get("SEO Health Score"),
        "Severity Badge": extra_values.get("Severity Badge"),
        "Health Icon": extra_values.get("Health Icon"),
        "Extraction State": main_values.get("Extraction State")
        or extra_values.get("Extraction State", "skipped"),
        "Extraction Source": main_values.get("Extraction Source")
        or extra_values.get("Extraction Source", "raw_http"),
        "CWV LCP (s)": extra_values.get("CWV LCP (s)"),
        "CWV CLS": extra_values.get("CWV CLS"),
        "Field vs Lab": extra_values.get("Field vs Lab"),
        "Regional Authority Score": extra_values.get("Regional Authority Score"),
        "Desktop PSI Score": extra_values.get("Desktop PSI Score", 0),
        "Mobile PSI Score": extra_values.get("Mobile PSI Score", 0),
        "Mobile LCP (s)": extra_values.get("Mobile LCP (s)", 0.0),
        "Mobile CLS": extra_values.get("Mobile CLS", 0.0),
        "Mobile TTFB (s)": extra_values.get("Mobile TTFB (s)", 0.0),
        "GSC Clicks": extra_values.get("GSC Clicks", 0.0),
        "GSC Impressions": extra_values.get("GSC Impressions", 0.0),
        "GSC CTR": extra_values.get("GSC CTR", 0.0),
        "GSC Avg Position": extra_values.get("GSC Avg Position", 0.0),
        "Click Depth": extra_values.get("Click Depth"),
        "Orphan Pages": extra_values.get("Orphan Pages", False),
        "Internal PageRank": extra_values.get("Internal PageRank", 0.0),
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
    validated = CrawlResultModel.model_validate(
        {"main": merged_row, "extra": extra_values}
    )
    return MainRowPayload.model_validate(validated.main)


def row_with_psi_gsc_harden(
    row: ExtraRowPayload,
    *,
    url_key: str,
    normalized_key: str,
    psi_map: Mapping[str, Any],
    gsc_metrics: Mapping[str, Any],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> ExtraRowPayload:
    norm = normalize_url_key_fn or normalize_url_key
    row_values = row.values
    psi = psi_map.get(url_key) or psi_map.get(normalized_key)
    if psi:
        merged: dict[str, object] = {
            **row_values,
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
            **row_values,
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
    return ExtraRowPayload.model_validate({**merged, **harden_page_row_metrics(merged)})


def row_with_canonical_and_internal_links(
    row: ExtraRowPayload,
    *,
    crawled_finals: set[str],
    status_by_url: Mapping[str, object],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> ExtraRowPayload:
    norm = normalize_url_key_fn or normalize_url_key
    row_values = row.values
    canonical_url = row_values.get("Canonical URL")
    url_val = row_values.get("URL")
    out = dict(row_values)
    if canonical_url and url_val:
        out["Canonical in Sitemap Match"] = norm(canonical_url) == norm(url_val)
    else:
        out["Canonical in Sitemap Match"] = row_values.get("Canonical in Sitemap Match")
    out["Hreflang Canonical Consistency"] = (
        (
            bool(row_values.get("Hreflang Present"))
            and row_values.get("Canonical Type") in {"self", "missing"}
        )
        if row_values.get("Hreflang Present")
        else None
    )
    if row_values.get("Hreflang Present"):
        out["Hreflang Reciprocal Check"] = norm(
            row_values.get("Final URL", "")
        ) in crawled_finals and bool(row_values.get("Hreflang Self Reference"))
    broken_internal = 0
    unresolved_internal = 0
    link_statuses: list[str] = []
    for target in row_values.get("Internal Links List Full", []):
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
    return ExtraRowPayload.model_validate(out)


def row_with_seo_health_enrichment(
    row: ExtraRowPayload,
    *,
    summary_rules: list[tuple[str, str, Any]],
    sitemap_url_keys: set[str],
    graph_metrics: Mapping[str, Mapping[str, Any]],
    inlinks_map: Mapping[str, set[str]],
    title_map: Mapping[str, list[Any]],
    meta_map: Mapping[str, list[Any]],
    segment_by_url: Mapping[Any, str],
    main_by_url: Mapping[str, MainRowPayload],
    normalize_url_key_fn: Callable[[object], str] | None = None,
) -> ExtraRowPayload:
    norm = normalize_url_key_fn or normalize_url_key
    row_values = row.values
    score, badge, icon, matched = score_url_health(row_values, summary_rules)
    row_url_norm = norm(row_values.get("Final URL") or row_values.get("URL"))
    base: dict[str, object] = {
        **row_values,
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
        stable_issue_id(row_values.get("URL"), issue)
        for issue in matched["Critical"]
        + matched["Warning"]
        + matched["Observation"]
    ]
    base["Stable Issue IDs"] = " | ".join(all_issue_ids) if all_issue_ids else None
    final_norm = norm(row_values.get("Final URL") or row_values.get("URL") or "")
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
    url_for_hint = row_values.get("URL")
    main_match = main_by_url.get(str(url_for_hint or "").strip())
    main_values = main_match.values if main_match else {}
    title_key = normalize_text_hash(main_values.get("Title"))
    meta_key = normalize_text_hash(main_values.get("Meta Description"))
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
    return ExtraRowPayload.model_validate(validated.extra)


def enrich_extra_rows_with_composite_scores(
    rows: list[ExtraRowPayload],
    *,
    main_by_url: Mapping[str, MainRowPayload] | None = None,
) -> list[ExtraRowPayload]:
    out: list[ExtraRowPayload] = []
    for r in rows:
        row_values = r.values
        th, cs, seo = compute_seo_technical_copy_scores(row_values)
        aeo_score, aeo_badge = compute_aeo_readiness_score(row_values)
        merged: dict[str, object] = {
            **row_values,
            "Technical Health": round(th, 2),
            "Copy Score": round(cs, 2),
            "SEO Score": round(seo, 2),
            "AEO Readiness Score": aeo_score,
            "AEO Badge": aeo_badge,
        }
        if main_by_url is not None:
            m = main_by_url.get(str(row_values.get("URL") or "").strip())
            main_values = m.values if m else {}
            tit = str(main_values.get("Title") or "").strip()
            h1ish = str(
                main_values.get("H1 Content")
                or row_values.get("Current H-Tag Structure")
                or ""
            ).strip()
            merged["Content Cluster ID"] = compute_content_cluster_id(
                row_values.get("URL"), title=tit, h1_or_structure=h1ish
            )
        out.append(ExtraRowPayload.model_validate(merged))
    return out


def build_title_meta_segment_maps(
    main_rows: list[MainRowPayload],
) -> tuple[
    defaultdict[str, list[str]],
    defaultdict[str, list[str]],
    dict[str, str],
]:
    title_map: defaultdict[str, list[str]] = defaultdict(list)
    meta_map: defaultdict[str, list[str]] = defaultdict(list)
    segment_by_url: dict[str, str] = {}
    for mrow in main_rows:
        row = mrow.values
        t_key = normalize_text_hash(row.get("Title"))
        d_key = normalize_text_hash(row.get("Meta Description"))
        parsed_u = urlparse(str(row.get("URL") or ""))
        segs = [s for s in parsed_u.path.strip("/").split("/") if s]
        u = row.get("URL")
        if u is not None:
            segment_by_url[str(u)] = segs[0] if segs else "(home)"
        if t_key:
            title_map[t_key].append(row.get("URL"))
        if d_key:
            meta_map[d_key].append(row.get("URL"))
    return title_map, meta_map, segment_by_url


def main_by_url_map(
    main_rows: list[MainRowPayload],
) -> dict[str, MainRowPayload]:
    return {
        str(r.values.get("URL") or "").strip(): r
        for r in main_rows
        if r.values.get("URL")
    }


def passthrough_assemble_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return rows


__all__ = [
    "assemble_enriched_row",
    "build_inlinks_map",
    "build_title_meta_segment_maps",
    "compute_aeo_readiness_score",
    "compute_seo_technical_copy_scores",
    "enrich_extra_rows_with_composite_scores",
    "main_by_url_map",
    "passthrough_assemble_rows",
    "row_with_canonical_and_internal_links",
    "row_with_psi_gsc_harden",
    "row_with_seo_health_enrichment",
]
