from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hype_frog.config import (
    get_cwv_inp_warning_ms,
    get_cwv_lcp_critical_threshold,
    get_cwv_lcp_warning_threshold,
    get_content_age_ageing_days,
    get_content_age_stale_days,
    get_high_third_party_script_count,
    get_lab_tbt_critical_ms,
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
)
from hype_frog.config_defaults import UNDER_LINKED_INBOUND_THRESHOLD
from hype_frog.core.status_codes import is_error_status
from hype_frog.core.text_utils import to_bool

RuleFn = Callable[[dict[str, Any]], bool]

EFFORT_TO_SPRINT_POINTS = {"S": 2, "M": 5, "L": 8}
EFFORT_TO_HOURS = {"S": 4, "M": 10, "L": 16}
SEVERITY_PRIORITY_BASE = {"Critical": 100, "Warning": 65, "Observation": 35}
AGING_BY_SEVERITY = {"Critical": "Immediate (Current Sprint)", "Warning": "Next Sprint", "Observation": "Backlog"}


@dataclass(frozen=True)
class IssueRule:
    severity: str
    name: str
    fn: RuleFn
    scope: str = "url"


def get_summary_rules() -> list[IssueRule]:
    return [
        IssueRule(
            "Critical",
            "Non-200 Status",
            lambda r: is_error_status(r.get("Status Code")),
        ),
        IssueRule("Critical", "Missing Title", lambda r: to_bool(r.get("Title Missing"))),
        IssueRule(
            "Critical",
            "Noindex Directive",
            lambda r: "noindex" in str(r.get("Indexability Reason", "")).lower(),
        ),
        IssueRule(
            "Critical",
            "Canonical Points Elsewhere",
            lambda r: r.get("Canonical Type") == "cross-canonical",
        ),
        IssueRule(
            "Critical",
            "Robots.txt Disallow Root",
            lambda r: to_bool(r.get("Robots.txt Disallow /")),
        ),
        IssueRule(
            "Critical",
            "CWV LCP Above 4.0s (Field Data)",
            lambda r: (
                r.get("CrUX Level") == "URL"
                and (r.get("CWV LCP (s)") or 0) > 4.0
            ),
        ),
        IssueRule(
            "Critical",
            "Lab LCP Above 4.0s (Mobile)",
            lambda r: (r.get("Lab LCP (Mobile) (s)") or 0) > 4.0,
        ),
        IssueRule(
            "Critical",
            "Broken Internal Links",
            lambda r: (r.get("Broken Internal Links Count") or 0) > 0,
        ),
        IssueRule(
            "Warning",
            "Redirect Chains",
            lambda r: (r.get("Redirect Chain Length") or 0) > 1,
        ),
        IssueRule(
            "Warning",
            "302 Redirect (Temporary)",
            lambda r: to_bool(r.get("Has 302 in Chain")),
        ),
        IssueRule(
            "Warning",
            "Mixed 301/302 Chain",
            lambda r: to_bool(r.get("Has Mixed Redirect Types")),
        ),
        IssueRule(
            "Critical",
            "Redirect Loop",
            lambda r: to_bool(r.get("Redirect Loop Flag")),
        ),
        IssueRule(
            "Warning",
            "Canonical Chain (>1 hop)",
            lambda r: (r.get("Canonical Chain Depth") or 0) > 1,
        ),
        IssueRule(
            "Critical",
            "Canonical Loop",
            lambda r: to_bool(r.get("Canonical Loop Detected")),
        ),
        IssueRule(
            "Critical",
            "Canonical Points to Broken URL",
            lambda r: to_bool(r.get("Canonical Points to Non-200")),
        ),
        IssueRule(
            "Warning",
            "Canonical Points to Redirect",
            lambda r: to_bool(r.get("Canonical Points to Redirect")),
        ),
        IssueRule(
            "Critical",
            "Not Indexed by Google",
            lambda r: str(r.get("GSC Index Status") or "").upper() == "NOT_INDEXED",
        ),
        IssueRule(
            "Warning",
            "Not Crawled in >30 Days",
            lambda r: (r.get("Days Since Last Crawl") or 0) > 30,
        ),
        IssueRule(
            "Warning",
            "GSC Mobile Usability Issue",
            lambda r: str(r.get("GSC Mobile Usability") or "").upper()
            == "NOT_MOBILE_FRIENDLY",
        ),
        IssueRule(
            "Warning",
            "GSC Rich Result Error",
            lambda r: str(r.get("GSC Rich Result Status") or "").upper() == "INVALID",
        ),
        IssueRule(
            "Critical",
            "Blocked by Googlebot",
            lambda r: str(r.get("Robots.txt: Googlebot") or "") == "Disallow",
        ),
        IssueRule(
            "Warning",
            "Blocked by Bingbot",
            lambda r: str(r.get("Robots.txt: Bingbot") or "") == "Disallow",
        ),
        IssueRule(
            "Critical",
            "In Sitemap but Blocked by Googlebot",
            lambda r: (
                to_bool(r.get("Found via Sitemap"))
                and str(r.get("Robots.txt: Googlebot") or "") == "Disallow"
            ),
        ),
        IssueRule(
            "Observation",
            "AI Crawlers: GPTBot Blocked",
            lambda r: str(r.get("Robots.txt: GPTBot") or "") == "Disallow",
            scope="site",
        ),
        IssueRule(
            "Observation",
            "AI Crawlers: ClaudeBot Blocked",
            lambda r: str(r.get("Robots.txt: ClaudeBot") or "") == "Disallow",
            scope="site",
        ),
        IssueRule(
            "Warning",
            "Missing Meta Description",
            lambda r: to_bool(r.get("Meta Description Missing")),
        ),
        IssueRule("Warning", "Missing H1", lambda r: to_bool(r.get("Missing H1 Flag"))),
        IssueRule("Warning", "Multiple H1", lambda r: to_bool(r.get("Multiple H1 Flag"))),
        IssueRule(
            "Warning",
            "CWV CLS Above 0.1 (Field Data)",
            lambda r: (
                r.get("CrUX Level") == "URL"
                and (r.get("CWV CLS") or 0) > 0.1
            ),
        ),
        IssueRule(
            "Warning",
            "CWV INP Above 200ms (Field Data)",
            lambda r: (
                r.get("CrUX Level") == "URL"
                and (r.get("CWV INP (ms)") or 0) > get_cwv_inp_warning_ms()
            ),
        ),
        IssueRule(
            "Warning",
            "Lab LCP 2.5s–4.0s (Mobile)",
            lambda r: get_cwv_lcp_warning_threshold()
            < (r.get("Lab LCP (Mobile) (s)") or 0)
            <= get_cwv_lcp_critical_threshold(),
        ),
        IssueRule(
            "Warning",
            "Lab TBT Above 300ms (Mobile)",
            lambda r: (r.get("Lab TBT (Mobile) (ms)") or 0) > get_lab_tbt_critical_ms(),
        ),
        IssueRule(
            "Warning",
            "Lab CLS Above 0.1 (Mobile)",
            lambda r: (r.get("Lab CLS (Mobile)") or 0) > 0.1,
        ),
        IssueRule(
            "Warning",
            "Low Lighthouse Performance Mobile (<50)",
            lambda r: 0 < (r.get("Lighthouse Performance (Mobile)") or 0) < 50,
        ),
        IssueRule(
            "Warning",
            "Low Lighthouse Accessibility (<80)",
            lambda r: 0 < (r.get("Lighthouse Accessibility (Mobile)") or 0) < 80,
        ),
        IssueRule(
            "Warning",
            "Lab TTFB Above 600ms",
            lambda r: (r.get("Lab TTFB (Mobile) (ms)") or 0) > 600,
        ),
        IssueRule(
            "Warning",
            "Missing FAQ/QA Schema",
            lambda r: not to_bool(r.get("QAPage/FAQ Schema Present"))
            and (r.get("Question Heading Count") or 0) > 0,
        ),
        IssueRule(
            "Warning",
            "Deep URL (>3 clicks)",
            lambda r: (r.get("Click Depth") or 0) > 3,
        ),
        IssueRule(
            "Warning",
            "Low Image Alt Coverage",
            lambda r: (r.get("Image Alt Coverage (%)") or 100) < 80,
        ),
        IssueRule(
            "Warning",
            "Mixed Content",
            lambda r: to_bool(r.get("Mixed Content Detected")),
        ),
        IssueRule(
            "Warning",
            "Canonical Missing",
            lambda r: r.get("Canonical Type") == "missing",
        ),
        IssueRule(
            "Warning",
            "Hreflang Without Reciprocity",
            lambda r: r.get("Hreflang Present")
            and str(r.get("Hreflang Reciprocal Status") or "")
            not in {"Valid", "Not Declared", ""},
        ),
        IssueRule(
            "Warning",
            "Invalid Hreflang Language Code",
            lambda r: r.get("Hreflang Present")
            and not to_bool(r.get("Hreflang Code Valid")),
        ),
        IssueRule(
            "Observation",
            "Uses URL Parameters",
            lambda r: to_bool(r.get("Param URL Flag")),
        ),
        IssueRule(
            "Observation",
            "Generic Anchor Text Present",
            lambda r: (r.get("Generic Anchor Text Count") or 0) > 0,
        ),
        IssueRule(
            "Observation",
            "Image Filename Quality Issues",
            lambda r: (r.get("Image Filename Quality Issues") or 0) > 0,
        ),
        IssueRule(
            "Observation",
            "No Compression Header",
            lambda r: not to_bool(r.get("Compression Enabled")),
        ),
        IssueRule(
            "Observation",
            "No Cache-Control Header",
            lambda r: not bool(r.get("Cache-Control")),
        ),
        IssueRule(
            "Observation",
            "No ETag Header",
            lambda r: not bool(r.get("ETag")),
            scope="server",
        ),
        IssueRule(
            "Observation",
            "Thin Content",
            lambda r: to_bool(r.get("Thin Content Flag")),
        ),
        IssueRule(
            "Warning",
            "Render Fallback (raw HTTP)",
            lambda r: to_bool(r.get("Extraction Source Fallback")),
        ),
        IssueRule(
            "Warning",
            "Thin Content (<200 words)",
            lambda r: r.get("Is Thin Content") is True,
        ),
        IssueRule(
            "Critical",
            "Near-Duplicate Content",
            lambda r: r.get("Is Near Duplicate") is True,
        ),
        IssueRule(
            "Warning",
            "Draft or Test Page (URL pattern)",
            lambda r: r.get("Is Draft or Test Page") is True,
        ),
        IssueRule(
            "Critical",
            "No Schema Markup",
            lambda r: not r.get("Schema Present", False),
        ),
        IssueRule(
            "Critical",
            "Schema Parse Error",
            lambda r: bool(r.get("Schema Parse Error Detail"))
            or (r.get("Schema Parse Errors") or 0) > 0,
        ),
        IssueRule(
            "Warning",
            "Schema Validation Errors",
            lambda r: (r.get("Schema Error Count") or 0) > 0,
        ),
        IssueRule(
            "Observation",
            "Schema Validation Warnings",
            lambda r: (r.get("Schema Warning Count") or 0) > 0
            and (r.get("Schema Error Count") or 0) == 0,
        ),
        IssueRule(
            "Warning",
            "Missing Event Schema",
            lambda r: (
                any(
                    token in (r.get("URL") or "")
                    for token in ("conference", "event", "summit", "awards", "webinar")
                )
                and not r.get("Schema Present", False)
            ),
        ),
        IssueRule(
            "Warning",
            "Missing Article Schema",
            lambda r: (
                any(
                    token in (r.get("URL") or "")
                    for token in ("news", "blog", "article", "post", "publication")
                )
                and not r.get("Schema Present", False)
            ),
        ),
        IssueRule(
            "Warning",
            "Low E-E-A-T Signal Score (<3)",
            lambda r: (r.get("E-E-A-T Signal Score") or 0) < 3,
        ),
        IssueRule(
            "Observation",
            "No Author Attribution",
            lambda r: (
                not r.get("Schema Author Name")
                and not r.get("Meta Author")
                and not r.get("Has Byline Element")
            ),
        ),
        IssueRule(
            "Observation",
            "No Publication Date",
            lambda r: (
                not r.get("OG Published Time") and not r.get("Schema Published Date")
            ),
        ),
        IssueRule(
            "Warning",
            "No Privacy Policy Link",
            lambda r: not r.get("Has Privacy Policy Link"),
            scope="site",
        ),
        IssueRule(
            "Warning",
            "No Terms Link",
            lambda r: not r.get("Has Terms Link"),
            scope="site",
        ),
        IssueRule(
            "Observation",
            "Stale Content (>2 years)",
            lambda r: (r.get("Content Age (days)") or 0) > get_content_age_stale_days(),
        ),
        IssueRule(
            "Observation",
            "Ageing Content (1-2 years)",
            lambda r: get_content_age_ageing_days()
            < (r.get("Content Age (days)") or 0)
            <= get_content_age_stale_days(),
        ),
        IssueRule(
            "Observation",
            "No Publication or Modification Date",
            lambda r: r.get("Freshness Status") == "Unknown",
        ),
        IssueRule(
            "Warning",
            "Missing OG Title",
            lambda r: not r.get("OG Title"),
        ),
        IssueRule(
            "Warning",
            "Missing OG Description",
            lambda r: not r.get("OG Description"),
        ),
        IssueRule(
            "Warning",
            "Missing OG Image",
            lambda r: not (
                r.get("OG Image URL") or r.get("OG Image") or r.get("OG-Image")
            ),
        ),
        IssueRule(
            "Critical",
            "OG Image Broken (non-200)",
            lambda r: r.get("OG Image OK") is False,
        ),
        IssueRule(
            "Warning",
            "OG URL Mismatch",
            lambda r: to_bool(r.get("OG URL Mismatch")),
        ),
        IssueRule(
            "Observation",
            "OG Type Not Set",
            lambda r: not r.get("OG Type"),
        ),
        IssueRule(
            "Observation",
            "Missing Twitter Card",
            lambda r: not r.get("Twitter Card Type"),
        ),
        IssueRule(
            "Observation",
            "OG Image Wrong Dimensions",
            lambda r: (
                r.get("OG Image Width") is not None
                and r.get("OG Image Height") is not None
                and r.get("OG Image Dimensions OK") is False
            ),
        ),
        IssueRule(
            "Warning",
            "Broken Images",
            lambda r: (r.get("Broken Image Count") or 0) > 0,
        ),
        IssueRule(
            "Critical",
            "High Broken Image Count (>3)",
            lambda r: (r.get("Broken Image Count") or 0) > 3,
        ),
        IssueRule(
            "Warning",
            "High Third-Party Script Count (>10)",
            lambda r: (r.get("Third Party Script Count") or 0)
            > get_high_third_party_script_count(),
        ),
        IssueRule(
            "Warning",
            "Third-Party Scripts Blocking Render",
            lambda r: r.get("Third Party JS Blocking") is True,
        ),
        IssueRule(
            "Observation",
            "No Consent Manager Detected",
            lambda r: not bool(r.get("Has Consent Manager")),
            scope="site",
        ),
        IssueRule(
            "Warning",
            "Under-Linked Priority Page",
            lambda r: (r.get("Business Risk Score") or 0) >= 30
            and (r.get("Inbound Internal Link Count") or 0)
            < UNDER_LINKED_INBOUND_THRESHOLD,
        ),
        IssueRule(
            "Observation",
            "Generic Anchor Dominance",
            lambda r: r.get("Generic Anchor Dominance") is True,
        ),
        IssueRule(
            "Warning",
            "Low AEO Readiness Score",
            lambda r: (r.get("AEO Readiness Score") or 0) < 70,
        ),
        IssueRule(
            "Observation",
            "No Question Headings",
            lambda r: (r.get("Question Heading Count") or 0) == 0,
        ),
        IssueRule(
            "Observation",
            "No Answer-Friendly Structure",
            lambda r: not to_bool(r.get("List/Table Answer Signal")),
        ),
        IssueRule(
            "Observation",
            "No 40-60 Word Answer Paragraphs",
            lambda r: (r.get("Paragraphs 40-60 Words Count") or 0) == 0,
        ),
        IssueRule(
            "Observation",
            "Lab TBT 150ms–300ms (Mobile)",
            lambda r: 150 < (r.get("Lab TBT (Mobile) (ms)") or 0) <= 300,
        ),
        IssueRule(
            "Observation",
            "Moderate Lighthouse Performance Mobile (50–89)",
            lambda r: 50 <= (r.get("Lighthouse Performance (Mobile)") or 0) < 90,
        ),
        IssueRule(
            "Observation",
            "Low Lighthouse Best Practices (<80)",
            lambda r: 0 < (r.get("Lighthouse Best Practices (Mobile)") or 0) < 80,
        ),
        IssueRule(
            "Observation",
            "Large Page Size (>1MB)",
            lambda r: (r.get("Page Size (KB)") or 0) > 1024,
        ),
        IssueRule(
            "Observation",
            "Large DOM Size (>1500 nodes)",
            lambda r: (r.get("DOM Size (nodes)") or 0) > 1500,
        ),
        IssueRule(
            "Observation",
            "High JS Execution Time (>2000ms)",
            lambda r: (r.get("JS Execution (ms)") or 0) > 2000,
        ),
        IssueRule(
            "Observation",
            "Render Blocking Resources",
            lambda r: r.get("Has Render Blocking Resources") is True,
        ),
        IssueRule(
            "Observation",
            "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)",
            lambda r: (
                r.get("CrUX Level") == "Origin"
                and (r.get("Origin CrUX LCP (s)") or 0) > get_cwv_lcp_critical_threshold()
            ),
            scope="site",
        ),
        IssueRule(
            "Observation",
            "Origin CrUX INP Above 200ms (per-URL data unavailable)",
            lambda r: (
                r.get("CrUX Level") == "Origin"
                and (r.get("Origin CrUX INP (ms)") or 0) > get_cwv_inp_warning_ms()
            ),
            scope="site",
        ),
        IssueRule(
            "Observation",
            "Low Regional Authority",
            lambda r: (r.get("Regional Authority Score") or 0) < 30,
        ),
        IssueRule(
            "Observation",
            "llms.txt Missing",
            lambda r: r.get("llms.txt Present") is False,
        ),
        IssueRule(
            "Observation",
            "AI Crawlers Not Explicitly Allowed",
            lambda r: not to_bool(
                r.get("AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)")
            ),
            scope="site",
        ),
    ]


