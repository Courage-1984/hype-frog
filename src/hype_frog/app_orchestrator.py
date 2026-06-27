from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

from hype_frog.config import (
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
    MAX_RETRIES,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.core.console import log_completion_panel
from hype_frog.core.run_config import RunConfig
from hype_frog.orchestration.crawl_runner import execute_crawl
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.export_flow import execute_export
from hype_frog.orchestration.run_setup import resolve_run_setup
from hype_frog.pipeline.enrich import value_or_default as _value_or_default_pipeline
from hype_frog.rules import owner_for_issue, stable_issue_id, workflow_metrics_for_issue
from hype_frog.core.url_normalization import normalize_url

logger = get_logger(__name__)


def _normalize_url_key(url: object) -> str:
    return normalize_url(url)


def _extract_subfolder(url: str) -> str:
    parsed = urlparse(str(url or ""))
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return f"/{parts[0]}/" if parts else "/"


def _value_or_default(value: object, default: float = 0.0) -> float:
    return _value_or_default_pipeline(value, default)


async def main(run: RunConfig | None = None) -> None:
    _start = time.perf_counter()
    setup = resolve_run_setup(run)
    crawl_result = await execute_crawl(setup)
    enrichment_result = await run_enrichment(crawl_result)
    execute_export(
        setup,
        crawl_result,
        enrichment_result,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )
    _pdf = crawl_result.output_filename.replace(".xlsx", "_executive_summary.pdf")
    log_completion_panel(
        output_filename=crawl_result.output_filename,
        url_count=len(crawl_result.crawl_rows),
        elapsed_seconds=time.perf_counter() - _start,
        pdf_filename=_pdf if os.path.exists(_pdf) else None,
    )


def _build_aeo_rows(extra_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in extra_rows:
        question_heading_count = int(row.get("Question Heading Count") or 0)
        faq_count = int(row.get("FAQ Section Count") or 0)
        answer_para_count = int(row.get("Paragraphs 40-60 Words Count") or 0)
        has_qa_schema = bool(row.get("QAPage/FAQ Schema Present"))
        has_speakable = bool(row.get("Speakable Schema Present"))
        has_howto = bool(row.get("HowTo Signal"))
        has_definition = bool(row.get("Definition Signal"))
        has_list_table = bool(row.get("List/Table Answer Signal"))
        title_missing = bool(row.get("Title Missing"))
        meta_missing = bool(row.get("Meta Description Missing"))
        aeo_score = int(row.get("AEO Readiness Score") or 0)

        why_notes: list[str] = []
        if answer_para_count == 0:
            why_notes.append(
                "Missing 30-60 word answer blocks reduces eligibility for featured snippets."
            )
        if question_heading_count == 0:
            why_notes.append(
                "Question-style headings help match conversational search and answer intent."
            )
        if not has_qa_schema:
            why_notes.append(
                "FAQ/QA schema improves machine understanding for rich answer surfaces."
            )
        if not has_speakable:
            why_notes.append(
                "Speakable markup can improve voice assistant readability of key answers."
            )
        if not has_howto and not has_definition and not has_list_table:
            why_notes.append(
                "Answer-friendly structure (how-to, definitions, lists/tables) helps extraction by answer engines."
            )
        if title_missing or meta_missing:
            why_notes.append(
                "Missing title/meta weakens topical context and lowers snippet confidence."
            )
        if not why_notes and aeo_score >= 80:
            why_notes.append(
                "Strong answer-engine foundations are present; maintain concise, direct answer blocks."
            )

        row_copy = dict(row)
        row_copy["Why It Matters"] = " ".join(why_notes)
        row_copy["Question Heading Count"] = question_heading_count
        row_copy["FAQ Section Count"] = faq_count
        row_copy["Paragraphs 40-60 Words Count"] = answer_para_count
        first_snippet = (
            (row.get("aeo_snippets") or [{}])[0] if row.get("aeo_snippets") else {}
        )
        heading = str(first_snippet.get("heading") or "").strip()
        snippet = str(first_snippet.get("snippet") or "").strip()
        row_copy["Snippet Preview Mockup"] = (
            f"{heading}\n{snippet}".strip() if heading or snippet else None
        )
        rows.append(row_copy)
    return rows


def _build_aioseo_rows(
    extra_rows: list[dict[str, object]],
    main_by_url: dict[str, dict[str, object]],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    severity_rank = {"Critical": 0, "Warning": 1, "Observation": 2}

    def _to_int(value: object, fallback: int = 0) -> int:
        try:
            return int(float(value)) if value is not None else fallback
        except Exception:
            return fallback

    def _to_float(value: object, fallback: float = 0.0) -> float:
        try:
            return float(value) if value is not None else fallback
        except Exception:
            return fallback

    def add_issue(
        *,
        url: str,
        issue: str,
        severity: str,
        panel: str,
        current_value: object,
        recommended_target: str,
        why_it_matters: str,
        how_to_fix: str,
        reference_tab: str,
        reference_field: str,
    ) -> None:
        workflow = workflow_metrics_for_issue(severity)
        rows.append(
            {
                "URL": url,
                "WordPress Post ID": current_post_id if current_post_id > 0 else None,
                "Direct Edit Link": current_direct_edit_link,
                "AIOSEO Panel": panel,
                "Severity": severity,
                "Issue": issue,
                "Current Value": current_value,
                "Recommended Target": recommended_target,
                "Why It Matters": why_it_matters,
                "How to Fix in AIOSEO": how_to_fix,
                "Reference Tab": reference_tab,
                "Reference Field": reference_field,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Owner": owner_for_issue(issue, severity),
                "Status": "Open",
                "Priority Score": workflow.get("Priority Score"),
                "Est. Hours": workflow.get("Est. Hours"),
                "Stable Issue ID": stable_issue_id(url, f"AIOSEO::{issue}"),
            }
        )

    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        post_id_raw = row.get("WordPress Post ID")
        current_post_id = _to_int(post_id_raw, 0)
        parsed_url = urlparse(url)
        site_root = (
            f"{parsed_url.scheme}://{parsed_url.netloc}"
            if parsed_url.scheme and parsed_url.netloc
            else ""
        )
        current_direct_edit_link = (
            f"{site_root}/wp-admin/post.php?post={current_post_id}&action=edit"
            if site_root and current_post_id > 0
            else None
        )
        main_row = main_by_url.get(url, {})
        title = str(main_row.get("Title") or "").strip()
        meta = str(main_row.get("Meta Description") or "").strip()
        title_len = len(title)
        meta_len = len(meta)

        status_code = _to_int(row.get("Status Code"))
        if status_code >= 400:
            add_issue(
                url=url,
                issue="Page returns non-200 response",
                severity="Critical",
                panel="Basic SEO",
                current_value=status_code,
                recommended_target="200",
                why_it_matters="Pages that error cannot perform in search and fail core page-level SEO checks.",
                how_to_fix="Update URL target, restore page, or set correct redirect. In AIOSEO, review canonical/robots only after the page returns 200.",
                reference_tab="Technical",
                reference_field="Status Code",
            )

        if "noindex" in str(row.get("Indexability Reason") or "").lower():
            add_issue(
                url=url,
                issue="Noindex directive on page",
                severity="Critical",
                panel="Advanced SEO",
                current_value=row.get("Indexability Reason"),
                recommended_target="Indexable",
                why_it_matters="Noindex prevents the page from being indexed.",
                how_to_fix="In AIOSEO page settings -> Advanced, remove noindex for pages intended to rank.",
                reference_tab="Indexability",
                reference_field="Indexability Reason",
            )

        canonical_type = str(row.get("Canonical Type") or "")
        if canonical_type in {"missing", "cross-canonical"}:
            add_issue(
                url=url,
                issue="Canonical configuration issue",
                severity=(
                    "Critical" if canonical_type == "cross-canonical" else "Warning"
                ),
                panel="Advanced SEO",
                current_value=canonical_type,
                recommended_target="self",
                why_it_matters="Incorrect canonicals can de-index or de-prioritise the intended URL.",
                how_to_fix="In AIOSEO -> Advanced -> Canonical URL, set canonical to the preferred final URL for this page.",
                reference_tab="Indexability",
                reference_field="Canonical Type",
            )

        if not title:
            add_issue(
                url=url,
                issue="Missing SEO title",
                severity="Warning",
                panel="Title",
                current_value="Missing",
                recommended_target="40-60 characters",
                why_it_matters="Titles are a core relevance and CTR signal.",
                how_to_fix="In AIOSEO snippet settings, add a unique SEO title with the primary topic near the beginning.",
                reference_tab="Main",
                reference_field="Title",
            )
        else:
            if title_len < 40:
                add_issue(
                    url=url,
                    issue="SEO title too short",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Very short titles often under-describe page intent.",
                    how_to_fix="Expand title in AIOSEO snippet editor with clearer intent and value proposition.",
                    reference_tab="Main",
                    reference_field="Title",
                )
            elif title_len > 60:
                add_issue(
                    url=url,
                    issue="SEO title too long",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Long titles are more likely to truncate in SERPs.",
                    how_to_fix="Shorten title in AIOSEO snippet editor and keep key terms in the first 55-60 characters.",
                    reference_tab="Main",
                    reference_field="Title",
                )

        if not meta:
            add_issue(
                url=url,
                issue="Missing meta description",
                severity="Warning",
                panel="Basic SEO",
                current_value="Missing",
                recommended_target="120-160 characters",
                why_it_matters="Missing descriptions reduce control over search snippet messaging.",
                how_to_fix="In AIOSEO snippet settings, add a concise, unique meta description aligned to page intent.",
                reference_tab="Main",
                reference_field="Meta Description",
            )
        else:
            if meta_len < 120:
                add_issue(
                    url=url,
                    issue="Meta description too short",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Short descriptions can under-communicate relevance and value.",
                    how_to_fix="Expand meta description in AIOSEO to include key value points and intent terms naturally.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )
            elif meta_len > 160:
                add_issue(
                    url=url,
                    issue="Meta description too long",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Long descriptions are often truncated and lose message clarity.",
                    how_to_fix="Trim meta description in AIOSEO and front-load essential context.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )

        if bool(row.get("Missing H1 Flag")):
            add_issue(
                url=url,
                issue="Missing H1 heading",
                severity="Warning",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 descriptive H1",
                why_it_matters="A missing H1 weakens topical clarity for users and crawlers.",
                how_to_fix="Update page content to include a single descriptive H1 aligned to primary intent.",
                reference_tab="Content",
                reference_field="Missing H1 Flag",
            )
        if bool(row.get("Multiple H1 Flag")):
            add_issue(
                url=url,
                issue="Multiple H1 headings",
                severity="Observation",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 H1",
                why_it_matters="Multiple H1s can reduce heading hierarchy clarity.",
                how_to_fix="Keep one primary H1, convert remaining top-level headings to H2/H3 where appropriate.",
                reference_tab="Content",
                reference_field="Multiple H1 Flag",
            )

        word_count = _to_int(row.get("Word Count"))
        if bool(row.get("Thin Content Flag")) or word_count < 300:
            add_issue(
                url=url,
                issue="Thin content",
                severity="Warning",
                panel="Readability",
                current_value=word_count,
                recommended_target=">=300 words (quality first)",
                why_it_matters="Low-content pages can struggle to satisfy intent and rank competitively.",
                how_to_fix="Expand page copy with useful, unique sections that answer key user questions.",
                reference_tab="Content",
                reference_field="Word Count",
            )

        readability = _to_float(row.get("Readability (Rough Flesch)"), -1)
        if readability >= 0 and readability < 50:
            add_issue(
                url=url,
                issue="Low readability score",
                severity="Observation",
                panel="Readability",
                current_value=readability,
                recommended_target=">=50",
                why_it_matters="Hard-to-read content lowers engagement and comprehension.",
                how_to_fix="Use shorter sentences/paragraphs, clearer transitions, and simpler phrasing in page content.",
                reference_tab="Content",
                reference_field="Readability (Rough Flesch)",
            )

        if _to_int(row.get("Internal Links Count")) == 0:
            add_issue(
                url=url,
                issue="No internal links found",
                severity="Observation",
                panel="Basic SEO",
                current_value=0,
                recommended_target=">=2 relevant internal links",
                why_it_matters="Internal links help discovery, topical signals, and authority flow.",
                how_to_fix="Add contextual internal links from and to related pages using descriptive anchor text.",
                reference_tab="Links",
                reference_field="Internal Links Count",
            )
        if _to_int(row.get("Broken Internal Links Count")) > 0:
            add_issue(
                url=url,
                issue="Broken internal links",
                severity="Critical",
                panel="Links",
                current_value=row.get("Broken Internal Links Count"),
                recommended_target="0",
                why_it_matters="Broken links waste crawl budget and degrade user experience.",
                how_to_fix="Replace dead links with live targets, or remove them in the page editor.",
                reference_tab="Links",
                reference_field="Broken Internal Links Count",
            )

        alt_coverage = _to_float(row.get("Image Alt Coverage (%)"), 100.0)
        if alt_coverage < 80:
            add_issue(
                url=url,
                issue="Low image alt coverage",
                severity="Warning",
                panel="Readability",
                current_value=alt_coverage,
                recommended_target=">=80%",
                why_it_matters="Missing alt text reduces accessibility and weakens image context signals.",
                how_to_fix="Add descriptive alt text to meaningful images in the page editor/media fields.",
                reference_tab="Media",
                reference_field="Image Alt Coverage (%)",
            )

        if _to_int(row.get("Schema Types Count")) == 0:
            add_issue(
                url=url,
                issue="No schema markup detected",
                severity="Warning",
                panel="Schema",
                current_value=0,
                recommended_target="At least one relevant schema type",
                why_it_matters="Schema improves understanding and rich result eligibility.",
                how_to_fix="In AIOSEO schema settings for the page, add the most relevant type (Article/FAQ/HowTo/Product, etc.).",
                reference_tab="Schema & Metadata",
                reference_field="Schema Types Count",
            )

        aeo_score = _to_int(row.get("AEO Readiness Score"), 100)
        if aeo_score < 70:
            add_issue(
                url=url,
                issue="Low AEO readiness score",
                severity="Warning",
                panel="Content",
                current_value=aeo_score,
                recommended_target=">=60",
                why_it_matters="Weak answer-style structure lowers AI/answer-engine retrieval potential.",
                how_to_fix="Add concise answer blocks, question-led subheadings, and clear structured sections.",
                reference_tab="AEO",
                reference_field="AEO Readiness Score",
            )
        if not bool(row.get("QAPage/FAQ Schema Present")):
            add_issue(
                url=url,
                issue="No FAQ/QA schema",
                severity="Observation",
                panel="Schema",
                current_value=False,
                recommended_target="True when page has Q&A intent",
                why_it_matters="Q&A schema can improve eligibility for answer-rich results.",
                how_to_fix="If content is Q&A style, add FAQPage/QAPage schema in AIOSEO and keep markup aligned with on-page content.",
                reference_tab="AEO",
                reference_field="QAPage/FAQ Schema Present",
            )
        if _to_int(row.get("Question Heading Count")) == 0:
            add_issue(
                url=url,
                issue="No question-style headings",
                severity="Observation",
                panel="Readability",
                current_value=0,
                recommended_target=">=1 where intent is informational",
                why_it_matters="Question headings better align with query phrasing and snippet extraction.",
                how_to_fix="Add at least one natural question heading (H2/H3) matching user intent.",
                reference_tab="AEO",
                reference_field="Question Heading Count",
            )
        if _to_int(row.get("Paragraphs 40-60 Words Count")) == 0:
            add_issue(
                url=url,
                issue="No concise answer paragraph (40-60 words)",
                severity="Observation",
                panel="Content",
                current_value=0,
                recommended_target=">=1 concise answer block",
                why_it_matters="Compact answer blocks improve direct-answer extraction chances.",
                how_to_fix="Add a direct 40-60 word answer immediately below key question headings.",
                reference_tab="AEO",
                reference_field="Paragraphs 40-60 Words Count",
            )

    rows.sort(
        key=lambda r: (
            severity_rank.get(str(r.get("Severity")), 9),
            -_to_int(r.get("Priority Score"), 0),
            str(r.get("AIOSEO Panel") or ""),
            str(r.get("URL") or ""),
            str(r.get("Issue") or ""),
        )
    )
    return rows


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
