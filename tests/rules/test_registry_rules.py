"""Verify summary registry rules fire on controlled trigger rows (D5)."""
from __future__ import annotations

import pytest

from hype_frog.core.status_codes import STATUS_TIMEOUT
from hype_frog.rules.registry import IssueRule, get_summary_rules

_BASE_URL = "https://example.com/page"


def _row(values: dict[str, object] | None = None) -> dict[str, object]:
    row: dict[str, object] = {"URL": _BASE_URL}
    if values:
        row.update(values)
    return row


# (rule_name, positive_row, negative_row)
RULE_TRIGGER_CASES: list[tuple[str, dict[str, object], dict[str, object]]] = [
    ("Non-200 Status", _row({"Status Code": 404}), _row({"Status Code": 200})),
    ("Non-200 Status", _row({"Status Code": STATUS_TIMEOUT}), _row({"Status Code": 200})),
    ("Missing Title", _row({"Title Missing": True}), _row({"Title Missing": False})),
    (
        "Noindex Directive",
        _row({"Indexability Reason": "noindex in meta robots"}),
        _row({"Indexability Reason": "indexable"}),
    ),
    (
        "Canonical Points Elsewhere",
        _row({"Canonical Type": "cross-canonical"}),
        _row({"Canonical Type": "self"}),
    ),
    (
        "Robots.txt Disallow Root",
        _row({"Robots.txt Disallow /": True}),
        _row({"Robots.txt Disallow /": False}),
    ),
    (
        "CWV LCP Above 4.0s (Field Data)",
        _row({"CrUX Level": "URL", "CWV LCP (s)": 4.5}),
        _row({"CrUX Level": "URL", "CWV LCP (s)": 2.0}),
    ),
    (
        "Lab LCP Above 4.0s (Mobile)",
        _row({"Lab LCP (Mobile) (s)": 4.2}),
        _row({"Lab LCP (Mobile) (s)": 2.0}),
    ),
    (
        "Broken Internal Links",
        _row({"Broken Internal Links Count": 2}),
        _row({"Broken Internal Links Count": 0}),
    ),
    (
        "Redirect Chains",
        _row({"Redirect Chain Length": 3}),
        _row({"Redirect Chain Length": 1}),
    ),
    (
        "302 Redirect (Temporary)",
        _row({"Has 302 in Chain": True}),
        _row({"Has 302 in Chain": False}),
    ),
    (
        "Mixed 301/302 Chain",
        _row({"Has Mixed Redirect Types": True}),
        _row({"Has Mixed Redirect Types": False}),
    ),
    (
        "Redirect Loop",
        _row({"Redirect Loop Flag": True}),
        _row({"Redirect Loop Flag": False}),
    ),
    (
        "Canonical Chain (>1 hop)",
        _row({"Canonical Chain Depth": 2}),
        _row({"Canonical Chain Depth": 1}),
    ),
    (
        "Canonical Loop",
        _row({"Canonical Loop Detected": True}),
        _row({"Canonical Loop Detected": False}),
    ),
    (
        "Canonical Points to Broken URL",
        _row({"Canonical Points to Non-200": True}),
        _row({"Canonical Points to Non-200": False}),
    ),
    (
        "Canonical Points to Redirect",
        _row({"Canonical Points to Redirect": True}),
        _row({"Canonical Points to Redirect": False}),
    ),
    (
        "Not Indexed by Google",
        _row({"GSC Index Status": "NOT_INDEXED"}),
        _row({"GSC Index Status": "INDEXED"}),
    ),
    (
        "Not Crawled in >30 Days",
        _row({"Days Since Last Crawl": 45}),
        _row({"Days Since Last Crawl": 10}),
    ),
    (
        "GSC Mobile Usability Issue",
        _row({"GSC Mobile Usability": "NOT_MOBILE_FRIENDLY"}),
        _row({"GSC Mobile Usability": "MOBILE_FRIENDLY"}),
    ),
    (
        "GSC Rich Result Error",
        _row({"GSC Rich Result Status": "INVALID"}),
        _row({"GSC Rich Result Status": "VALID"}),
    ),
    (
        "Blocked by Googlebot",
        _row({"Robots.txt: Googlebot": "Disallow"}),
        _row({"Robots.txt: Googlebot": "Allow"}),
    ),
    (
        "Blocked by Bingbot",
        _row({"Robots.txt: Bingbot": "Disallow"}),
        _row({"Robots.txt: Bingbot": "Allow"}),
    ),
    (
        "In Sitemap but Blocked by Googlebot",
        _row({"Found via Sitemap": True, "Robots.txt: Googlebot": "Disallow"}),
        _row({"Found via Sitemap": True, "Robots.txt: Googlebot": "Allow"}),
    ),
    (
        "AI Crawlers: GPTBot Blocked",
        _row({"Robots.txt: GPTBot": "Disallow"}),
        _row({"Robots.txt: GPTBot": "Allow"}),
    ),
    (
        "AI Crawlers: ClaudeBot Blocked",
        _row({"Robots.txt: ClaudeBot": "Disallow"}),
        _row({"Robots.txt: ClaudeBot": "Allow"}),
    ),
    (
        "Broken Images",
        _row({"Broken Image Count": 1}),
        _row({"Broken Image Count": 0}),
    ),
    (
        "High Broken Image Count (>3)",
        _row({"Broken Image Count": 4}),
        _row({"Broken Image Count": 1}),
    ),
    (
        "High Third-Party Script Count (>10)",
        _row({"Third Party Script Count": 12}),
        _row({"Third Party Script Count": 2}),
    ),
    (
        "Third-Party Scripts Blocking Render",
        _row({"Third Party JS Blocking": True}),
        _row({"Third Party JS Blocking": False}),
    ),
    (
        "Under-Linked Priority Page",
        _row({"Business Risk Score": 40, "Inbound Internal Link Count": 1}),
        _row({"Business Risk Score": 40, "Inbound Internal Link Count": 5}),
    ),
    (
        "Generic Anchor Dominance",
        _row({"Generic Anchor Dominance": True}),
        _row({"Generic Anchor Dominance": False}),
    ),
    (
        "No Consent Manager Detected",
        _row({"Has Consent Manager": False}),
        _row({"Has Consent Manager": True}),
    ),
    (
        "Missing Meta Description",
        _row({"Meta Description Missing": True}),
        _row({"Meta Description Missing": False}),
    ),
    ("Missing H1", _row({"Missing H1 Flag": True}), _row({"Missing H1 Flag": False})),
    ("Multiple H1", _row({"Multiple H1 Flag": True}), _row({"Multiple H1 Flag": False})),
    (
        "CWV CLS Above 0.1 (Field Data)",
        _row({"CrUX Level": "URL", "CWV CLS": 0.15}),
        _row({"CrUX Level": "URL", "CWV CLS": 0.05}),
    ),
    (
        "CWV INP Above 200ms (Field Data)",
        _row({"CrUX Level": "URL", "CWV INP (ms)": 250}),
        _row({"CrUX Level": "URL", "CWV INP (ms)": 150}),
    ),
    (
        "Lab LCP 2.5s–4.0s (Mobile)",
        _row({"Lab LCP (Mobile) (s)": 3.0}),
        _row({"Lab LCP (Mobile) (s)": 2.0}),
    ),
    (
        "Lab TBT Above 300ms (Mobile)",
        _row({"Lab TBT (Mobile) (ms)": 350}),
        _row({"Lab TBT (Mobile) (ms)": 100}),
    ),
    (
        "Lab CLS Above 0.1 (Mobile)",
        _row({"Lab CLS (Mobile)": 0.12}),
        _row({"Lab CLS (Mobile)": 0.05}),
    ),
    (
        "Low Lighthouse Performance Mobile (<50)",
        _row({"Lighthouse Performance (Mobile)": 40}),
        _row({"Lighthouse Performance (Mobile)": 75}),
    ),
    (
        "Low Lighthouse Accessibility (<80)",
        _row({"Lighthouse Accessibility (Mobile)": 70}),
        _row({"Lighthouse Accessibility (Mobile)": 90}),
    ),
    (
        "Lab TTFB Above 600ms",
        _row({"Lab TTFB (Mobile) (ms)": 700}),
        _row({"Lab TTFB (Mobile) (ms)": 400}),
    ),
    (
        "Missing FAQ/QA Schema",
        _row({"QAPage/FAQ Schema Present": False, "Question Heading Count": 3}),
        _row({"QAPage/FAQ Schema Present": True, "Question Heading Count": 3}),
    ),
    ("Deep URL (>3 clicks)", _row({"Click Depth": 5}), _row({"Click Depth": 2})),
    (
        "Low Image Alt Coverage",
        _row({"Image Alt Coverage (%)": 50}),
        _row({"Image Alt Coverage (%)": 95}),
    ),
    (
        "Mixed Content",
        _row({"Mixed Content Detected": True}),
        _row({"Mixed Content Detected": False}),
    ),
    (
        "Canonical Missing",
        _row({"Canonical Type": "missing"}),
        _row({"Canonical Type": "self"}),
    ),
    (
        "Hreflang Without Reciprocity",
        _row(
            {
                "Hreflang Present": True,
                "Hreflang Reciprocal Status": "Missing Return Link",
            }
        ),
        _row(
            {
                "Hreflang Present": True,
                "Hreflang Reciprocal Status": "Valid",
            }
        ),
    ),
    (
        "Invalid Hreflang Language Code",
        _row({"Hreflang Present": True, "Hreflang Code Valid": False}),
        _row({"Hreflang Present": True, "Hreflang Code Valid": True}),
    ),
    ("Uses URL Parameters", _row({"Param URL Flag": True}), _row({"Param URL Flag": False})),
    (
        "Generic Anchor Text Present",
        _row({"Generic Anchor Text Count": 2}),
        _row({"Generic Anchor Text Count": 0}),
    ),
    (
        "Image Filename Quality Issues",
        _row({"Image Filename Quality Issues": 1}),
        _row({"Image Filename Quality Issues": 0}),
    ),
    (
        "No Compression Header",
        _row({"Compression Enabled": False}),
        _row({"Compression Enabled": True}),
    ),
    (
        "No Cache-Control Header",
        _row({"Cache-Control": None}),
        _row({"Cache-Control": "max-age=3600"}),
    ),
    ("No ETag Header", _row({"ETag": None}), _row({"ETag": '"abc123"'})),
    ("Thin Content", _row({"Thin Content Flag": True}), _row({"Thin Content Flag": False})),
    (
        "Render Fallback (raw HTTP)",
        _row({"Extraction Source Fallback": True}),
        _row({"Extraction Source Fallback": False}),
    ),
    (
        "Thin Content (<200 words)",
        _row({"Is Thin Content": True}),
        _row({"Is Thin Content": False}),
    ),
    (
        "Near-Duplicate Content",
        _row({"Is Near Duplicate": True}),
        _row({"Is Near Duplicate": False}),
    ),
    (
        "Draft or Test Page (URL pattern)",
        _row({"Is Draft or Test Page": True}),
        _row({"Is Draft or Test Page": False}),
    ),
    (
        "No Schema Markup",
        _row({"Schema Present": False}),
        _row({"Schema Present": True}),
    ),
    (
        "Schema Parse Error",
        _row({"Schema Parse Errors": 1}),
        _row({"Schema Parse Errors": 0}),
    ),
    (
        "Schema Validation Errors",
        _row({"Schema Error Count": 2}),
        _row({"Schema Error Count": 0}),
    ),
    (
        "Schema Validation Warnings",
        _row({"Schema Warning Count": 1, "Schema Error Count": 0}),
        _row({"Schema Warning Count": 0, "Schema Error Count": 0}),
    ),
    (
        "Missing Event Schema",
        _row({"URL": "https://example.com/conference-2026", "Schema Present": False}),
        _row({"URL": "https://example.com/conference-2026", "Schema Present": True}),
    ),
    (
        "Missing Article Schema",
        _row({"URL": "https://example.com/blog/post", "Schema Present": False}),
        _row({"URL": "https://example.com/blog/post", "Schema Present": True}),
    ),
    (
        "Low E-E-A-T Signal Score (<3)",
        _row({"E-E-A-T Signal Score": 1}),
        _row({"E-E-A-T Signal Score": 8}),
    ),
    (
        "No Author Attribution",
        _row(
            {
                "Schema Author Name": None,
                "Meta Author": None,
                "Has Byline Element": False,
            }
        ),
        _row(
            {
                "Schema Author Name": "Jane",
                "Meta Author": None,
                "Has Byline Element": False,
            }
        ),
    ),
    (
        "No Publication Date",
        _row({"OG Published Time": None, "Schema Published Date": None}),
        _row({"OG Published Time": "2025-01-01", "Schema Published Date": None}),
    ),
    (
        "No Privacy Policy Link",
        _row({"Has Privacy Policy Link": False}),
        _row({"Has Privacy Policy Link": True}),
    ),
    (
        "No Terms Link",
        _row({"Has Terms Link": False}),
        _row({"Has Terms Link": True}),
    ),
    (
        "Stale Content (>2 years)",
        _row({"Content Age (days)": 800}),
        _row({"Content Age (days)": 100}),
    ),
    (
        "Ageing Content (1-2 years)",
        _row({"Content Age (days)": 400}),
        _row({"Content Age (days)": 100}),
    ),
    (
        "No Publication or Modification Date",
        _row({"Freshness Status": "Unknown"}),
        _row({"Freshness Status": "Fresh (< 3 months)"}),
    ),
    (
        "Low AEO Readiness Score",
        _row({"AEO Readiness Score": 50}),
        _row({"AEO Readiness Score": 85}),
    ),
    (
        "No Question Headings",
        _row({"Question Heading Count": 0}),
        _row({"Question Heading Count": 2}),
    ),
    (
        "No Answer-Friendly Structure",
        _row({"List/Table Answer Signal": False}),
        _row({"List/Table Answer Signal": True}),
    ),
    (
        "No 40-60 Word Answer Paragraphs",
        _row({"Paragraphs 40-60 Words Count": 0}),
        _row({"Paragraphs 40-60 Words Count": 2}),
    ),
    (
        "Lab TBT 150ms–300ms (Mobile)",
        _row({"Lab TBT (Mobile) (ms)": 200}),
        _row({"Lab TBT (Mobile) (ms)": 100}),
    ),
    (
        "Moderate Lighthouse Performance Mobile (50–89)",
        _row({"Lighthouse Performance (Mobile)": 65}),
        _row({"Lighthouse Performance (Mobile)": 95}),
    ),
    (
        "Low Lighthouse Best Practices (<80)",
        _row({"Lighthouse Best Practices (Mobile)": 70}),
        _row({"Lighthouse Best Practices (Mobile)": 90}),
    ),
    (
        "Large Page Size (>1MB)",
        _row({"Page Size (KB)": 1100}),
        _row({"Page Size (KB)": 500}),
    ),
    (
        "Large DOM Size (>1500 nodes)",
        _row({"DOM Size (nodes)": 1600}),
        _row({"DOM Size (nodes)": 800}),
    ),
    (
        "High JS Execution Time (>2000ms)",
        _row({"JS Execution (ms)": 2500}),
        _row({"JS Execution (ms)": 500}),
    ),
    (
        "Render Blocking Resources",
        _row({"Has Render Blocking Resources": True}),
        _row({"Has Render Blocking Resources": False}),
    ),
    (
        "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)",
        _row({"CrUX Level": "Origin", "Origin CrUX LCP (s)": 4.5}),
        _row({"CrUX Level": "Origin", "Origin CrUX LCP (s)": 2.0}),
    ),
    (
        "Origin CrUX INP Above 200ms (per-URL data unavailable)",
        _row({"CrUX Level": "Origin", "Origin CrUX INP (ms)": 250}),
        _row({"CrUX Level": "Origin", "Origin CrUX INP (ms)": 150}),
    ),
    (
        "Low Regional Authority",
        _row({"Regional Authority Score": 10}),
        _row({"Regional Authority Score": 50}),
    ),
    (
        "llms.txt Missing",
        _row({"llms.txt Present": False}),
        _row({"llms.txt Present": True}),
    ),
    (
        "Missing OG Title",
        _row({"OG Title": None}),
        _row({"OG Title": "Share title"}),
    ),
    (
        "Missing OG Description",
        _row({"OG Description": None}),
        _row({"OG Description": "Share description"}),
    ),
    (
        "Missing OG Image",
        _row({"OG Image URL": None, "OG-Image": None}),
        _row({"OG Image URL": "https://example.com/og.jpg"}),
    ),
    (
        "OG Image Broken (non-200)",
        _row({"OG Image OK": False}),
        _row({"OG Image OK": True}),
    ),
    (
        "OG URL Mismatch",
        _row({"OG URL Mismatch": True}),
        _row({"OG URL Mismatch": False}),
    ),
    (
        "OG Type Not Set",
        _row({"OG Type": None}),
        _row({"OG Type": "website"}),
    ),
    (
        "Missing Twitter Card",
        _row({"Twitter Card Type": None}),
        _row({"Twitter Card Type": "summary_large_image"}),
    ),
    (
        "OG Image Wrong Dimensions",
        _row({"OG Image Width": 800, "OG Image Height": 400, "OG Image Dimensions OK": False}),
        _row({"OG Image Width": 1200, "OG Image Height": 630, "OG Image Dimensions OK": True}),
    ),
    (
        "AI Crawlers Not Explicitly Allowed",
        _row({"AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": False}),
        _row({"AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": True}),
    ),
]