def stable_issue_id(url: str | None, issue_name: str | None) -> str:
    safe_url = str(url or "").strip()
    safe_issue = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(issue_name or "").strip().lower())
    return f"{safe_url}::{safe_issue}"


def root_cause_and_fix(issue_name: str) -> tuple[str, str]:
    mapping = {
        "Non-200 Status": ("URL returns 4xx/5xx or equivalent failure.", "Fix status code, restore page, or implement correct redirect to canonical destination."),
        "Noindex Directive": ("Meta robots or X-Robots-Tag contains noindex.", "Remove unintended noindex directives on index-worthy URLs."),
        "Canonical Points Elsewhere": ("Canonical targets a different URL variant.", "Align canonical to preferred final URL and ensure internal links use canonical target."),
        "Broken Internal Links": ("Internal links resolve to missing or error pages.", "Update internal links to valid URLs and remove dead references."),
        "Missing Title": ("Template/page missing title tag.", "Add unique descriptive title on affected template/page type."),
        "Missing Meta Description": ("Meta description missing or empty.", "Add concise unique description aligned with user intent."),
        "Thin Content": ("Insufficient body content for indexing confidence.", "Expand page with helpful, unique, intent-matching content."),
        "Render Fallback (raw HTTP)": (
            "Accurate crawl mode attempted Playwright rendering but fell back to the raw HTTP payload for this URL.",
            "Re-run in accurate mode with Playwright installed, or fix page timeouts/blocking so rendered_browser extraction succeeds for parity with other URLs.",
        ),
        "Probable Draft or Duplicate Page": (
            "URL slug and/or heading/body structure closely matches another crawled page (common on WordPress copy/draft URLs).",
            "Consolidate into one canonical URL: noindex or delete the draft/copy page, 301 redirect to the primary page, and deduplicate repetitive H2/H3 blocks.",
        ),
        "Low AEO Readiness Score": (
            "Weighted AEO score is below the 70-point extraction-confidence band.",
            "Raise the weighted mix: add a 40–60 word factual paragraph under each question H2/H3, add FAQPage/HowTo/Speakable JSON-LD, tune copy to FK grade 7–10, add ul/ol/table for key facts, and ensure robots.txt explicitly allows GPTBot, PerplexityBot, and CCBot.",
        ),
        "Missing FAQ/QA Schema": (
            "Question-style content without matching FAQPage/QAPage JSON-LD.",
            "Publish machine-readable FAQPage or QAPage JSON-LD that mirrors visible Q&A text so answer engines can treat schema as a stable API surface.",
        ),
        "No Question Headings": (
            "Headings are not phrased as user questions.",
            "Rewrite priority H2/H3 headings into natural-language questions (Who/What/How) so the following paragraph can serve as a direct extractable answer.",
        ),
        "No Answer-Friendly Structure": (
            "Dense prose without lists or tables where facts could be chunked.",
            "Break data-heavy explanations into ul/ol steps or a comparison table so LLMs can cite discrete facts without re-parsing long paragraphs.",
        ),
        "No 40-60 Word Answer Paragraphs": (
            "No 40–60 word definitional paragraph directly under a question-style H2/H3.",
            "Refactor each target section to lead with a ~45-word factual definition (no fluff) immediately under the question heading to improve LLM Position Zero retrieval.",
        ),
        "Mixed Content": ("HTTPS page references insecure HTTP assets.", "Serve all assets over HTTPS and update hardcoded URLs."),
    }
    return mapping.get(issue_name, ("Template/technical implementation quality issue.", "Apply fix based on issue type and re-run audit."))


