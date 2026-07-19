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


ISSUE_CONTENT: dict[str, dict[str, str]] = {
    # --- Critical -----------------------------------------------------
    "Non-200 Status": {
        "what_it_is": "The URL returns a 4xx/5xx HTTP status instead of 200 OK.",
        "why_it_matters": "Search engines drop non-200 URLs from the index and users hit a dead page — any inbound links or ranking history on the URL is wasted.",
        "how_to_fix": "Restore the page if it was removed by mistake, or implement a 301 redirect to the correct live URL. Update internal links to point at the final destination directly.",
        "how_to_verify": "Re-crawl the URL and confirm Status Code is 200 on the Main tab.",
    },
    "Missing Title": {
        "what_it_is": "The HTML <title> element is absent or empty.",
        "why_it_matters": "Titles are the primary SERP headline and one of the strongest on-page relevance signals; without one, search engines auto-generate a title that rarely matches intent.",
        "how_to_fix": "Add one unique <title> per URL (50–60 characters), leading with the primary topic then brand, and publish.",
        "how_to_verify": "View source or check Title Health on the Content Optimisation Hub — should read OK.",
    },
    "Noindex Directive": {
        "what_it_is": "A meta robots tag or X-Robots-Tag header contains noindex for this URL.",
        "why_it_matters": "Noindex tells search engines to exclude the page from results entirely, so it cannot rank or receive organic traffic regardless of content quality.",
        "how_to_fix": "Remove the noindex directive from the page template or server header unless the URL is intentionally excluded (e.g. thank-you or admin pages).",
        "how_to_verify": "Inspect the rendered <head> or response headers and confirm noindex is gone; check GSC coverage status updates after recrawl.",
    },
    "Canonical Points Elsewhere": {
        "what_it_is": "The rel=canonical tag targets a different URL variant than the one being crawled.",
        "why_it_matters": "Search engines will consolidate ranking signals onto the canonical target, not this URL — if that's unintentional, this page will never rank under its own address.",
        "how_to_fix": "Set the canonical to self-reference the URL's own final address unless it is deliberately a duplicate of another page, and make sure internal links point at the canonical target.",
        "how_to_verify": "Check Canonical Type on Main reads self-canonical (not cross-canonical) for URLs that should rank independently.",
    },
    "Robots.txt Disallow Root": {
        "what_it_is": "robots.txt disallows crawling of the site root or a directory that includes this URL.",
        "why_it_matters": "A blanket disallow can silently deindex large sections of the site — this is a site-wide risk, not a single-page issue.",
        "how_to_fix": "Edit robots.txt to remove the overly broad Disallow rule, scoping any intentional blocks to specific paths only.",
        "how_to_verify": "Fetch /robots.txt and confirm the affected paths are no longer disallowed; use GSC's robots.txt tester to double-check.",
    },
    "CWV LCP Above 4.0s (Field Data)": {
        "what_it_is": "Real-user (CrUX field) Largest Contentful Paint exceeds 4.0 seconds for this URL.",
        "why_it_matters": "LCP is a Core Web Vital ranking factor and directly affects perceived load speed and conversion; anything above 4.0s is classified 'poor' by Google.",
        "how_to_fix": "Optimise the largest above-the-fold element: compress/resize hero images, preload the LCP resource, remove render-blocking CSS/JS, and use a CDN.",
        "how_to_verify": "Re-check field data in PageSpeed Insights/CrUX after the fix propagates (field data trends over the trailing 28 days, so allow time).",
    },
    "Lab LCP Above 4.0s (Mobile)": {
        "what_it_is": "Lab-measured (Lighthouse) mobile LCP exceeds 4.0 seconds.",
        "why_it_matters": "Lab LCP is an immediate, reproducible signal of slow mobile rendering, which hurts both rankings and mobile user retention.",
        "how_to_fix": "Reduce mobile payload: compress images, defer non-critical JS/CSS, enable text compression, and preconnect to critical origins.",
        "how_to_verify": "Re-run a mobile Lighthouse/PSI audit on the URL and confirm Lab LCP (Mobile) drops below 4.0s.",
    },
    "Broken Internal Links": {
        "what_it_is": "One or more internal links on this page resolve to a missing or error page.",
        "why_it_matters": "Broken internal links waste crawl budget, dilute link equity, and create dead ends that frustrate users.",
        "how_to_fix": "Update each broken link to the correct live URL, or remove the link if the target no longer exists.",
        "how_to_verify": "Check Broken Internal Links Count on Main returns to 0, and cross-check the Link Intelligence tab's Detail rows for remaining 4xx/5xx targets from this page.",
    },
    "Redirect Loop": {
        "what_it_is": "The URL's redirect chain loops back on itself instead of reaching a final 200 destination.",
        "why_it_matters": "Browsers and crawlers abandon looping redirects, so the page is completely unreachable for users and search engines alike.",
        "how_to_fix": "Trace the redirect chain (see the Redirects tab) and correct whichever hop points back to an earlier URL in the chain.",
        "how_to_verify": "Follow the redirect chain manually or re-crawl and confirm it terminates in a single 200 response with no loop flag.",
    },
    "Canonical Loop": {
        "what_it_is": "Canonical tags between two or more URLs point at each other in a cycle.",
        "why_it_matters": "Search engines can't resolve which URL is authoritative, so ranking signals may be split or dropped entirely for the whole cluster.",
        "how_to_fix": "Pick one URL as the true canonical for the group and point every other URL's canonical tag at it (not at each other).",
        "how_to_verify": "Trace each URL's canonical target and confirm they all converge on a single non-looping destination.",
    },
    "Canonical Points to Broken URL": {
        "what_it_is": "The canonical tag targets a URL that itself returns a non-200 status.",
        "why_it_matters": "Search engines can't consolidate signals onto a dead canonical target, effectively orphaning this page's ranking potential.",
        "how_to_fix": "Point the canonical at a live, 200-status URL — either restore the target page or update the canonical to self-reference.",
        "how_to_verify": "Fetch the canonical target URL directly and confirm it returns 200.",
    },
    "Not Indexed by Google": {
        "what_it_is": "Google Search Console reports this URL is not indexed.",
        "why_it_matters": "Non-indexed pages cannot appear in search results or earn organic traffic no matter how well-optimised they are.",
        "how_to_fix": "Review the GSC coverage reason on the Main tab, remove any accidental noindex/robots blocks, strengthen internal links to the page, and request indexing.",
        "how_to_verify": "Check GSC Index Status on Main after the next crawl, and use URL Inspection in Search Console to confirm indexing.",
        "owner": "Dev",
    },
    "In Sitemap but Blocked by Googlebot": {
        "what_it_is": "The URL is listed in the XML sitemap but robots.txt disallows Googlebot from crawling it.",
        "why_it_matters": "This sends Google a contradictory signal — 'index this' via the sitemap and 'don't crawl this' via robots.txt — wasting crawl budget and preventing indexing.",
        "how_to_fix": "Either remove the URL from the sitemap if it's intentionally blocked, or remove the robots.txt disallow if it should be indexed.",
        "how_to_verify": "Confirm the URL no longer appears in both the sitemap and a matching robots.txt Disallow rule.",
    },
    "Near-Duplicate Content": {
        "what_it_is": "This page's heading/body structure closely matches another crawled URL.",
        "why_it_matters": "Search engines may choose only one version to rank and can flag the site for thin/duplicate content, diluting authority across near-identical pages.",
        "how_to_fix": "Consolidate into one canonical URL — 301 redirect or noindex the duplicate, and rewrite overlapping H2/H3 blocks to be unique where both pages must remain live.",
        "how_to_verify": "Compare the two URLs' body content after the fix and confirm Is Near Duplicate no longer flags true.",
    },
    "No Schema Markup": {
        "what_it_is": "No structured data (JSON-LD) was detected on the page.",
        "why_it_matters": "Schema is how search and answer engines understand page type/entities beyond raw text — without it, rich results and AI-overview eligibility are lost.",
        "how_to_fix": "Add the appropriate JSON-LD type for the page (Article, Product, FAQPage, Organization, etc.) mirroring the visible content.",
        "how_to_verify": "Validate with Google's Rich Results Test and confirm Schema Present reads true on Main.",
    },
    "Schema Parse Error": {
        "what_it_is": "JSON-LD is present but fails to parse as valid JSON/structured data.",
        "why_it_matters": "Invalid schema is ignored by search engines entirely — it provides zero benefit while still adding page weight.",
        "how_to_fix": "Fix the JSON syntax error (check for trailing commas, unescaped quotes, or malformed nesting) using the Schema Parse Error Detail column for the exact fault.",
        "how_to_verify": "Re-validate with Google's Rich Results Test or schema.org validator and confirm zero parse errors.",
    },
    "OG Image Broken (non-200)": {
        "what_it_is": "The Open Graph image URL returns a non-200 status when fetched.",
        "why_it_matters": "Social platforms (Facebook, LinkedIn, X) fail to render a preview image on share, hurting click-through from social referral traffic.",
        "how_to_fix": "Upload a working image at the og:image URL, or update the tag to point at a live image asset.",
        "how_to_verify": "Fetch the og:image URL directly and confirm 200, then re-test with Facebook's Sharing Debugger.",
    },
    "High Broken Image Count (>3)": {
        "what_it_is": "More than 3 images on this page fail to load (broken src references).",
        "why_it_matters": "Multiple broken images signal a template or migration problem and visibly degrade page quality and user trust.",
        "how_to_fix": "Audit the Image Inventory tab for this page's broken entries, fix or replace each src, and check for a systemic cause (e.g. a CDN path change).",
        "how_to_verify": "Re-crawl and confirm Broken Image Count drops to 0 or near-0 for the page.",
    },
    # --- Warning --------------------------------------------------------
    "Redirect Chains": {
        "what_it_is": "The URL passes through more than one redirect hop before reaching its final destination.",
        "why_it_matters": "Each extra hop adds latency and dilutes link equity slightly; long chains occasionally break entirely in some crawlers/browsers.",
        "how_to_fix": "Update the original link/reference to point directly at the final destination URL, collapsing the chain to a single hop.",
        "how_to_verify": "Check Redirect Chain Length on the Redirects tab is 1 (or 0) after the fix.",
    },
    "302 Redirect (Temporary)": {
        "what_it_is": "The redirect uses a 302 (temporary) status instead of 301 (permanent).",
        "why_it_matters": "Search engines may not pass full ranking signal through a 302 and may keep the old URL indexed indefinitely, splitting authority.",
        "how_to_fix": "Change the redirect to a 301 if the move is permanent (the common case for URL restructures).",
        "how_to_verify": "Check the response header on the source URL returns 301, and confirm Has 302 in Chain is false.",
    },
    "Mixed 301/302 Chain": {
        "what_it_is": "A single redirect chain contains both 301 and 302 hops.",
        "why_it_matters": "Mixed-type chains create ambiguous signals about permanence, and search engines may not fully consolidate ranking value along the chain.",
        "how_to_fix": "Standardise every hop in the chain to 301 unless a hop is genuinely temporary, and shorten the chain where possible.",
        "how_to_verify": "Trace the full chain on the Redirects tab and confirm consistent 301 status codes end to end.",
    },
    "Canonical Chain (>1 hop)": {
        "what_it_is": "Canonical tags chain through more than one intermediate URL before reaching the final canonical target.",
        "why_it_matters": "Search engines may not follow multi-hop canonical chains reliably, risking the wrong URL (or none) being treated as authoritative.",
        "how_to_fix": "Point every URL in the chain directly at the single true canonical target instead of at each other.",
        "how_to_verify": "Check Canonical Chain Depth on Main is 0 or 1 after the fix.",
    },
    "Canonical Points to Redirect": {
        "what_it_is": "The canonical tag targets a URL that itself redirects elsewhere.",
        "why_it_matters": "Search engines have to follow an extra hop to find the true target, adding ambiguity to which URL should rank.",
        "how_to_fix": "Update the canonical tag to point directly at the final destination URL, skipping the redirect hop.",
        "how_to_verify": "Fetch the canonical target URL and confirm it returns 200 directly (no further redirect).",
    },
    "Not Crawled in >30 Days": {
        "what_it_is": "Google Search Console's last-crawl data shows this URL hasn't been crawled in over 30 days.",
        "why_it_matters": "Stale crawl data means recent content changes may not be reflected in search results, and ranking signals may lag.",
        "how_to_fix": "Strengthen internal linking to the page and submit it via URL Inspection in Search Console to request a recrawl.",
        "how_to_verify": "Check Days Since Last Crawl on Main drops after Google recrawls (may take days to update).",
    },
    "GSC Mobile Usability Issue": {
        "what_it_is": "Google Search Console flags this URL as not mobile-friendly.",
        "why_it_matters": "Google predominantly uses mobile-first indexing, so mobile usability problems directly suppress ranking and hurt the majority of visitors on mobile devices.",
        "how_to_fix": "Review the specific GSC mobile usability flag (viewport, tap targets, text size) and adjust the responsive template accordingly.",
        "how_to_verify": "Re-run the Mobile-Friendly Test in Search Console and confirm the issue clears from the Mobile Usability report.",
    },
    "GSC Rich Result Error": {
        "what_it_is": "Google Search Console reports an invalid rich-result status for this URL's structured data.",
        "why_it_matters": "Invalid rich results are excluded from enhanced SERP features (stars, FAQs, etc.), losing valuable SERP real estate.",
        "how_to_fix": "Open the specific error in GSC's Rich Results report and correct the flagged schema property.",
        "how_to_verify": "Re-validate with Rich Results Test and confirm the status changes from Invalid to Valid.",
    },
    "Blocked by Googlebot": {
        "what_it_is": "robots.txt explicitly disallows Googlebot from crawling this URL.",
        "why_it_matters": "This removes the page from Google search entirely — the largest source of organic traffic for most sites.",
        "how_to_fix": "Remove the Googlebot-specific Disallow rule in robots.txt unless the block is intentional (e.g. staging/admin paths).",
        "how_to_verify": "Check Robots.txt: Googlebot on Main reads Allow after the edit, and use GSC's robots.txt tester to confirm.",
        "owner": "Dev",
    },
    "Blocked by Bingbot": {
        "what_it_is": "robots.txt explicitly disallows Bingbot from crawling this URL.",
        "why_it_matters": "This removes the page from Bing/Yahoo search entirely, losing that traffic share.",
        "how_to_fix": "Remove the Bingbot-specific Disallow rule in robots.txt unless the block is intentional.",
        "how_to_verify": "Check Robots.txt: Bingbot on Main reads Allow after the edit.",
    },
    "Missing Meta Description": {
        "what_it_is": "The meta description tag is missing or empty.",
        "why_it_matters": "Descriptions influence click-through from search results even when not a direct ranking factor — without one Google auto-generates a snippet that rarely sells the page well.",
        "how_to_fix": "Write a unique 120–155 character summary matching search intent, with a soft call to action, avoiding duplication of the title.",
        "how_to_verify": "View source or check the Content Optimisation Hub — Meta Description Health should read OK.",
    },
    "Missing H1": {
        "what_it_is": "The page has no <h1> heading.",
        "why_it_matters": "The H1 is the primary on-page topic signal for both users and search engines; its absence weakens topical clarity.",
        "how_to_fix": "Add one clear, unique H1 that states the page's primary topic, matching (but not duplicating verbatim) the title tag.",
        "how_to_verify": "Inspect the rendered page and confirm exactly one <h1> is present.",
    },
    "Multiple H1": {
        "what_it_is": "The page has more than one <h1> heading.",
        "why_it_matters": "Multiple H1s dilute the primary topic signal and can confuse both users skimming the page structure and search engines parsing hierarchy.",
        "how_to_fix": "Keep a single H1 for the page's main topic and demote the others to H2/H3 as appropriate subsections.",
        "how_to_verify": "Inspect the rendered page and confirm exactly one <h1> remains.",
    },
    "CWV CLS Above 0.1 (Field Data)": {
        "what_it_is": "Real-user (CrUX field) Cumulative Layout Shift exceeds 0.1 for this URL.",
        "why_it_matters": "CLS is a Core Web Vital; visible layout shift frustrates users (mis-clicks) and is penalised in ranking.",
        "how_to_fix": "Reserve explicit width/height (or aspect-ratio) for images/embeds, avoid injecting content above existing content, and preload web fonts to prevent FOIT/FOUT shifts.",
        "how_to_verify": "Re-check field CLS in PageSpeed Insights/CrUX after the fix propagates over the trailing 28-day window.",
    },
    "CWV INP Above 200ms (Field Data)": {
        "what_it_is": "Real-user (CrUX field) Interaction to Next Paint exceeds the warning threshold for this URL.",
        "why_it_matters": "INP measures real responsiveness to clicks/taps; slow INP directly hurts usability and is a Core Web Vital ranking factor.",
        "how_to_fix": "Break up long JavaScript tasks, defer non-critical scripts, and reduce main-thread work triggered by user interactions.",
        "how_to_verify": "Re-check field INP in PageSpeed Insights/CrUX after the fix propagates.",
    },
    "Lab LCP 2.5s–4.0s (Mobile)": {
        "what_it_is": "Lab-measured mobile LCP falls in the 'needs improvement' band (2.5s–4.0s).",
        "why_it_matters": "This is on the edge of Google's 'good' threshold — closing the gap now is cheaper than after it degrades into the 'poor' (>4.0s) band.",
        "how_to_fix": "Trim hero image size, preload the LCP element, and remove render-blocking resources above the fold.",
        "how_to_verify": "Re-run a mobile Lighthouse/PSI audit and confirm Lab LCP (Mobile) drops below 2.5s.",
    },
    "Lab TBT Above 300ms (Mobile)": {
        "what_it_is": "Lab-measured mobile Total Blocking Time exceeds 300ms.",
        "why_it_matters": "High TBT means the main thread is busy with JS during load, making the page feel unresponsive to early taps.",
        "how_to_fix": "Split large JS bundles, defer non-critical scripts, and remove/replace heavy third-party tags blocking the main thread.",
        "how_to_verify": "Re-run a mobile Lighthouse audit and confirm Lab TBT (Mobile) drops below 300ms.",
    },
    "Lab CLS Above 0.1 (Mobile)": {
        "what_it_is": "Lab-measured mobile Cumulative Layout Shift exceeds 0.1.",
        "why_it_matters": "Layout shift on mobile is especially disruptive for touch interaction and directly affects Core Web Vitals scoring.",
        "how_to_fix": "Reserve space for images/ads/embeds with explicit dimensions and avoid late-injected banners above existing content.",
        "how_to_verify": "Re-run a mobile Lighthouse audit and confirm Lab CLS (Mobile) drops below 0.1.",
    },
    "Low Lighthouse Performance Mobile (<50)": {
        "what_it_is": "The Lighthouse mobile Performance score is below 50 (out of 100).",
        "why_it_matters": "A sub-50 score indicates a poor mobile experience across the board, which correlates with higher bounce rates and lower rankings.",
        "how_to_fix": "Address the top Lighthouse opportunities/diagnostics for this URL — typically image optimisation, JS reduction, and render-blocking resources.",
        "how_to_verify": "Re-run mobile Lighthouse/PSI and confirm the Performance score rises above 50 (target 90+).",
    },
    "Low Lighthouse Accessibility (<80)": {
        "what_it_is": "The Lighthouse Accessibility score is below 80 (out of 100).",
        "why_it_matters": "Low accessibility scores indicate real usability barriers for assistive-technology users and can carry legal/compliance risk (WCAG).",
        "how_to_fix": "Fix the specific Lighthouse accessibility audits flagged (commonly: missing alt text, low colour contrast, missing form labels, invalid ARIA).",
        "how_to_verify": "Re-run Lighthouse and confirm the Accessibility score rises above 80.",
    },
    "Lab TTFB Above 600ms": {
        "what_it_is": "Lab-measured mobile Time to First Byte exceeds 600ms.",
        "why_it_matters": "Slow TTFB delays everything downstream (LCP, INP) and often points to server/hosting or backend performance problems.",
        "how_to_fix": "Investigate server response time: enable caching, upgrade hosting/PHP version, optimise database queries, or add a CDN.",
        "how_to_verify": "Re-run a mobile Lighthouse audit and confirm Lab TTFB (Mobile) drops below 600ms.",
        "owner": "Server/Host",
    },
    "Missing FAQ/QA Schema": {
        "what_it_is": "Question-style content is present without matching FAQPage/QAPage JSON-LD.",
        "why_it_matters": "Answer engines and AI overviews increasingly rely on schema as a stable API surface — visible Q&A copy without matching schema is far less likely to be surfaced.",
        "how_to_fix": "Publish machine-readable FAQPage or QAPage JSON-LD that mirrors the visible question/answer text on the page.",
        "how_to_verify": "Validate with Google's Rich Results Test and confirm QAPage/FAQ Schema Present is true.",
    },
    "Deep URL (>3 clicks)": {
        "what_it_is": "The page requires more than 3 clicks from the homepage to reach (click depth).",
        "why_it_matters": "Deep pages receive less crawl frequency and weaker internal link equity, which suppresses their ranking potential.",
        "how_to_fix": "Add internal links from higher-authority, shallower pages (nav, related-content blocks, hub pages) to reduce click depth.",
        "how_to_verify": "Check Click Depth on the Link Intelligence/Main tab drops to 3 or fewer after new links are added and re-crawled.",
    },
    "Low Image Alt Coverage": {
        "what_it_is": "Fewer than 80% of images on the page have alt text.",
        "why_it_matters": "Missing alt text hurts accessibility for screen-reader users and removes a ranking/context signal for image search.",
        "how_to_fix": "Add descriptive, unique alt text to every content image (decorative images can use alt=\"\").",
        "how_to_verify": "Check Image Alt Coverage (%) on Main/Image Inventory rises to 100% (or as close as content allows).",
    },
    "Mixed Content": {
        "what_it_is": "An HTTPS page references one or more insecure HTTP assets (images, scripts, stylesheets).",
        "why_it_matters": "Browsers block or warn on mixed content, which can break page functionality and shows a broken padlock/security warning to users.",
        "how_to_fix": "Update every hardcoded http:// asset URL to https://, or use protocol-relative/absolute HTTPS paths.",
        "how_to_verify": "Open DevTools console on the live page and confirm no mixed-content warnings remain.",
    },
    "Canonical Missing": {
        "what_it_is": "The page has no rel=canonical tag at all.",
        "why_it_matters": "Without an explicit canonical, search engines must guess which URL variant (with/without params, trailing slash, etc.) is authoritative.",
        "how_to_fix": "Add a self-referencing canonical tag to every indexable page.",
        "how_to_verify": "View source and confirm a rel=canonical tag is present and correct.",
    },
    "Hreflang Without Reciprocity": {
        "what_it_is": "Hreflang alternates on this page do not reference back to it from the other language/region URLs.",
        "why_it_matters": "Google may ignore one-way hreflang clusters entirely, causing wrong-country rankings or duplicate-content treatment across the language set.",
        "how_to_fix": "List every language variant on each page in the cluster and ensure each alternate URL returns the same reciprocal set of hreflang tags.",
        "how_to_verify": "Check Hreflang Reciprocal Status reads Valid on Main after all variants are updated.",
        "owner": "Dev",
    },
    "Invalid Hreflang Language Code": {
        "what_it_is": "One or more hreflang values use non-standard language or region codes.",
        "why_it_matters": "Invalid codes are silently ignored by search engines, breaking international targeting without any visible error to users.",
        "how_to_fix": "Use ISO 639-1 language codes (e.g. en, fr) with an optional ISO 3166-1 region (e.g. en-GB), and keep x-default for the fallback URL.",
        "how_to_verify": "Check Hreflang Code Valid reads true on Main after the correction.",
        "owner": "Dev",
    },
    "Render Fallback (raw HTTP)": {
        "what_it_is": "Accurate crawl mode attempted Playwright rendering but fell back to the raw HTTP payload for this URL.",
        "why_it_matters": "Content that depends on JavaScript rendering may be missing or incomplete in this row, understating true page quality.",
        "how_to_fix": "Re-run in accurate mode with Playwright installed, or fix page timeouts/blocking so rendered_browser extraction succeeds for parity with other URLs.",
        "how_to_verify": "Re-crawl the URL and confirm Extraction Source Fallback is false.",
        "owner": "Dev",
    },
    "Thin Content (<200 words)": {
        "what_it_is": "The page's body content is under 200 words.",
        "why_it_matters": "Search engines have low confidence indexing very short pages, and they rarely satisfy user intent well enough to rank.",
        "how_to_fix": "Expand the page with unique, helpful, intent-matching content — real detail, not filler.",
        "how_to_verify": "Check Is Thin Content reads false on Main after the content is expanded.",
    },
    "Draft or Test Page (URL pattern)": {
        "what_it_is": "The URL pattern matches a draft/test/staging naming convention (e.g. containing '-copy', '-draft', '-test').",
        "why_it_matters": "Draft/test URLs left live and crawlable can get indexed as duplicate or low-quality content, and often expose unfinished work publicly.",
        "how_to_fix": "Noindex or delete the draft/test page, or 301 redirect it to the finished production URL.",
        "how_to_verify": "Confirm the URL is no longer reachable/crawlable, or check Is Draft or Test Page reads false if the URL was legitimately renamed.",
    },
    "Schema Validation Errors": {
        "what_it_is": "The page's structured data contains one or more schema.org validation errors.",
        "why_it_matters": "Schema with errors is typically ignored or only partially used by search engines, losing rich-result eligibility.",
        "how_to_fix": "Open the Schema Error Count detail and correct each flagged property against the relevant schema.org type spec.",
        "how_to_verify": "Re-validate with Google's Rich Results Test and confirm Schema Error Count is 0.",
    },
    "Missing Event Schema": {
        "what_it_is": "The URL looks like an event/conference/webinar page (by URL pattern) but has no structured data.",
        "why_it_matters": "Event schema powers rich date/location results in search, which meaningfully lifts click-through for time-sensitive pages.",
        "how_to_fix": "Add Event JSON-LD with name, startDate, location, and offers matching the visible page content.",
        "how_to_verify": "Validate with Rich Results Test and confirm Schema Present is true.",
    },
    "Missing Article Schema": {
        "what_it_is": "The URL looks like a news/blog/article page (by URL pattern) but has no structured data.",
        "why_it_matters": "Article schema enables author/date/headline rich results and supports AI/answer-engine citation of the content.",
        "how_to_fix": "Add Article or NewsArticle JSON-LD with headline, datePublished, and author matching the visible byline.",
        "how_to_verify": "Validate with Rich Results Test and confirm Schema Present is true.",
    },
    "Low E-E-A-T Signal Score (<3)": {
        "what_it_is": "The page scores below 3 on the composite Experience/Expertise/Authoritativeness/Trust signal check (author byline, credentials, citations, contact/about links).",
        "why_it_matters": "Google's quality raters and ranking systems weigh E-E-A-T heavily for YMYL and informational content; weak signals suppress ranking potential even with good copy.",
        "how_to_fix": "Add a visible author byline with credentials, link to an About/Contact page, and cite credible sources where claims are made.",
        "how_to_verify": "Re-check E-E-A-T Signal Score on Main rises to 3 or above after the additions.",
    },
    "No Privacy Policy Link": {
        "what_it_is": "No footer/navigation link to a Privacy Policy page was found anywhere on the site.",
        "why_it_matters": "A missing privacy policy is a trust signal Google's quality guidelines explicitly look for, and is a compliance risk (GDPR/POPIA/CCPA) for sites collecting any personal data.",
        "how_to_fix": "Publish a Privacy Policy page (e.g. at /privacy-policy/) covering what data is collected and how it's used, then link it from the site footer and/or main navigation.",
        "how_to_verify": "Check Has Privacy Policy Link reads true on Main after the link is added site-wide.",
    },
    "No Terms Link": {
        "what_it_is": "No footer/navigation link to a Terms of Service or Terms & Conditions page was found anywhere on the site.",
        "why_it_matters": "Terms of use are a standard trust signal expected by both users and Google's quality guidelines, and protect the business by setting clear usage/liability terms.",
        "how_to_fix": "Publish a Terms of Service / Terms & Conditions page (e.g. at /terms/ or /terms-and-conditions/) and link it from the site footer alongside the Privacy Policy.",
        "how_to_verify": "Check Has Terms Link reads true on Main after the link is added site-wide.",
    },
    "Missing OG Title": {
        "what_it_is": "The og:title Open Graph tag is missing.",
        "why_it_matters": "Without og:title, social platforms fall back to an auto-picked heading when the page is shared, often the wrong one — hurting social click-through.",
        "how_to_fix": "Add an og:title tag, ideally matching or closely mirroring the page's <title>.",
        "how_to_verify": "Re-test the URL in Facebook's Sharing Debugger or LinkedIn Post Inspector and confirm the title renders correctly.",
    },
    "Missing OG Description": {
        "what_it_is": "The og:description Open Graph tag is missing.",
        "why_it_matters": "Without it, social share previews show no summary text (or an auto-scraped fragment), reducing click appeal.",
        "how_to_fix": "Add an og:description tag with a concise, compelling summary (can mirror the meta description).",
        "how_to_verify": "Re-test the URL in Facebook's Sharing Debugger and confirm the description renders.",
    },
    "Missing OG Image": {
        "what_it_is": "No og:image tag (or usable image URL) is set for the page.",
        "why_it_matters": "Shares without a preview image get far lower engagement/click-through on every major social platform.",
        "how_to_fix": "Add an og:image tag pointing at a hosted image at least 1200×630px.",
        "how_to_verify": "Re-test the URL in Facebook's Sharing Debugger and confirm a preview image renders.",
    },
    "OG URL Mismatch": {
        "what_it_is": "The og:url tag does not match the page's actual final/canonical URL.",
        "why_it_matters": "A mismatched og:url can cause shares/likes to accrue against the wrong URL, splitting social signal and analytics.",
        "how_to_fix": "Set og:url to exactly match the canonical URL of the page.",
        "how_to_verify": "View source and confirm og:url equals the Final URL/Canonical URL value on Main.",
    },
    "Broken Images": {
        "what_it_is": "One or more images on the page fail to load (broken src references).",
        "why_it_matters": "Broken images visibly degrade page quality and user trust, and waste crawl budget on dead asset requests.",
        "how_to_fix": "Check the Image Inventory tab for this page's broken entries and fix or replace each src.",
        "how_to_verify": "Re-crawl and confirm Broken Image Count is 0 for the page.",
    },
    "High Third-Party Script Count (>10)": {
        "what_it_is": "More than 10 third-party scripts (analytics, ads, widgets, trackers) load on this page.",
        "why_it_matters": "Excess third-party JS is a leading cause of slow load times and main-thread blocking, directly hurting Core Web Vitals.",
        "how_to_fix": "Audit the Script Inventory tab, remove unused/redundant tags, and load remaining non-critical scripts async/deferred or via a tag manager with consent gating.",
        "how_to_verify": "Re-crawl and confirm Third Party Script Count drops to 10 or fewer.",
    },
    "Third-Party Scripts Blocking Render": {
        "what_it_is": "One or more third-party scripts block page rendering (synchronous, render-blocking load).",
        "why_it_matters": "Render-blocking scripts delay First Contentful Paint and LCP, directly hurting perceived speed and Core Web Vitals.",
        "how_to_fix": "Add async or defer attributes to third-party script tags, or load them via a tag manager after first paint.",
        "how_to_verify": "Re-run Lighthouse and confirm Has Render Blocking Resources / Third Party JS Blocking reads false.",
    },
    "Under-Linked Priority Page": {
        "what_it_is": "A page with a high Business Risk Score (≥30) has fewer than the expected number of internal inbound links.",
        "why_it_matters": "Important pages that are weakly linked internally receive less crawl priority and less passed-through link equity than their business value warrants.",
        "how_to_fix": "Add internal links from relevant high-traffic or high-authority pages (nav, related content, contextual body links) pointing to this URL.",
        "how_to_verify": "Check Inbound Internal Link Count on the Link Intelligence tab rises after new links are added and re-crawled.",
    },
    "Low AEO Readiness Score": {
        "what_it_is": "The page's weighted Answer Engine Optimisation score is below the 70-point extraction-confidence band.",
        "why_it_matters": "Answer engines and AI overviews favour concise, structured, factual copy — a low score means this page is unlikely to be cited or extracted by AI search tools.",
        "how_to_fix": "Add question-style H2/H3 headings, place a 40–60 word factual answer directly beneath each, add FAQPage/HowTo/Speakable JSON-LD, use ul/ol/table for key facts, and ensure robots.txt explicitly allows GPTBot, PerplexityBot, and CCBot.",
        "how_to_verify": "Re-check AEO Readiness Score on Main rises above 70 after the content updates.",
        "owner": "Copy Writer",
    },
    # --- Observation ------------------------------------------------------
    "AI Crawlers: GPTBot Blocked": {
        "what_it_is": "robots.txt disallows GPTBot (OpenAI's crawler) site-wide.",
        "why_it_matters": "Blocking GPTBot excludes the site's content from being referenced by ChatGPT and related AI answer surfaces, a growing traffic/visibility channel.",
        "how_to_fix": "Remove the GPTBot Disallow rule in robots.txt unless intentionally opting out of AI training/answer use.",
        "how_to_verify": "Fetch /robots.txt and confirm no Disallow rule targets GPTBot.",
        "owner": "Dev",
    },
    "AI Crawlers: ClaudeBot Blocked": {
        "what_it_is": "robots.txt disallows ClaudeBot (Anthropic's crawler) site-wide.",
        "why_it_matters": "Blocking ClaudeBot excludes the site's content from being referenced by Claude's answer/search surfaces, a growing traffic/visibility channel.",
        "how_to_fix": "Remove the ClaudeBot Disallow rule in robots.txt unless intentionally opting out of AI training/answer use.",
        "how_to_verify": "Fetch /robots.txt and confirm no Disallow rule targets ClaudeBot.",
        "owner": "Dev",
    },
    "Uses URL Parameters": {
        "what_it_is": "The URL contains query-string parameters (e.g. ?sort=, ?utm_).",
        "why_it_matters": "Parameterised URLs can create near-duplicate crawlable variants of the same page, spreading crawl budget and link equity thin.",
        "how_to_fix": "Canonicalise to the clean (parameter-free) URL and exclude tracking-parameter variants via robots.txt or GSC's URL parameters tool where appropriate.",
        "how_to_verify": "Confirm the canonical tag on parameterised variants points to the clean URL.",
    },
    "Generic Anchor Text Present": {
        "what_it_is": "One or more internal links use generic anchor text (e.g. 'click here', 'read more', 'this page').",
        "why_it_matters": "Generic anchors carry no topical signal to search engines and are less helpful to screen-reader users navigating by link list.",
        "how_to_fix": "Rewrite anchor text to be descriptive of the destination page's topic.",
        "how_to_verify": "Check Generic Anchor Text Count on Main drops to 0 after anchors are rewritten.",
    },
    "Image Filename Quality Issues": {
        "what_it_is": "One or more images use low-quality filenames (e.g. IMG_1234.jpg, generic auto-generated names).",
        "why_it_matters": "Descriptive filenames are a minor but free image-search relevance signal that's lost with generic names.",
        "how_to_fix": "Rename image files to short, descriptive, hyphenated names reflecting their content before re-uploading.",
        "how_to_verify": "Check the Image Inventory tab shows descriptive filenames for the affected images.",
    },
    "No Compression Header": {
        "what_it_is": "The server response does not include a compression encoding (e.g. gzip/br) for this URL.",
        "why_it_matters": "Uncompressed responses are larger than necessary, slowing load time and Core Web Vitals, especially on mobile connections.",
        "how_to_fix": "Enable gzip or Brotli compression at the web server/CDN level for HTML/CSS/JS responses.",
        "how_to_verify": "Check the response headers include Content-Encoding: gzip or br after the change.",
        "owner": "Server/Host",
    },
    "No Cache-Control Header": {
        "what_it_is": "The response has no Cache-Control header.",
        "why_it_matters": "Without caching directives, browsers and CDNs can't efficiently cache the resource, causing unnecessary repeat downloads and slower repeat visits.",
        "how_to_fix": "Add an appropriate Cache-Control header (with sensible max-age) at the server/CDN level for static and semi-static resources.",
        "how_to_verify": "Check the response headers include a Cache-Control value after the change.",
        "owner": "Server/Host",
    },
    "No ETag Header": {
        "what_it_is": "The server response has no ETag header for this resource.",
        "why_it_matters": "Without an ETag, browsers can't efficiently validate cached copies, leading to more full re-downloads than necessary.",
        "how_to_fix": "Enable ETag generation at the web server/CDN level (most servers support this natively).",
        "how_to_verify": "Check the response headers include an ETag value after the change.",
        "owner": "Server/Host",
    },
    "Thin Content": {
        "what_it_is": "The page's body content is judged thin relative to its page type/template expectations.",
        "why_it_matters": "Thin pages provide little value to searchers and are less likely to earn rankings against more comprehensive competing content.",
        "how_to_fix": "Expand the page with unique, helpful, intent-matching content addressing what a visitor would actually want to know.",
        "how_to_verify": "Check Thin Content Flag reads false on Main after the content is expanded.",
    },
    "Schema Validation Warnings": {
        "what_it_is": "The page's structured data has warnings (non-fatal issues) but no hard errors.",
        "why_it_matters": "Warnings often mean missing recommended (not required) properties, limiting how rich the resulting search feature can be even though the schema still validates.",
        "how_to_fix": "Review the Schema Warning Count detail and add the recommended properties the validator flags.",
        "how_to_verify": "Re-validate with Rich Results Test and confirm the warning count drops.",
    },
    "No Author Attribution": {
        "what_it_is": "No author name is present via schema, meta tag, or a visible byline element.",
        "why_it_matters": "Author attribution is an E-E-A-T signal, especially important for informational/YMYL content — its absence weakens perceived trust and expertise.",
        "how_to_fix": "Add a visible author byline and matching Person schema (or meta author tag) with the author's name and, ideally, a bio/credentials link.",
        "how_to_verify": "Check Schema Author Name or Has Byline Element is populated on Main after the change.",
    },
    "No Publication Date": {
        "what_it_is": "No published date is present via OG tags or schema.",
        "why_it_matters": "Search engines and users use publish dates to judge content freshness/relevance; its absence can suppress visibility for time-sensitive queries.",
        "how_to_fix": "Add a datePublished value in the page's Article schema and/or an og:published_time meta tag.",
        "how_to_verify": "Check OG Published Time or Schema Published Date is populated on Main after the change.",
    },
    "Stale Content (>2 years)": {
        "what_it_is": "The page's content age exceeds the configured 'stale' threshold (default 2 years) since last meaningful update.",
        "why_it_matters": "Search engines favour fresher content for many query types, and visitors trust recently-updated pages more, especially for time-sensitive topics.",
        "how_to_fix": "Review and refresh the content — update facts/figures, add current context, and update the modified date/schema accordingly.",
        "how_to_verify": "Check Content Age (days) on Main drops below the stale threshold after the refresh, and Freshness Status updates.",
        "owner": "Copy Writer",
    },
    "Ageing Content (1-2 years)": {
        "what_it_is": "The page's content age falls in the 1–2 year 'ageing' band, approaching staleness.",
        "why_it_matters": "Catching ageing content before it becomes fully stale is cheaper and keeps rankings from sliding in the first place.",
        "how_to_fix": "Schedule a content review — refresh statistics/examples and update the modified date if changes are made.",
        "how_to_verify": "Check Content Age (days) and Freshness Status on Main after the review.",
        "owner": "Copy Writer",
    },
    "No Publication or Modification Date": {
        "what_it_is": "Neither a publish nor a last-modified date could be determined for this page.",
        "why_it_matters": "Without any date signal, freshness cannot be assessed by search engines or by this audit, which may undervalue genuinely current content.",
        "how_to_fix": "Add datePublished and dateModified to the page's schema, or an equivalent visible/meta date signal.",
        "how_to_verify": "Check Freshness Status on Main no longer reads Unknown after the change.",
        "owner": "Copy Writer",
    },
    "OG Type Not Set": {
        "what_it_is": "The og:type Open Graph tag is missing.",
        "why_it_matters": "og:type tells social platforms how to render the share (article vs. website vs. product); without it, platforms fall back to a generic default presentation.",
        "how_to_fix": "Add an og:type tag matching the page's content (e.g. article, website, product).",
        "how_to_verify": "View source and confirm og:type is present with the correct value.",
    },
    "Missing Twitter Card": {
        "what_it_is": "No Twitter/X Card meta tag (twitter:card) is present.",
        "why_it_matters": "Without a Twitter Card, shares on X fall back to a plain link with no preview image/summary, reducing engagement.",
        "how_to_fix": "Add twitter:card (typically summary_large_image) plus twitter:title/description/image tags.",
        "how_to_verify": "Re-test the URL in X's Card Validator and confirm a card renders.",
    },
    "OG Image Wrong Dimensions": {
        "what_it_is": "The og:image is present but its actual dimensions don't match recommended social preview dimensions.",
        "why_it_matters": "Incorrectly sized images get cropped or scaled poorly by social platforms, producing an unprofessional-looking share preview.",
        "how_to_fix": "Replace the image with one sized to at least 1200×630px (1.91:1 ratio) as recommended by Facebook/LinkedIn/X.",
        "how_to_verify": "Re-test the URL in Facebook's Sharing Debugger and confirm the preview image displays uncropped.",
    },
    "No Consent Manager Detected": {
        "what_it_is": "No cookie/privacy consent management platform was detected site-wide.",
        "why_it_matters": "Sites using tracking cookies without a consent mechanism risk non-compliance with GDPR/POPIA/CCPA and similar regulations.",
        "how_to_fix": "Install a consent management platform (e.g. a CMP banner) that gates non-essential cookies/scripts until consent is given.",
        "how_to_verify": "Check Has Consent Manager reads true on Main after the CMP is installed and re-crawled.",
        "owner": "Dev",
    },
    "Generic Anchor Dominance": {
        "what_it_is": "The majority of inbound internal anchor text pointing to this URL is generic (e.g. 'click here', 'read more').",
        "why_it_matters": "Dominant generic anchors mean this page's topical relevance isn't reinforced by its internal link profile, weakening its ranking signal for target keywords.",
        "how_to_fix": "Update internal links across the site pointing to this URL to use descriptive, keyword-relevant anchor text.",
        "how_to_verify": "Check the Content & AI Readiness tab shows reduced generic-anchor share for this destination URL.",
    },
    "No Question Headings": {
        "what_it_is": "None of the page's headings are phrased as user questions.",
        "why_it_matters": (
            "Question-style H2–H4 headings are the highest-leverage AEO fix on most sites: "
            "they give answer engines a clear query–answer pair to extract."
        ),
        "how_to_fix": (
            "Rewrite priority H2–H4 as natural-language questions (Who/What/How/Why) and place "
            "a concise 40–60 word factual answer directly underneath each heading."
        ),
        "how_to_verify": "Check Question Heading Count and Answer Blocks rise above 0 after the rewrite.",
        "owner": "Copy Writer",
    },
    "No 40-60 Word Answer Paragraphs": {
        "what_it_is": "No 40–60 word definitional paragraph appears directly under a question-style H2/H3.",
        "why_it_matters": (
            "This word-count band is what answer engines most often cite — without it, even good "
            "content is less likely to surface in AI overviews."
        ),
        "how_to_fix": (
            "Under each question-style heading, lead with a ~45-word factual answer (no fluff), "
            "then expand with supporting detail in lists or tables."
        ),
        "how_to_verify": "Check Answer Blocks (Paragraphs 40-60 Words Count) rises above 0 after the rewrite.",
        "owner": "Copy Writer",
    },
    "No Answer-Friendly Structure": {
        "what_it_is": "The page's content is dense prose without lists or tables where facts could be chunked.",
        "why_it_matters": "LLMs and answer engines strongly prefer scannable, structured formats when extracting facts to cite — dense prose is harder to parse into a discrete answer.",
        "how_to_fix": "Break data-heavy explanations into ul/ol steps or a comparison table so key facts are chunked and independently citable.",
        "how_to_verify": "Check List/Table Answer Signal reads true on Main after restructuring.",
        "owner": "Copy Writer",
    },
    "Lab TBT 150ms–300ms (Mobile)": {
        "what_it_is": "Lab-measured mobile Total Blocking Time falls in the 150–300ms 'needs improvement' band.",
        "why_it_matters": "This is on the edge of becoming a Warning-level TBT problem (>300ms) — worth addressing proactively before it worsens.",
        "how_to_fix": "Defer non-critical JS and split large bundles to reduce main-thread blocking time.",
        "how_to_verify": "Re-run a mobile Lighthouse audit and confirm Lab TBT (Mobile) drops below 150ms.",
    },
    "Moderate Lighthouse Performance Mobile (50–89)": {
        "what_it_is": "The Lighthouse mobile Performance score falls in the 50–89 'needs improvement' band.",
        "why_it_matters": "The page is functional but leaves meaningful speed (and ranking) headroom on the table compared to a 90+ score.",
        "how_to_fix": "Work through the top Lighthouse opportunities for this URL — typically image sizing, unused JS/CSS, and caching.",
        "how_to_verify": "Re-run mobile Lighthouse/PSI and confirm the Performance score rises to 90 or above.",
    },
    "Low Lighthouse Best Practices (<80)": {
        "what_it_is": "The Lighthouse Best Practices score is below 80.",
        "why_it_matters": "This category flags security, console-error, and modern-web-standard issues that affect trust and technical quality even if not directly ranking factors.",
        "how_to_fix": "Review the flagged Best Practices audits (e.g. console errors, deprecated APIs, insecure requests) and resolve each.",
        "how_to_verify": "Re-run Lighthouse and confirm the Best Practices score rises above 80.",
    },
    "Large Page Size (>1MB)": {
        "what_it_is": "The total page weight (HTML + assets) exceeds 1MB.",
        "why_it_matters": "Larger pages take longer to load, especially on mobile/slower connections, directly hurting Core Web Vitals and bounce rate.",
        "how_to_fix": "Compress/resize images, minify CSS/JS, and lazy-load below-the-fold assets to cut total page weight.",
        "how_to_verify": "Re-crawl and confirm Page Size (KB) drops below 1024.",
    },
    "Large DOM Size (>1500 nodes)": {
        "what_it_is": "The rendered DOM contains more than 1500 nodes.",
        "why_it_matters": "Very large DOMs slow down style/layout recalculation and JS execution, hurting interactivity metrics like INP.",
        "how_to_fix": "Simplify page markup — remove unnecessary wrapper divs, paginate long lists, and lazy-render off-screen sections.",
        "how_to_verify": "Re-crawl and confirm DOM Size (nodes) drops below 1500.",
        "owner": "Dev",
    },
    "High JS Execution Time (>2000ms)": {
        "what_it_is": "Total JavaScript execution time on the page exceeds 2000ms.",
        "why_it_matters": "Heavy JS execution blocks the main thread, delaying interactivity and hurting INP/TBT metrics.",
        "how_to_fix": "Code-split and lazy-load non-critical JS, remove unused third-party scripts, and defer work until after first paint.",
        "how_to_verify": "Re-run Lighthouse and confirm JS Execution (ms) drops below 2000.",
        "owner": "Dev",
    },
    "Render Blocking Resources": {
        "what_it_is": "One or more CSS/JS resources block initial page rendering.",
        "why_it_matters": "Render-blocking resources delay First Contentful Paint and LCP, directly hurting perceived speed and Core Web Vitals.",
        "how_to_fix": "Inline critical CSS, defer non-critical CSS/JS, and load third-party scripts asynchronously.",
        "how_to_verify": "Re-run Lighthouse and confirm Has Render Blocking Resources reads false.",
        "owner": "Dev",
    },
    "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)": {
        "what_it_is": "Origin-level (whole-site) CrUX field LCP exceeds the critical threshold; per-URL field data wasn't available for this run.",
        "why_it_matters": "Origin-level data suggests a site-wide LCP problem, but without a PSI API key the audit can't pinpoint which specific URLs are worst affected.",
        "how_to_fix": "Configure a PSI API key to get URL-level field data, and in parallel address common site-wide LCP causes (hosting, hero image delivery, render-blocking assets).",
        "how_to_verify": "Re-run with a PSI API key configured and check per-URL CWV LCP (s) values populate.",
        "owner": "Dev",
    },
    "Origin CrUX INP Above 200ms (per-URL data unavailable)": {
        "what_it_is": "Origin-level (whole-site) CrUX field INP exceeds the warning threshold; per-URL field data wasn't available for this run.",
        "why_it_matters": "Origin-level data suggests a site-wide responsiveness problem, but without a PSI API key the audit can't pinpoint which specific URLs are worst affected.",
        "how_to_fix": "Configure a PSI API key to get URL-level field data, and in parallel reduce site-wide JS execution/main-thread blocking.",
        "how_to_verify": "Re-run with a PSI API key configured and check per-URL CWV INP (ms) values populate.",
        "owner": "Dev",
    },
    "Low Regional Authority": {
        "what_it_is": "The page's estimated regional authority score is below 30.",
        "why_it_matters": "Low regional authority suggests the page has weak local/regional relevance signals, which can limit visibility for geo-targeted queries.",
        "how_to_fix": "Add region-specific content, local business schema/NAP details, and build regionally-relevant internal/external links.",
        "how_to_verify": "Re-check Regional Authority Score on Main after the changes and next crawl.",
        "owner": "Copy Writer",
    },
    "llms.txt Missing": {
        "what_it_is": "No llms.txt file was found at the site root.",
        "why_it_matters": "llms.txt is an emerging convention that gives AI/LLM crawlers a curated guide to the site's key content — its absence is a minor missed opportunity, not a hard requirement.",
        "how_to_fix": "Publish an llms.txt file at the site root summarising key pages/sections for LLM consumption.",
        "how_to_verify": "Fetch /llms.txt and confirm it returns 200 with the expected content.",
        "owner": "Dev",
    },
    "AI Crawlers Not Explicitly Allowed": {
        "what_it_is": "robots.txt does not explicitly allow the major AI crawlers (GPTBot, ClaudeBot, PerplexityBot).",
        "why_it_matters": "While not blocked, the absence of an explicit Allow can be ambiguous for some bots and misses a clear signal of openness to AI answer-engine inclusion.",
        "how_to_fix": "Add explicit User-agent/Allow entries for GPTBot, ClaudeBot, and PerplexityBot in robots.txt.",
        "how_to_verify": "Fetch /robots.txt and confirm explicit Allow rules exist for each AI crawler.",
        "owner": "Dev",
    },
}


