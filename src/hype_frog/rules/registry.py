from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from hype_frog.config import DEFAULT_EFFORT_BY_SEVERITY, DEFAULT_OWNER_BY_SEVERITY
from hype_frog.core.text_utils import to_bool

RuleFn = Callable[[dict[str, Any]], bool]

EFFORT_TO_SPRINT_POINTS = {"S": 2, "M": 5, "L": 8}
EFFORT_TO_HOURS = {"S": 4, "M": 10, "L": 16}
SEVERITY_PRIORITY_BASE = {"Critical": 100, "Warning": 65, "Observation": 35}
AGING_BY_SEVERITY = {"Critical": "Immediate (Current Sprint)", "Warning": "Next Sprint", "Observation": "Backlog"}


def get_summary_rules() -> list[tuple[str, str, RuleFn]]:
    return [
        ("Critical", "Non-200 Status", lambda r: isinstance(r.get("Status Code"), int) and r.get("Status Code") >= 400),
        ("Critical", "Missing Title", lambda r: to_bool(r.get("Title Missing"))),
        ("Critical", "Noindex Directive", lambda r: "noindex" in str(r.get("Indexability Reason", "")).lower()),
        ("Critical", "Canonical Points Elsewhere", lambda r: r.get("Canonical Type") == "cross-canonical"),
        ("Critical", "Robots.txt Disallow Root", lambda r: to_bool(r.get("Robots.txt Disallow /"))),
        ("Critical", "CWV LCP Above 4.0s", lambda r: (r.get("CWV LCP (s)") or 0) > 4.0),
        ("Critical", "Broken Internal Links", lambda r: (r.get("Broken Internal Links Count") or 0) > 0),
        ("Warning", "Redirect Chains", lambda r: (r.get("Redirect Chain Length") or 0) > 1),
        ("Warning", "Missing Meta Description", lambda r: to_bool(r.get("Meta Description Missing"))),
        ("Warning", "Missing H1", lambda r: to_bool(r.get("Missing H1 Flag"))),
        ("Warning", "Multiple H1", lambda r: to_bool(r.get("Multiple H1 Flag"))),
        ("Warning", "CWV LCP Needs Improvement (2.5-4.0s)", lambda r: 2.5 <= float(r.get("CWV LCP (s)") or 0) <= 4.0),
        ("Warning", "Missing FAQ/QA Schema", lambda r: not to_bool(r.get("QAPage/FAQ Schema Present")) and (r.get("Question Heading Count") or 0) > 0),
        ("Warning", "Deep URL (>3 clicks)", lambda r: (r.get("URL Depth") or 0) > 3),
        ("Warning", "Low Image Alt Coverage", lambda r: (r.get("Image Alt Coverage (%)") or 100) < 80),
        ("Warning", "Mixed Content", lambda r: to_bool(r.get("Mixed Content Detected"))),
        ("Warning", "Canonical Missing", lambda r: r.get("Canonical Type") == "missing"),
        ("Warning", "Hreflang Without Reciprocity", lambda r: r.get("Hreflang Present") and not to_bool(r.get("Hreflang Reciprocal Check"))),
        ("Observation", "Uses URL Parameters", lambda r: to_bool(r.get("Param URL Flag"))),
        ("Observation", "Generic Anchor Text Present", lambda r: (r.get("Generic Anchor Text Count") or 0) > 0),
        ("Observation", "Image Filename Quality Issues", lambda r: (r.get("Image Filename Quality Issues") or 0) > 0),
        ("Observation", "No Compression Header", lambda r: not to_bool(r.get("Compression Enabled"))),
        ("Observation", "No Cache-Control Header", lambda r: not bool(r.get("Cache-Control"))),
        ("Observation", "No ETag Header", lambda r: not bool(r.get("ETag"))),
        ("Observation", "Thin Content", lambda r: to_bool(r.get("Thin Content Flag"))),
        ("Warning", "Low AEO Readiness Score", lambda r: (r.get("AEO Readiness Score") or 0) < 60),
        ("Observation", "No Question Headings", lambda r: (r.get("Question Heading Count") or 0) == 0),
        ("Observation", "No Answer-Friendly Structure", lambda r: not to_bool(r.get("List/Table Answer Signal"))),
        ("Observation", "No 40-60 Word Answer Paragraphs", lambda r: (r.get("Paragraphs 40-60 Words Count") or 0) == 0),
        ("Observation", "INP Above 100ms", lambda r: (r.get("CWV INP (ms)") or 0) > 100),
        ("Observation", "CLS Above 0.1", lambda r: (r.get("CWV CLS") or 0) > 0.1),
        ("Observation", "Low Regional Authority", lambda r: (r.get("Regional Authority Score") or 0) < 30),
        ("Observation", "llms.txt Missing", lambda r: r.get("llms.txt Present") is False),
        ("Observation", "AI Crawlers Not Explicitly Allowed", lambda r: not to_bool(r.get("AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)"))),
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
        "Low AEO Readiness Score": ("Page lacks concise answer-oriented signals and structured answer patterns.", "Add short direct answer blocks, question-led headings, and answer-ready formatting."),
        "Missing FAQ/QA Schema": ("No FAQPage/QAPage schema found for likely Q&A style content.", "Add valid FAQPage or QAPage JSON-LD where appropriate and ensure on-page parity."),
        "No Question Headings": ("Headings are not phrased as user questions.", "Add clear question-style headings (especially H2/H3) for key intents."),
        "No Answer-Friendly Structure": ("Page lacks lists/tables that help concise answer extraction.", "Introduce structured bullets, ordered steps, or tables for key answers."),
        "No 40-60 Word Answer Paragraphs": ("No concise answer-length paragraph detected.", "Add a direct 30-60 word answer summary near question headings."),
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