def owner_for_issue(issue_name: str, severity: str | None = None) -> str:
    issue = str(issue_name or "").strip()
    copy_writer_issues = {
        "Missing Title",
        "Missing Meta Description",
        "Missing H1",
        "Multiple H1",
        "Thin Content",
        "Low AEO Readiness Score",
        "No Question Headings",
        "No Answer-Friendly Structure",
        "No 40-60 Word Answer Paragraphs",
        "Low Image Alt Coverage",
        "Generic Anchor Text Present",
        "Image Filename Quality Issues",
        "Probable Draft or Duplicate Page",
    }
    dev_issues = {
        "Noindex Directive",
        "Canonical Points Elsewhere",
        "Canonical Missing",
        "Redirect Chains",
        "Broken Internal Links",
        "Mixed Content",
        "Missing FAQ/QA Schema",
        "Uses URL Parameters",
    }
    server_host_issues = {
        "Non-200 Status",
        "Robots.txt Disallow Root",
        "No Compression Header",
        "No Cache-Control Header",
        "No ETag Header",
    }

    if issue in copy_writer_issues:
        return "Copy Writer"
    if issue in server_host_issues:
        return "Server/Host"
    if issue in dev_issues:
        return "Dev"
    return DEFAULT_OWNER_BY_SEVERITY.get(str(severity or ""), "Dev")


def workflow_metrics_for_issue(severity: str, effort: str | None = None) -> dict[str, Any]:
    normalized_effort = effort or DEFAULT_EFFORT_BY_SEVERITY.get(severity, "S")
    sprint_points = EFFORT_TO_SPRINT_POINTS.get(normalized_effort, 2)
    est_hours = EFFORT_TO_HOURS.get(normalized_effort, 4)
    priority_score = SEVERITY_PRIORITY_BASE.get(severity, 25) + sprint_points
    return {
        "Agency Owner": DEFAULT_OWNER_BY_SEVERITY.get(severity, "Dev"),
        "Est. Sprint Points": sprint_points,
        "Est. Hours": est_hours,
        "Priority Score": priority_score,
        "Aging/Priority": AGING_BY_SEVERITY.get(severity, "Backlog"),
    }