def root_cause_and_fix(issue_name: str) -> tuple[str, str]:
    entry = ISSUE_CONTENT.get(issue_name)
    if entry is None:
        return ("Template/technical implementation quality issue.", "Apply fix based on issue type and re-run audit.")
    return (entry["what_it_is"], entry["how_to_fix"])


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
        # Redirect issues
        "302 Redirect (Temporary)",
        "Mixed 301/302 Chain",
        "Redirect Loop",
        "Canonical Chain (>1 hop)",
        "Canonical Loop",
        "Canonical Points to Broken URL",
        "Canonical Points to Redirect",
        # Core Web Vitals / Lab performance
        "CWV LCP Above 4.0s (Field Data)",
        "CWV CLS Above 0.1 (Field Data)",
        "CWV INP Above 200ms (Field Data)",
        "Lab LCP Above 4.0s (Mobile)",
        "Lab LCP 2.5s–4.0s (Mobile)",
        "Lab TBT Above 300ms (Mobile)",
        "Lab TBT 150ms–300ms (Mobile)",
        "Lab CLS Above 0.1 (Mobile)",
        # Lighthouse / page quality
        "Low Lighthouse Performance Mobile (<50)",
        "Low Lighthouse Accessibility (<80)",
        "Low Lighthouse Best Practices (<80)",
        "Moderate Lighthouse Performance Mobile (50–89)",
        # Page weight / scripts
        "High Third-Party Script Count (>10)",
        "Third-Party Scripts Blocking Render",
        "Large Page Size (>1MB)",
        "Large DOM Size (>1500 nodes)",
        "High JS Execution Time (>2000ms)",
        "Render Blocking Resources",
        # Origin CrUX (site-level)
        "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)",
        "Origin CrUX INP Above 200ms (per-URL data unavailable)",
    }
    server_host_issues = {
        "Non-200 Status",
        "Robots.txt Disallow Root",
        "No Compression Header",
        "No Cache-Control Header",
        "No ETag Header",
        "Lab TTFB Above 600ms",
    }

    if issue in copy_writer_issues:
        return "Copy Writer"
    if issue in server_host_issues:
        return "Server/Host"
    if issue in dev_issues:
        return "Dev"
    return DEFAULT_OWNER_BY_SEVERITY.get(str(severity or ""), "Dev")


