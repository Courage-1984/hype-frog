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
from hype_frog.crawler.psi_engine import psi_index_key
from hype_frog.pipeline.gsc_coverage import apply_gsc_coverage_fields
from hype_frog.pipeline.broken_links import count_broken_internal_from_link_details
from hype_frog.pipeline.content_cluster import compute_content_cluster_id
from hype_frog.pipeline.enrich import value_or_default
from hype_frog.pipeline.graph_engine import build_inlinks_map
from hype_frog.rules import (
    get_summary_rules,
    owner_for_issue,
    score_url_health,
    stable_issue_id,
)
from hype_frog.core.text_utils import normalize_text_hash, to_bool
from hype_frog.core.url_normalization import normalize_url


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


_AEO_SCORABLE_EXTRACTION: frozenset[str] = frozenset({"complete", "partial"})


def _answer_paragraph_aeo_points(row: Mapping[str, Any]) -> float:
    """Up to 30 points: 40–60 word paragraphs directly under question H2/H3."""
    n = int(float(row.get("Paragraphs 40-60 Words Count") or 0))
    if n <= 0:
        return 0.0
    return min(30.0, 15.0 * float(n))


def _answer_focused_schema_aeo_points(row: Mapping[str, Any]) -> float:
    """Up to 25 points: FAQPage/QAPage, HowTo, or Speakable-style JSON-LD."""
    if bool(row.get("QAPage/FAQ Schema Present")):
        return 25.0
    if bool(row.get("HowTo Signal")):
        return 25.0
    if bool(row.get("Speakable Schema Present")):
        return 25.0
    return 0.0


def _fk_readability_aeo_points(row: Mapping[str, Any]) -> float:
    """Up to 20 points: Flesch–Kincaid grade in the AEO 'sweet spot' (7–10)."""
    raw = row.get("Flesch-Kincaid Grade (Est.)")
    if raw is None or raw == "":
        return 10.0
    try:
        grade = float(raw)
    except (TypeError, ValueError):
        return 10.0
    if 7.0 <= grade <= 10.0:
        return 20.0
    if grade < 7.0:
        return max(0.0, 20.0 * (grade / 7.0))
    return max(0.0, 20.0 - 3.0 * (grade - 10.0))


def _structured_fragments_aeo_points(row: Mapping[str, Any]) -> float:
    """Up to 15 points: lists or tables for scannable, data-heavy sections."""
    return 15.0 if to_bool(row.get("List/Table Answer Signal")) else 0.0


def _ai_bot_robots_aeo_points(row: Mapping[str, Any]) -> float:
    """Up to 10 points: robots.txt mentions GPTBot, PerplexityBot, and CCBot (naive text match)."""
    raw = row.get("AEO Robots AI Bot Coverage")
    if raw is None or raw == "":
        return 5.0
    try:
        ratio = max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 5.0
    return 10.0 * ratio


def compute_aeo_readiness_score(row: Mapping[str, Any]) -> tuple[float, str]:
    """0–100 weighted AEO readiness (answer blocks, schema, readability, structure, robots).

    Weights: answer paragraphs 30%, answer-focused schema 25%, FK grade 20%,
    list/table structure 15%, robots AI-bot coverage 10%.

    Returns:
        Tuple of (score, badge). For rows without scorable HTML extraction, returns a neutral
        score above the ``Low AEO Readiness Score`` rule threshold (70).
    """
    extraction = str(row.get("Extraction State") or "").strip().lower()
    if extraction not in _AEO_SCORABLE_EXTRACTION:
        return 71.0, "Unmeasured"

    total = (
        _answer_paragraph_aeo_points(row)
        + _answer_focused_schema_aeo_points(row)
        + _fk_readability_aeo_points(row)
        + _structured_fragments_aeo_points(row)
        + _ai_bot_robots_aeo_points(row)
    )
    score = max(0.0, min(100.0, round(total, 2)))

    if score >= 80.0:
        badge = "Strong"
    elif score >= 70.0:
        badge = "Good"
    elif score >= 50.0:
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
        "Extraction Source": extra_values.get("Extraction Source")
        or main_values.get("Extraction Source", "raw_http"),
        "CWV LCP (s)": extra_values.get("CWV LCP (s)"),
        "CWV CLS": extra_values.get("CWV CLS"),
        "Field vs Lab": extra_values.get("Field vs Lab"),
        "CWV Data Source": extra_values.get("CWV Data Source"),
        "PSI Data Status": extra_values.get("PSI Data Status"),
        "Regional Authority Score": extra_values.get("Regional Authority Score"),
        "Desktop PSI Score": extra_values.get("Desktop PSI Score"),
        "Mobile PSI Score": extra_values.get("Mobile PSI Score"),
        "Mobile LCP (s)": extra_values.get("Mobile LCP (s)"),
        "Mobile CLS": extra_values.get("Mobile CLS"),
        "Mobile TTFB (s)": extra_values.get("Mobile TTFB (s)"),
        "GSC Clicks": extra_values.get("GSC Clicks"),
        "GSC Impressions": extra_values.get("GSC Impressions"),
        "GSC CTR": extra_values.get("GSC CTR"),
        "GSC Avg Position": extra_values.get("GSC Avg Position"),
        "GSC Data Freshness": extra_values.get("GSC Data Freshness"),
        "GSC Coverage Note": extra_values.get("GSC Coverage Note"),
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
        "Discovered On URL": (
            main_values.get("Discovered On URL")
            or extra_values.get("Discovered On URL")
            or ""
        ),
        "Technical Health": round(technical_health, 2),
        "Copy Score": round(copy_score, 2),
        "SEO Score": round(seo_score, 2),
    }
    validated = CrawlResultModel.model_validate(
        {"main": merged_row, "extra": extra_values}
    )
    return MainRowPayload.model_validate(validated.main)


