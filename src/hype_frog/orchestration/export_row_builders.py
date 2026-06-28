"""AEO and AIOSEO recommendation row builders for full-suite export."""

from __future__ import annotations

from urllib.parse import urlparse

from hype_frog.core import get_logger
from hype_frog.rules import owner_for_issue, stable_issue_id, workflow_metrics_for_issue

logger = get_logger(__name__)

_SEVERITY_RANK = {"Critical": 0, "Warning": 1, "Observation": 2}

_TAXONOMY_URL_TOKENS = (
    "/category/", "/tag/", "/author/", "/product-category/",
    "/product-tag/", "/topics/", "/archive/",
)


def _detect_wp_page_type(url: str, post_id: int) -> str:
    if post_id > 0:
        path = urlparse(url).path.lower()
        if "/product/" in path:
            return "WooCommerce Product"
        return "Post/Page"
    path = urlparse(url).path.lower()
    if any(token in path for token in _TAXONOMY_URL_TOKENS):
        return "Taxonomy/Archive"
    if path in {"/", ""}:
        return "Homepage"
    return "Taxonomy/Archive"


def _to_int(value: object, fallback: int = 0) -> int:
    try:
        return int(float(value)) if value is not None else fallback
    except Exception as exc:
        logger.debug("Could not coerce value to int (%r): %s", value, exc)
        return fallback


def _to_float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value) if value is not None else fallback
    except Exception as exc:
        logger.debug("Could not coerce value to float (%r): %s", value, exc)
        return fallback


def build_aeo_rows(extra_rows: list[dict[str, object]]) -> list[dict[str, object]]:
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


class _AioseoIssueWriter:
    """Accumulates AIOSEO recommendation rows for one crawl URL."""

    def __init__(
        self,
        *,
        rows: list[dict[str, object]],
        url: str,
        post_id: int,
        direct_edit_link: str | None,
        page_type: str = "Post/Page",
    ) -> None:
        self._rows = rows
        self._url = url
        self._post_id = post_id
        self._direct_edit_link = direct_edit_link
        self._page_type = page_type

    def add_issue(
        self,
        *,
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
        _taxonomy_suffix = (
            " (Taxonomy/Archive page: navigate via AIOSEO → Search Appearance → Taxonomies.)"
            if self._post_id == 0 and self._page_type == "Taxonomy/Archive"
            else ""
        )
        self._rows.append(
            {
                "URL": self._url,
                "Page Type": self._page_type,
                "WordPress Post ID": self._post_id if self._post_id > 0 else None,
                "Direct Edit Link": self._direct_edit_link,
                "AIOSEO Panel": panel,
                "Severity": severity,
                "Issue": issue,
                "Current Value": current_value,
                "Recommended Target": recommended_target,
                "Why It Matters": why_it_matters,
                "How to Fix in AIOSEO": how_to_fix + _taxonomy_suffix,
                "Reference Tab": reference_tab,
                "Reference Field": reference_field,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Owner": owner_for_issue(issue, severity),
                "Status": "Open",
                "Priority Score": workflow.get("Priority Score"),
                "Est. Hours": workflow.get("Est. Hours"),
                "Stable Issue ID": stable_issue_id(self._url, f"AIOSEO::{issue}"),
            }
        )


def _wordpress_edit_context(
    url: str,
    row: dict[str, object],
) -> tuple[int, str | None]:
    post_id = _to_int(row.get("WordPress Post ID"), 0)
    parsed_url = urlparse(url)
    site_root = (
        f"{parsed_url.scheme}://{parsed_url.netloc}"
        if parsed_url.scheme and parsed_url.netloc
        else ""
    )
    direct_edit_link = (
        f"{site_root}/wp-admin/post.php?post={post_id}&action=edit"
        if site_root and post_id > 0
        else None
    )
    return post_id, direct_edit_link


def _append_technical_aioseo_issues(
    writer: _AioseoIssueWriter,
    *,
    row: dict[str, object],
) -> None:
    status_code = _to_int(row.get("Status Code"))
    if status_code >= 400:
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
            issue="Canonical configuration issue",
            severity="Critical" if canonical_type == "cross-canonical" else "Warning",
            panel="Advanced SEO",
            current_value=canonical_type,
            recommended_target="self",
            why_it_matters="Incorrect canonicals can de-index or de-prioritise the intended URL.",
            how_to_fix="In AIOSEO -> Advanced -> Canonical URL, set canonical to the preferred final URL for this page.",
            reference_tab="Indexability",
            reference_field="Canonical Type",
        )


def _append_title_meta_aioseo_issues(
    writer: _AioseoIssueWriter,
    *,
    title: str,
    meta: str,
) -> None:
    title_len = len(title)
    meta_len = len(meta)

    if not title:
        writer.add_issue(
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
    elif title_len < 40:
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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
    elif meta_len < 120:
        writer.add_issue(
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
        writer.add_issue(
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


def _append_content_aioseo_issues(
    writer: _AioseoIssueWriter,
    *,
    row: dict[str, object],
) -> None:
    if bool(row.get("Missing H1 Flag")):
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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


def _append_link_media_aioseo_issues(
    writer: _AioseoIssueWriter,
    *,
    row: dict[str, object],
) -> None:
    if _to_int(row.get("Internal Links Count")) == 0:
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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


def _append_schema_aeo_aioseo_issues(
    writer: _AioseoIssueWriter,
    *,
    row: dict[str, object],
) -> None:
    if _to_int(row.get("Schema Types Count")) == 0:
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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
        writer.add_issue(
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


def _collect_aioseo_issues_for_url(
    rows: list[dict[str, object]],
    *,
    row: dict[str, object],
    main_row: dict[str, object],
) -> None:
    url = str(row.get("URL") or "").strip()
    if not url:
        return
    post_id, direct_edit_link = _wordpress_edit_context(url, row)
    writer = _AioseoIssueWriter(
        rows=rows,
        url=url,
        post_id=post_id,
        direct_edit_link=direct_edit_link,
        page_type=_detect_wp_page_type(url, post_id),
    )
    title = str(main_row.get("Title") or "").strip()
    meta = str(main_row.get("Meta Description") or "").strip()

    _append_technical_aioseo_issues(writer, row=row)
    _append_title_meta_aioseo_issues(writer, title=title, meta=meta)
    _append_content_aioseo_issues(writer, row=row)
    _append_link_media_aioseo_issues(writer, row=row)
    _append_schema_aeo_aioseo_issues(writer, row=row)


def build_aioseo_rows(
    extra_rows: list[dict[str, object]],
    main_by_url: dict[str, dict[str, object]],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, object]]:
    del default_owner_by_severity  # reserved for future owner overrides
    rows: list[dict[str, object]] = []
    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        _collect_aioseo_issues_for_url(
            rows,
            row=row,
            main_row=main_by_url.get(url, {}),
        )

    rows.sort(
        key=lambda r: (
            _SEVERITY_RANK.get(str(r.get("Severity")), 9),
            -_to_int(r.get("Priority Score"), 0),
            str(r.get("AIOSEO Panel") or ""),
            str(r.get("URL") or ""),
            str(r.get("Issue") or ""),
        )
    )
    return rows