def effort_for_issue(issue_name: str, severity: str, affected_count: int = 0) -> str:
    """Return effort band S/M/L based on issue class rather than severity alone."""
    _config_fixes = {
        "Non-200 Status", "Robots.txt Disallow Root", "302 Redirect (Temporary)",
        "Mixed 301/302 Chain", "No Compression Header", "No Cache-Control Header",
        "No ETag Header", "Redirect Chains", "Canonical Missing",
        "Canonical Points Elsewhere", "Canonical Loop", "Canonical Chain (>1 hop)",
    }
    _performance_fixes = {
        "CWV LCP Above 4.0s (Field Data)", "CWV CLS Above 0.1 (Field Data)",
        "CWV INP Above 200ms (Field Data)", "Lab LCP Above 4.0s (Mobile)",
        "Lab LCP 2.5s–4.0s (Mobile)", "Lab TBT Above 300ms (Mobile)",
        "Lab TBT 150ms–300ms (Mobile)", "Lab CLS Above 0.1 (Mobile)",
        "Low Lighthouse Performance Mobile (<50)", "Low Lighthouse Accessibility (<80)",
        "Low Lighthouse Best Practices (<80)", "Moderate Lighthouse Performance Mobile (50–89)",
        "High Third-Party Script Count (>10)", "Third-Party Scripts Blocking Render",
        "Large DOM Size (>1500 nodes)", "High JS Execution Time (>2000ms)",
        "Render Blocking Resources",
        "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)",
        "Origin CrUX INP Above 200ms (per-URL data unavailable)",
    }
    _schema_fixes = {
        "Missing FAQ/QA Schema", "No Schema Markup", "Schema Parse Error",
        "Schema Validation Errors", "Missing Event Schema", "Missing Article Schema",
    }
    _large_page_issues = {
        "Large Page Size (>1MB)",
    }
    _per_page_content = {
        "Missing Title", "Missing Meta Description", "Missing H1",
        "No 40-60 Word Answer Paragraphs", "No Question Headings",
        "Thin Content", "Thin Content (<200 words)", "Low AEO Readiness Score",
        "Low Image Alt Coverage", "Missing OG Title", "Missing OG Description",
        "Missing OG Image", "No Answer-Friendly Structure",
    }

    if issue_name in _config_fixes:
        return "S"
    if issue_name in _performance_fixes:
        return "M"
    if issue_name in _schema_fixes:
        return "M"
    if issue_name in _large_page_issues:
        return "M"
    if issue_name in _per_page_content:
        if affected_count > 50:
            return "L"
        if affected_count > 10:
            return "M"
        return "S"
    return DEFAULT_EFFORT_BY_SEVERITY.get(severity, "S")


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