def _lookup_psi_entry(
    psi_map: Mapping[str, Any],
    *,
    url_key: str,
    normalized_key: str,
    seed_url: str,
) -> dict[str, Any] | None:
    for key in (url_key, normalized_key, psi_index_key(seed_url), psi_index_key(url_key)):
        if key and key in psi_map:
            entry = psi_map[key]
            if isinstance(entry, dict):
                return entry
    return None


def _psi_numeric(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_with_psi_gsc_harden(
    row: ExtraRowPayload,
    *,
    url_key: str,
    normalized_key: str,
    psi_map: Mapping[str, Any],
    gsc_metrics: Mapping[str, Any],
    normalize_url_key_fn: Callable[[object], str] | None = None,
    gsc_analytics_succeeded: bool = False,
    gsc_data_freshness: str | None = None,
) -> ExtraRowPayload:
    norm = normalize_url_key_fn or normalize_url_key
    row_values = row.values
    seed_url = str(row_values.get("URL") or url_key or "").strip()
    psi = _lookup_psi_entry(
        psi_map,
        url_key=url_key,
        normalized_key=normalized_key,
        seed_url=seed_url,
    )
    if psi:
        mobile_lcp = _psi_numeric(psi.get("Mobile LCP"))
        mobile_cls = _psi_numeric(psi.get("Mobile CLS"))
        cwv_lcp = _psi_numeric(psi.get("CWV LCP (s)"))
        cwv_cls = _psi_numeric(psi.get("CWV CLS"))
        cwv_inp = _psi_numeric(psi.get("CWV INP (ms)"))
        merged: dict[str, object] = {
            **row_values,
            "PSI Data Status": psi.get("PSI Data Status", "Not available"),
            "Desktop PSI Score": psi.get("Desktop Score"),
            "Mobile PSI Score": psi.get("Mobile Score"),
            "Mobile LCP (s)": mobile_lcp,
            "Mobile CLS": mobile_cls,
            "Mobile TTFB (s)": _psi_numeric(psi.get("Mobile TTFB")),
            "CWV LCP (s)": cwv_lcp if cwv_lcp is not None else mobile_lcp,
            "CWV CLS": cwv_cls if cwv_cls is not None else mobile_cls,
            "CWV INP (ms)": cwv_inp,
            "CWV Data Source": psi.get("CWV Data Source", "None"),
            "Field vs Lab": psi.get("Field vs Lab", "N/A"),
        }
    elif psi_map:
        merged = {
            **row_values,
            "PSI Data Status": "Not available",
            "Field vs Lab": "N/A",
            "CWV Data Source": "None",
        }
    else:
        merged = {
            **row_values,
            "PSI Data Status": "Not measured (PSI disabled)",
        }
    apply_gsc_coverage_fields(
        merged,
        gsc_map=gsc_metrics,
        url_key=url_key,
        normalized_key=normalized_key,
        analytics_succeeded=gsc_analytics_succeeded,
        gsc_data_freshness=gsc_data_freshness,
    )
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
    link_details = row_values.get("Link Details") or []
    broken_internal = count_broken_internal_from_link_details(link_details)
    unresolved_internal = 0
    link_statuses: list[str] = []
    for target in row_values.get("Internal Links List Full", []):
        status = status_by_url.get(norm(target))
        if status is None:
            unresolved_internal += 1
        link_statuses.append(
            f"{target} => {status if status is not None else 'Not crawled'}"
        )
    if not link_details:
        broken_internal = 0
        for target in row_values.get("Internal Links List Full", []):
            status = status_by_url.get(norm(target))
            if isinstance(status, int) and status >= 400:
                broken_internal += 1
    out["Broken Internal Links Count"] = broken_internal
    out["Unresolved Internal Links Count"] = unresolved_internal
    out["Internal Link Statuses"] = (
        " | ".join(link_statuses) if link_statuses else None
    )
    return ExtraRowPayload.model_validate(out)


def row_with_seo_health_enrichment(
    row: ExtraRowPayload,
    *,
    summary_rules: list[IssueRule],
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


def row_with_aeo_readiness_fields(row: ExtraRowPayload) -> ExtraRowPayload:
    """Compute AEO readiness before ``Matched Issues`` so summary rules can match."""
    row_values = row.values
    aeo_score, aeo_badge = compute_aeo_readiness_score(row_values)
    return ExtraRowPayload.model_validate(
        {
            **row_values,
            "AEO Readiness Score": aeo_score,
            "AEO Badge": aeo_badge,
        }
    )


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
    "row_with_aeo_readiness_fields",
    "row_with_canonical_and_internal_links",
    "row_with_psi_gsc_harden",
    "row_with_seo_health_enrichment",
]