@pytest.fixture(scope="module")
def rules_by_name() -> dict[str, IssueRule]:
    return {rule.name: rule for rule in get_summary_rules()}


def test_all_summary_rules_have_unique_names() -> None:
    names = [rule.name for rule in get_summary_rules()]
    assert len(names) == len(set(names))


def test_rule_trigger_matrix_covers_every_rule(rules_by_name: dict[str, IssueRule]) -> None:
    covered = {case[0] for case in RULE_TRIGGER_CASES}
    missing = set(rules_by_name) - covered
    assert not missing, f"Missing trigger cases for: {sorted(missing)}"


@pytest.mark.parametrize(
    ("rule_name", "positive_row", "negative_row"),
    RULE_TRIGGER_CASES,
    ids=[f"{case[0]}-{idx}" for idx, case in enumerate(RULE_TRIGGER_CASES)],
)
def test_rule_fires_on_positive_not_negative(
    rules_by_name: dict[str, IssueRule],
    rule_name: str,
    positive_row: dict[str, object],
    negative_row: dict[str, object],
) -> None:
    rule = rules_by_name[rule_name]
    assert rule.fn(positive_row) is True, f"{rule_name} should fire on positive row"
    assert rule.fn(negative_row) is False, f"{rule_name} should not fire on negative row"


def test_all_rules_tolerate_minimal_row(rules_by_name: dict[str, IssueRule]) -> None:
    minimal = _row({"Status Code": 200, "Extraction State": "complete"})
    for rule in rules_by_name.values():
        try:
            rule.fn(minimal)
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(f"Rule {rule.name!r} raised on minimal row: {exc}")
