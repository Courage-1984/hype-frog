"""WI3 extraction investigation: snapshot distributions + Playwright re-parse compare.

Read-only investigation harness — does not modify production metrics.
Outputs JSON to stdout or a path for findings doc assembly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from hype_frog.core.text_utils import to_bool
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.crawler.network_engine import fetch_rendered_with_diagnostics
from hype_frog.extractors import extract_aeo_snippets, extract_heading_outline, extract_json_ld_blocks
from hype_frog.extractors.page import HeadingOutline
from hype_frog.extractors.schema import parse_jsonld_summary
from hype_frog.extractors.semantic_engine import SemanticAnalyzer, count_citation_candidates
from hype_frog.pipeline.assemble import (
    _ai_bot_robots_aeo_points,
    _answer_focused_schema_aeo_points,
    _answer_paragraph_aeo_points,
    _fk_readability_aeo_points,
    _structured_fragments_aeo_points,
    compute_aeo_readiness_score,
)
from hype_frog.snapshots.store import load_crawl_snapshot_by_id
from hype_frog.validators.schema_validator import validate_schemas_from_html

_NON_CONTENT_SELECTOR = (
    "nav, header, footer, aside, script, style, noscript, template, "
    "[role='navigation'], [role='banner'], [role='contentinfo'], [role='complementary']"
)

DOMAIN = "africanmarketingconfederation.org"
SNAPSHOT_ID = "b513adec-d888-4037-aeba-5b26b68fe609"
RENDER_WAIT_MS = 2000
SELECTOR_WAIT_MS = 1500


def _primary_paragraphs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    primary = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", attrs={"role": "main"})
    )
    source_html = str(primary) if primary is not None else html
    content_soup = BeautifulSoup(source_html, "lxml")
    for tag in content_soup.select(_NON_CONTENT_SELECTOR):
        tag.decompose()
    region = content_soup.body or content_soup
    return [
        p.get_text(" ", strip=True)
        for p in region.find_all("p")
        if p.get_text(" ", strip=True)
    ]


def _question_headings_from_outline(outline: HeadingOutline) -> list[str]:
    texts: list[str] = []
    for level in range(1, 7):
        for text in outline.headings_by_level.get(level, ()):
            if text.endswith("?"):
                texts.append(f"H{level}: {text}")
    return texts


def _image_alt_coverage(html: str) -> tuple[int, int, float | None]:
    soup = BeautifulSoup(html, "lxml")
    images = soup.find_all("img")
    if not images:
        return 0, 0, None
    missing = sum(1 for img in images if not str(img.get("alt") or "").strip())
    total = len(images)
    return total, missing, round(((max(0, total - missing) / total) * 100), 2)


def _aeo_score_breakdown(row: dict[str, Any]) -> dict[str, float]:
    return {
        "answer_paragraph_pts": _answer_paragraph_aeo_points(row),
        "schema_pts": _answer_focused_schema_aeo_points(row),
        "fk_readability_pts": _fk_readability_aeo_points(row),
        "list_table_pts": _structured_fragments_aeo_points(row),
        "robots_ai_pts": _ai_bot_robots_aeo_points(row),
    }


def _row_by_url(extra_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {normalize_url_key(str(r.get("URL") or "")): r for r in extra_rows if r.get("URL")}


def analyze_distributions(extra_rows: list[dict[str, Any]]) -> dict[str, Any]:
    para_counts = Counter(int(r.get("Paragraphs 40-60 Words Count") or 0) for r in extra_rows)
    aeo_scores = Counter(round(float(r.get("AEO Readiness Score") or 0), 2) for r in extra_rows)
    q_counts = Counter(int(r.get("Question Heading Count") or 0) for r in extra_rows)
    extractability = Counter(str(r.get("AEO Extractability Score") or "") for r in extra_rows)
    citation_counts = Counter(int(r.get("Citation Candidate Count") or 0) for r in extra_rows)

    plateau_urls = [
        str(r["URL"])
        for r in extra_rows
        if round(float(r.get("AEO Readiness Score") or 0), 2) == 14.33
    ][:3]
    high_urls = [
        str(r["URL"])
        for r in extra_rows
        if round(float(r.get("AEO Readiness Score") or 0), 2) == 71.0
    ][:2]
    question_urls = [
        str(r["URL"])
        for r in extra_rows
        if int(r.get("Question Heading Count") or 0) > 0
    ][:2]

    raw_http_urls = [
        str(r["URL"])
        for r in extra_rows
        if str(r.get("Extraction Source") or "").strip() == "raw_http"
    ][:1]

    plateau_samples = []
    for url in plateau_urls[:2]:
        row = _row_by_url(extra_rows).get(normalize_url_key(url), {})
        breakdown = _aeo_score_breakdown(row)
        score, badge = compute_aeo_readiness_score(row)
        plateau_samples.append(
            {
                "url": url,
                "workbook_aeo_score": row.get("AEO Readiness Score"),
                "recomputed_score": score,
                "badge": badge,
                "fk_grade": row.get("Flesch-Kincaid Grade (Est.)"),
                "breakdown": breakdown,
                "paragraphs_40_60": row.get("Paragraphs 40-60 Words Count"),
                "citation_candidates": row.get("Citation Candidate Count"),
                "list_table_signal": row.get("List/Table Answer Signal"),
                "schema_faq": row.get("QAPage/FAQ Schema Present"),
                "robots_coverage": row.get("AEO Robots AI Bot Coverage"),
            }
        )

    return {
        "row_count": len(extra_rows),
        "paragraphs_40_60_distribution": dict(para_counts.most_common(10)),
        "paragraphs_40_60_all_zero": all(
            int(r.get("Paragraphs 40-60 Words Count") or 0) == 0 for r in extra_rows
        ),
        "aeo_score_top": aeo_scores.most_common(10),
        "aeo_score_14_33_count": aeo_scores.get(14.33, 0),
        "question_heading_distribution": dict(q_counts.most_common(5)),
        "question_heading_zero_pct": round(100 * q_counts.get(0, 0) / max(len(extra_rows), 1), 1),
        "extractability_labels": dict(extractability.most_common(5)),
        "citation_candidate_distribution": dict(citation_counts.most_common(10)),
        "citation_nonzero_count": sum(1 for c in citation_counts if c > 0),
        "plateau_samples": plateau_samples,
        "selected_urls": {
            "plateau": plateau_urls[:1] or [str(extra_rows[0].get("URL"))],
            "high": high_urls[:1],
            "question": question_urls[:1],
            "raw_http": raw_http_urls[:1],
        },
    }


def extract_from_html(url: str, html: str) -> dict[str, Any]:
    outline = extract_heading_outline(html)
    snippets = extract_aeo_snippets(html)
    paragraphs = _primary_paragraphs(html)
    analyzer = SemanticAnalyzer()
    body_text = " ".join(paragraphs)
    semantic = analyzer.analyze(body_text=body_text, paragraphs=paragraphs or None)
    citation_wide = count_citation_candidates(body_text=body_text, paragraphs=paragraphs or None)
    img_total, img_missing, alt_pct = _image_alt_coverage(html)
    schema_summary = parse_jsonld_summary(html)
    json_ld = extract_json_ld_blocks(html)
    schema_result = validate_schemas_from_html(url, json_ld)
    question_from_snippets = len({s["heading"] for s in snippets})
    q_count = max(outline.question_heading_count, question_from_snippets)

    return {
        "h1_count": outline.h1_count,
        "question_heading_count": q_count,
        "question_headings": _question_headings_from_outline(outline),
        "strict_snippets_count": len(snippets),
        "strict_snippets_sample": snippets[:3],
        "citation_candidate_count": citation_wide,
        "semantic_citation_count": semantic.get("citation_count"),
        "semantic_analysis_mode": semantic.get("analysis_mode"),
        "image_total": img_total,
        "images_missing_alt": img_missing,
        "image_alt_coverage_pct": alt_pct,
        "schema_types_count": len(schema_result.types_found)
        or int(schema_summary.get("schema_types_count") or 0),
        "schema_types_found": schema_result.types_found or schema_summary.get("schema_types"),
    }


async def compare_url(url: str, snapshot_row: dict[str, Any] | None) -> dict[str, Any]:
    diag = await fetch_rendered_with_diagnostics(
        url,
        render_wait_ms=RENDER_WAIT_MS,
        selector_wait_ms=SELECTOR_WAIT_MS,
    )
    html = diag.get("html") or diag.get("raw_html") or ""
    extracted = extract_from_html(url, html) if html else {}

    snap = snapshot_row or {}
    snap_score, snap_badge = compute_aeo_readiness_score(snap) if snap else (None, None)

    # Build synthetic row from re-extraction for score what-if (read-only)
    synthetic_row = dict(snap)
    synthetic_row.update(
        {
            "Paragraphs 40-60 Words Count": extracted.get("strict_snippets_count", 0),
            "Question Heading Count": extracted.get("question_heading_count", 0),
            "Extraction State": "partial",
        }
    )
    recompute_score, recompute_badge = compute_aeo_readiness_score(synthetic_row)
    recompute_breakdown = _aeo_score_breakdown(synthetic_row)

    return {
        "url": url,
        "playwright": {
            "extraction_state": diag.get("extraction_state"),
            "extraction_source": diag.get("extraction_source"),
            "rendered_word_count": diag.get("rendered_word_count"),
            "is_js_dependent": diag.get("is_js_dependent"),
            "html_bytes": len(html),
        },
        "snapshot": {
            "extraction_source": snap.get("Extraction Source"),
            "extraction_state": snap.get("Extraction State"),
            "question_heading_count": snap.get("Question Heading Count"),
            "paragraphs_40_60": snap.get("Paragraphs 40-60 Words Count"),
            "answer_blocks_export": snap.get("Paragraphs 40-60 Words Count"),
            "citation_candidate_count": snap.get("Citation Candidate Count"),
            "image_alt_coverage_pct": snap.get("Image Alt Coverage (%)"),
            "aeo_readiness_score": snap.get("AEO Readiness Score"),
            "aeo_badge": snap.get("AEO Badge"),
            "aeo_extractability": snap.get("AEO Extractability Score"),
            "h1_count": snap.get("H1 Count"),
            "schema_types_count": snap.get("Schema Types Count"),
            "computed_score": snap_score,
            "score_breakdown": _aeo_score_breakdown(snap) if snap else {},
        },
        "reextracted_on_playwright_html": extracted,
        "synthetic_recompute": {
            "score": recompute_score,
            "badge": recompute_badge,
            "breakdown": recompute_breakdown,
            "note": "Uses snapshot row + re-extracted paragraph/question counts only",
        },
    }


async def run_investigation(snapshot_id: str, output: Path | None) -> dict[str, Any]:
    snapshot = load_crawl_snapshot_by_id(snapshot_id)
    if snapshot is None:
        raise SystemExit(f"Snapshot not found: {snapshot_id}")

    extra_rows = snapshot.extra_rows
    by_url = _row_by_url(extra_rows)
    dist = analyze_distributions(extra_rows)

    selected = dist["selected_urls"]
    urls_to_fetch: list[tuple[str, str]] = []
    for bucket, url in selected.items():
        if url:
            urls_to_fetch.append((bucket, url[0] if isinstance(url, list) else url))

    comparisons: list[dict[str, Any]] = []
    for bucket, url in urls_to_fetch:
        comp = await compare_url(url, by_url.get(normalize_url_key(url)))
        comp["bucket"] = bucket
        comparisons.append(comp)

    result = {
        "snapshot_id": snapshot_id,
        "domain": snapshot.domain,
        "run_timestamp": snapshot.run_timestamp,
        "distributions": dist,
        "playwright_comparisons": comparisons,
    }

    payload = json.dumps(result, indent=2, default=str)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="WI3 extraction investigation")
    parser.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("reports/wi3_investigation_data.json"),
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_investigation(args.snapshot_id, args.output))


if __name__ == "__main__":
    main()
