from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, TypedDict

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class MainRow(TypedDict, total=False):
    URL: str
    Status_Code: Any
    Load_Time_s: float
    Indexability: str
    Title: str | None
    Title_Length: int
    Meta_Description: str | None
    Meta_Desc_Length: int
    Word_Count_Body: int
    OG_Image: str | None
    Has_Valid_JSON_LD: bool
    SEO_Health_Score: float
    Severity_Badge: str
    Health_Icon: str


class LinkDetail(TypedDict):
    Source_URL: str
    Target_URL: str
    Internal: bool
    Nofollow: bool
    Anchor_Text: str


class AEOSnippet(TypedDict):
    heading: str
    snippet: str
    word_count: int


class ExtraRow(TypedDict, total=False):
    URL: str
    Status_Code: Any
    Final_URL: str | None
    Canonical_URL: str | None
    Canonical_Type: str | None
    Hreflang_Present: bool
    Hreflang_Reciprocal_Check: bool | None
    Broken_Internal_Links_Count: int
    Unresolved_Internal_Links_Count: int
    Internal_Links_List: list[str]
    Internal_Links_List_Full: list[str]
    Link_Details: list[LinkDetail]
    Matched_Issues: str | None
    Severity_Badge: str
    SEO_Health_Score: float
    Health_Icon: str
    aeo_snippets: list[AEOSnippet]


class CrawlResult(TypedDict):
    main: dict[str, Any]
    extra: dict[str, Any]


class CheckpointPayload(TypedDict):
    saved_at: str
    completed: int
    total: int
    completed_urls: list[str]
    remaining_urls: list[str]
    results: list[CrawlResult]


class CrawlResultModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    main: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class PageRowMetricsModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        validate_assignment=True,
    )

    url: str = Field(default="", alias="URL")
    desktop_psi_score: int | None = Field(default=None, alias="Desktop PSI Score")
    mobile_psi_score: int | None = Field(default=None, alias="Mobile PSI Score")
    mobile_lcp_s: float | None = Field(default=None, alias="Mobile LCP (s)")
    cwv_lcp_s: float | None = Field(default=None, alias="CWV LCP (s)")
    gsc_clicks: float | None = Field(default=None, alias="GSC Clicks")
    gsc_impressions: float | None = Field(default=None, alias="GSC Impressions")

    @field_validator(
        "desktop_psi_score",
        "mobile_psi_score",
        "mobile_lcp_s",
        "cwv_lcp_s",
        mode="before",
    )
    @classmethod
    def _coerce_optional_psi_metrics(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric

    @field_validator("gsc_clicks", "gsc_impressions", mode="before")
    @classmethod
    def _coerce_gsc_numeric_defaults(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric


def harden_page_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    def _safe_float(raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return value

    try:
        validated = PageRowMetricsModel.model_validate(row)
    except ValidationError:
        fallback = dict(row)
        for psi_key in ("Desktop PSI Score", "Mobile PSI Score"):
            raw = fallback.get(psi_key)
            if raw is None or str(raw).strip() == "":
                fallback[psi_key] = None
            else:
                fallback[psi_key] = int(_safe_float(raw))
        for lcp_key in ("Mobile LCP (s)", "CWV LCP (s)"):
            raw = fallback.get(lcp_key)
            if raw is None or str(raw).strip() == "":
                fallback[lcp_key] = None
            else:
                fallback[lcp_key] = _safe_float(raw)
        for gsc_key in ("GSC Clicks", "GSC Impressions"):
            raw = fallback.get(gsc_key)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                fallback[gsc_key] = None
            else:
                fallback[gsc_key] = _safe_float(raw)
        return fallback
    return validated.model_dump(by_alias=True, exclude_none=False)


MAIN_ROW_DEFAULTS: dict[str, Any] = {
    "URL": "",
    "Extraction State": "skipped",
    "Extraction Source": "raw_http",
    "Extraction Source Fallback": False,
    "Status Code": None,
    "Load Time (s)": None,
    "Indexability": "Indexable",
    "Title": None,
    "Title Length": 0,
    "Meta Description": None,
    "Meta Desc Length": 0,
    "Word Count (Body)": 0,
    "OG-Image": None,
    "Has Valid JSON-LD": False,
    "Meta Keywords": None,
    "H1 Content": None,
    "H1 Length": 0,
    "H2 Content": None,
    "H2 Length": 0,
    "H3 Content": None,
    "H3 Length": 0,
    "H4 Content": None,
    "H4 Length": 0,
    "H5 Content": None,
    "H5 Length": 0,
    "H6 Content": None,
    "H6 Length": 0,
    "SEO Health Score": 0.0,
    "Severity Badge": None,
    "Health Icon": None,
    "CWV LCP (s)": None,
    "CWV CLS": None,
    "CWV INP (ms)": None,
    "CWV FCP (ms)": None,
    "CWV TTFB (ms)": None,
    "CrUX Level": None,
    "CrUX LCP Category": None,
    "CrUX CLS Category": None,
    "CrUX INP Category": None,
    "Origin CrUX LCP (s)": None,
    "Origin CrUX CLS": None,
    "Origin CrUX INP (ms)": None,
    "Field vs Lab": "Lab",
    "CWV Data Source": "None",
    "Regional Authority Score": 0,
    "PSI Data Status": "Not measured",
    "Desktop PSI Score": None,
    "Mobile PSI Score": None,
    "Mobile LCP (s)": None,
    "Mobile CLS": None,
    "Mobile TTFB (s)": None,
    "GSC Clicks": 0.0,
    "GSC Impressions": 0.0,
    "GSC CTR": 0.0,
    "GSC Avg Position": 0.0,
    "GSC Data Freshness": None,
    "GSC Coverage Note": None,
    "Click Depth": None,
    "Orphan Pages": False,
    "Reachable from Homepage": False,
    "Internal PageRank": 0.0,
    "Found via Sitemap": False,
    "Found via Crawl": False,
    "Discovery Source": "Crawl",
    "Discovered On URL": "",
    "Discovery Rank": None,
    "Technical Health": 0.0,
    "Copy Score": 0.0,
    "SEO Score": 0.0,
    "Action Needed": "No",
    # Top 8 expansion — mirrored on Main after enrichment merge
    "Schema Present": False,
    "Schema Valid": False,
    "Schema Types Found": None,
    "Schema Types Valid": None,
    "Schema Types With Errors": None,
    "Schema Error Count": 0,
    "Schema Warning Count": 0,
    "Schema Parse Error Detail": None,
    "Schema Validation Summary": None,
    "Schema Issues Detail": None,
    "E-E-A-T Signal Score": 0,
    "Schema Author Name": None,
    "Meta Author": None,
    "Has Byline Element": False,
    "Byline Text": None,
    "Schema Published Date": None,
    "Schema Modified Date": None,
    "OG Published Time": None,
    "OG Modified Time": None,
    "Has Time Element": False,
    "Has Privacy Policy Link": False,
    "Has Terms Link": False,
    "Has Social Links": False,
    "Social Profile Link Count": 0,
    "Has Phone Number": False,
    "Has Email Address": False,
    "Links to About Page": False,
    "Has Authority External Links": False,
    "Is Thin Content": False,
    "Is Near Duplicate": False,
    "Near Duplicate Of": None,
    "Content Similarity Score": None,
    "Is Draft or Test Page": False,
    "Draft Signal": None,
    "Published Date": None,
    "Last Modified Date": None,
    "HTTP Last-Modified": None,
    "Content Age (days)": None,
    "Freshness Status": None,
    # A1 — Open Graph & Twitter Card audit
    "OG Title": None,
    "OG Description": None,
    "OG Type": None,
    "OG URL": None,
    "OG Image URL": None,
    "OG Image Width": None,
    "OG Image Height": None,
    "OG Image OK": None,
    "OG Image Dimensions OK": None,
    "OG URL Mismatch": False,
    "Twitter Card Type": None,
    "Twitter Title": None,
    "Twitter Description": None,
    "Twitter Image": None,
    "OG Completeness Score": 0,
    "Open Graph Complete": False,
    # A3 — redirect chain mapping
    "Final URL": None,
    "Redirect Chain": None,
    "Redirect Chain Length": 0,
    "Redirect Chain Hops": None,
    "Has 302 in Chain": False,
    "Has Mixed Redirect Types": False,
    "Redirect Loop Flag": False,
    # B1 — canonical chain tracing
    "Canonical Chain Depth": 0,
    "Canonical Chain Final": None,
    "Canonical Chain": None,
    "Canonical Loop Detected": False,
    "Canonical Points to Redirect": False,
    "Canonical Points to Non-200": False,
    # B4 — GSC URL Inspection (Main merge when enabled)
    "GSC Index Status": None,
    "GSC Last Crawl Date": None,
    "GSC Mobile Usability": None,
    "GSC Rich Result Status": None,
    "GSC Coverage Reason": None,
    "Days Since Last Crawl": None,
    # A5 — robots.txt per-URL mapping
    "Robots.txt: Googlebot": None,
    "Robots.txt: Bingbot": None,
    "Robots.txt: GPTBot": None,
    "Robots.txt: ClaudeBot": None,
    "Robots.txt: PerplexityBot": None,
    "Crawl-Delay Applies": False,
}


EXTRA_ROW_DEFAULTS: dict[str, Any] = {
    "URL": "",
    "Extraction State": "skipped",
    "Extraction Source": "raw_http",
    "Extraction Source Fallback": False,
    "Status Code": None,
    "Final URL": None,
    "Protocol": None,
    "Redirect Chain Length": 0,
    "Redirect Target": None,
    "Redirect Hops": None,
    "Redirect Chain": None,
    "Redirect Chain Hops": None,
    "Has 302 in Chain": False,
    "Has Mixed Redirect Types": False,
    "Redirect Loop Flag": False,
    "Redirect SEO Risk": None,
    # B1 — canonical chain tracing
    "Canonical Chain Depth": 0,
    "Canonical Chain Final": None,
    "Canonical Chain": None,
    "Canonical Loop Detected": False,
    "Canonical Points to Redirect": False,
    "Canonical Points to Non-200": False,
    # B4 — GSC URL Inspection (populated when --gsc-url-inspection is enabled)
    "GSC Index Status": None,
    "GSC Last Crawl Date": None,
    "GSC Mobile Usability": None,
    "GSC Rich Result Status": None,
    "GSC Coverage Reason": None,
    "Days Since Last Crawl": None,
    "HTTP->HTTPS Redirect": False,
    "Status Class": None,
    "TTFB (ms)": None,
    "Total Request Time (ms)": None,
    "Content-Type": None,
    # Dead-letter / short-circuit reasons (machine-readable), e.g.
    # ``unsupported_mime`` when HTTP 200 returns a non-HTML body.
    "skip_reason": None,
    "HTTP Version": None,
    "HTML Size (KB)": None,
    "Compression Enabled": False,
    "Cache-Control": None,
    "ETag": None,
    "X-Robots-Tag": None,
    "Meta Robots Raw": None,
    "Canonical URL": None,
    "Canonical Matches Final URL": None,
    "Canonical Type": None,
    "Canonical Absolute URL": None,
    "Canonical in Sitemap Match": None,
    "Hreflang Present": False,
    "Hreflang Count": 0,
    "Hreflang Self Reference": False,
    "Hreflang Reciprocal Check": None,
    "Hreflang Canonical Consistency": None,
    "x-default Present": False,
    "Pagination rel=next": False,
    "Pagination rel=prev": False,
    "H1 Count": 0,
    "Primary H1 Content": None,
    "Current H-Tag Structure": None,
    "Current Page Copy Snippet": None,
    "Missing H1 Flag": False,
    "Multiple H1 Flag": False,
    "Thin Content Flag": False,
    "Body Text-to-HTML Ratio": None,
    "Word Count": 0,
    "Word Count (Body)": 0,
    "Word Count Band": None,
    "Sentence Count": 0,
    "Readability (Rough Flesch)": None,
    "Flesch-Kincaid Grade (Est.)": None,
    "AEO Robots AI Bot Coverage": None,
    "Last-Modified": None,
    "Published Date": None,
    "Modified Date": None,
    "Last Updated": None,
    "Change Frequency": None,
    "Priority": None,
    "Internal Links Count": 0,
    "External Links Count": 0,
    "Unique Internal Links Count": 0,
    "Nofollow Internal Links Count": 0,
    "Nofollow External Links Count": 0,
    "Generic Anchor Text Count": 0,
    "Broken Internal Links Count": 0,
    "Unresolved Internal Links Count": 0,
    "JS Dependent": False,
    "Raw Words": 0,
    "Rendered Words": 0,
    "Field LCP (ms)": None,
    "Field CLS": None,
    "Param URL Flag": False,
    "URL Depth": 0,
    "Image Count": 0,
    "Images": None,
    "Images Missing Alt": 0,
    "Image Alt Coverage (%)": None,
    "Image Extension Distribution": None,
    "Likely Large Image Count": 0,
    "Image Filename Quality Issues": 0,
    "Image On Canonical Domain (%)": None,
    "Mixed Content Detected": False,
    "Schema Types Found": None,
    "Schema Types Count": 0,
    "Schema Parse Errors": 0,
    "Open Graph Complete": False,
    "Twitter Card Type": None,
    "OG Title": None,
    "OG Description": None,
    "OG Type": None,
    "OG URL": None,
    "OG Image": None,
    "OG Image URL": None,
    "OG Image Width": None,
    "OG Image Height": None,
    "OG Image OK": None,
    "OG Image Dimensions OK": None,
    "OG URL Mismatch": False,
    "Twitter Title": None,
    "Twitter Description": None,
    "Twitter Image": None,
    "OG Completeness Score": 0,
    "Meta Keywords": None,
    "Strict-Transport-Security": None,
    "Content-Security-Policy": None,
    "X-Content-Type-Options": None,
    "X-Frame-Options": None,
    "Referrer-Policy": None,
    "Permissions-Policy": None,
    "Robots.txt Accessible": None,
    "Sitemap in Robots.txt": None,
    "Robots.txt Crawl-Delay": None,
    "Robots.txt Disallow /": None,
    "Robots.txt: Googlebot": None,
    "Robots.txt: Bingbot": None,
    "Robots.txt: GPTBot": None,
    "Robots.txt: ClaudeBot": None,
    "Robots.txt: PerplexityBot": None,
    "Crawl-Delay Applies": False,
    "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": None,
    "llms.txt Present": None,
    "Title Missing": True,
    "Meta Description Missing": True,
    "Indexability Reason": None,
    "SERP Title Truncation Risk": False,
    "SERP Meta Truncation Risk": False,
    "SERP Title Pixel Approx": 0,
    "SERP Meta Pixel Approx": 0,
    "Inlinks Bucket": None,
    "Important But Underlinked": False,
    "Cannibalization Hint": None,
    "Draft Page Flag": False,
    "Probable Duplicate Flag": False,
    "Duplicate Of URL": None,
    "Content Similarity %": None,
    "Heading Structure Cluster Size": 0,
    "FAQ Section Count": 0,
    "Question Heading Count": 0,
    "HowTo Signal": False,
    "Definition Signal": False,
    "List/Table Answer Signal": False,
    "Paragraphs 40-60 Words Count": 0,
    "Answer Block Detected (First 60 Words)": False,
    "AEO Extractability Score": "Low",
    "Regional Authority Score": 0,
    "Regional Entity Hits": 0,
    "CWV LCP (s)": None,
    "CWV CLS": None,
    "CWV INP (ms)": None,
    "CWV FCP (ms)": None,
    "CWV TTFB (ms)": None,
    "CrUX Level": None,
    "CrUX LCP Category": None,
    "CrUX CLS Category": None,
    "CrUX INP Category": None,
    "Origin CrUX LCP (s)": None,
    "Origin CrUX CLS": None,
    "Origin CrUX INP (ms)": None,
    "Field vs Lab": "Lab",
    "CWV Data Source": "None",
    "Speakable Schema Present": False,
    "QAPage/FAQ Schema Present": False,
    "AEO Readiness Score": 0,
    "AEO Badge": "Needs Work",
    "Action Needed": "No",
    "SEO Health Score": 0.0,
    "Severity Badge": None,
    "Health Icon": None,
    "Critical Issues Count": 0,
    "Warning Issues Count": 0,
    "Observation Issues Count": 0,
    "Matched Issues": None,
    "PSI Data Status": "Not measured",
    "Desktop PSI Score": None,
    "Mobile PSI Score": None,
    "Mobile LCP (s)": None,
    "Mobile CLS": None,
    "Mobile TTFB (s)": None,
    "GSC Clicks": 0.0,
    "GSC Impressions": 0.0,
    "GSC CTR": 0.0,
    "GSC Avg Position": 0.0,
    "GSC Data Freshness": None,
    "GSC Coverage Note": None,
    "GSC Inspection Coverage": None,
    "GSC Inspection Verdict": None,
    "GSC Inspection Coverage State": None,
    "GSC Inspection Google Canonical": None,
    "GSC Inspection Crawl State": None,
    "GSC Inspection Robots State": None,
    "GSC Inspection Last Crawl": None,
    "Click Depth": None,
    "Orphan Pages": False,
    "Reachable from Homepage": False,
    "Internal PageRank": 0.0,
    "Internal Inlinks": 0,
    "Found via Sitemap": False,
    "Found via Crawl": False,
    "Discovery Source": "Crawl",
    "Discovered On URL": "",
    "Discovery Rank": None,
    "Internal Link Statuses": None,
    "Technical Health": 0.0,
    "Copy Score": 0.0,
    "SEO Score": 0.0,
    "Content Cluster ID": None,
    "Owner": None,
    "Sprint": "",
    "Status": "Open",
    "Stable Issue IDs": None,
    "WordPress Post ID": None,
    "Internal Links List Full": [],
    "Internal Links List": [],
    "Link Details": [],
    "Nav Footer Link Details": [],
    "aeo_snippets": [],
    # Sprint 3 — semantic / answer-engine readiness columns. These are
    # additive workbook fields populated by
    # ``hype_frog.extractors.semantic_engine.SemanticAnalyzer``. They
    # coexist with the existing ``AEO Readiness Score`` / ``AEO Badge``
    # columns above without overwriting them.
    "Entity Density (%)": None,
    "Top Entities": None,
    "Citation Candidate Count": 0,
    "Semantic AEO Score": None,
    "Semantic Analysis Mode": "No content",
    # LLM intent classifier. Populated as one of: Informational,
    # Transactional, Navigational, Commercial Investigation, or Unknown.
    # Defaults to Unknown so missing API keys and skipped LLM calls remain
    # explicit in downstream reports instead of disappearing during
    # ExtraRowPayload re-validation.
    "Search Intent": "Unknown",
    # Sprint 4 — structural intelligence, security boolean digests, and
    # internationalisation. ``Crawl Depth`` is the BFS distance from the
    # seed URL (``0`` for the seed); ``Security: HSTS`` / ``Security: CSP``
    # are boolean digests derived from the raw ``Strict-Transport-Security``
    # / ``Content-Security-Policy`` header columns above (those keep their
    # raw header strings, these add a fast pass/fail signal). ``Anchor
    # Text Diversity`` is a "<unique> unique / <total> total" summary over
    # the internal-link anchor pool. ``Hreflang Signals`` is the on-page
    # hreflang cluster as a ``"lang: url; lang: url"`` string — no extra
    # network fetch is performed (Sprint 4 brief constraint).
    "Crawl Depth": 0,
    "Security: HSTS": False,
    "Security: CSP": False,
    "Anchor Text Diversity": None,
    "Hreflang Signals": None,
    # Top 8 expansion — schema validation
    "Schema Present": False,
    "Schema Valid": False,
    "Schema Types Valid": None,
    "Schema Types With Errors": None,
    "Schema Error Count": 0,
    "Schema Warning Count": 0,
    "Schema Parse Error Detail": None,
    "Schema Validation Summary": None,
    "Schema Issues Detail": None,
    # E-E-A-T signals
    "E-E-A-T Signal Score": 0,
    "Schema Author Name": None,
    "Meta Author": None,
    "OG Article Author": None,
    "Has Rel Author Link": False,
    "Rel Author URL": None,
    "Has Byline Element": False,
    "Byline Text": None,
    "Schema Published Date": None,
    "Schema Modified Date": None,
    "OG Published Time": None,
    "OG Modified Time": None,
    "Has Time Element": False,
    "Time Element Datetime": None,
    "Has Privacy Policy Link": False,
    "Has Terms Link": False,
    "Has Social Links": False,
    "Social Profile Link Count": 0,
    "Has Phone Number": False,
    "Has Email Address": False,
    "Links to About Page": False,
    "Has Authority External Links": False,
    "External Link Count": 0,
    # Content similarity / duplication
    "Body Text Excerpt": None,
    "Content Fingerprint": None,
    "Is Thin Content": False,
    "Thin Content Word Count": 0,
    "Is Near Duplicate": False,
    "Near Duplicate Of": None,
    "Content Similarity Score": None,
    "Is Draft or Test Page": False,
    "Draft Signal": None,
    # Content freshness
    "HTTP Last-Modified": None,
    "Last Modified Date": None,
    "Content Age (days)": None,
    "Freshness Status": None,
}

# Enrichment and crawl-derived fields that must survive ExtraRowPayload /
# MainRowPayload whitelist validation (``extra="ignore"``). Without these
# defaults, values set during crawl or post-crawl enrichment are dropped
# before Main merge and dedicated inventory sheets.
ENRICHMENT_PIPELINE_DEFAULTS: dict[str, Any] = {
    # A2 — third-party script inventory (PSI network items)
    "Third Party Script Count": 0,
    "Third Party Scripts": None,
    "Third Party Total Size (KB)": None,
    "Has Google Analytics": False,
    "Has Tag Manager": False,
    "Has Meta Pixel": False,
    "Has Chat Widget": False,
    "Has Consent Manager": False,
    "Third Party JS Blocking": False,
    "PSI Network Items": None,
    "PSI Render Blocking URLs": None,
    # A4 — content image probes and broken/oversized rollups
    "Broken Image Count": 0,
    "Large Image Count": 0,
    "Broken Image URLs": None,
    "Oversized Image URLs": None,
    "Has Broken Images": False,
    "Content Images": None,
    "Has HTML Table": False,
    # A6 — hreflang cluster audit (declared on-page; reciprocity in enrichment)
    "Hreflang Declared Languages": None,
    "Hreflang Alternate URLs": None,
    "Hreflang Reciprocal Status": None,
    "Hreflang Code Valid": True,
    "Hreflang Invalid Codes": None,
    # B2 — internal link equity
    "PageRank Percentile": None,
    "Equity Tier": None,
    "Inbound Internal Link Count": 0,
    "Generic Inbound Anchor %": None,
    "Generic Anchor Dominance": False,
    # B3 — featured snippet opportunities
    "Featured Snippet Type": None,
    "Featured Snippet Readiness": None,
    "GSC Position Opportunity": False,
    "Snippet Restructuring Advice": None,
    # B6 — topical authority / TF-IDF
    "Top TF-IDF Terms": None,
    "Target Keyword": None,
    "Keyword in Title": False,
    "Keyword in H1": False,
    "Keyword in First Paragraph": False,
    "Keyword Density (%)": None,
}

EXTRA_ROW_DEFAULTS.update(ENRICHMENT_PIPELINE_DEFAULTS)

_MAIN_ENRICHMENT_MIRROR_KEYS: tuple[str, ...] = (
    "Third Party Script Count",
    "Third Party Scripts",
    "Third Party Total Size (KB)",
    "Has Google Analytics",
    "Has Tag Manager",
    "Has Meta Pixel",
    "Has Chat Widget",
    "Has Consent Manager",
    "Third Party JS Blocking",
    "Image Count",
    "Broken Image Count",
    "Large Image Count",
    "Broken Image URLs",
    "Oversized Image URLs",
    "Has Broken Images",
    "Hreflang Declared Languages",
    "Hreflang Alternate URLs",
    "Hreflang Reciprocal Status",
    "Hreflang Code Valid",
    "PageRank Percentile",
    "Equity Tier",
    "Inbound Internal Link Count",
    "Generic Inbound Anchor %",
    "Generic Anchor Dominance",
    "Featured Snippet Type",
    "Featured Snippet Readiness",
    "GSC Position Opportunity",
    "Top TF-IDF Terms",
    "Keyword in Title",
    "Keyword in H1",
    "Keyword in First Paragraph",
    "Keyword Density (%)",
)

MAIN_ROW_DEFAULTS.update(
    {
        key: ENRICHMENT_PIPELINE_DEFAULTS.get(key, EXTRA_ROW_DEFAULTS.get(key))
        for key in _MAIN_ENRICHMENT_MIRROR_KEYS
    }
)

EXTRA_ROW_DEFAULTS.update(
    {
        key: None
        for key in (
            "Lighthouse Performance (Mobile)",
            "Lighthouse Accessibility (Mobile)",
            "Lighthouse Best Practices (Mobile)",
            "Lighthouse SEO Score (Mobile)",
            "Lab LCP (Mobile) (s)",
            "Lab CLS (Mobile)",
            "Lab TBT (Mobile) (ms)",
            "Lab INP (Mobile) (ms)",
            "Lab FCP (Mobile) (s)",
            "Lab Speed Index (Mobile) (s)",
            "Lab TTI (Mobile) (s)",
            "Lab TTFB (Mobile) (ms)",
            "Lighthouse Performance (Desktop)",
            "Lighthouse Accessibility (Desktop)",
            "Lighthouse Best Practices (Desktop)",
            "Lighthouse SEO Score (Desktop)",
            "Lab LCP (Desktop) (s)",
            "Lab CLS (Desktop)",
            "Lab TBT (Desktop) (ms)",
            "Lab INP (Desktop) (ms)",
            "Lab FCP (Desktop) (s)",
            "Lab Speed Index (Desktop) (s)",
            "Lab TTI (Desktop) (s)",
            "Lab TTFB (Desktop) (ms)",
            "Page Size (KB)",
            "DOM Size (nodes)",
            "JS Execution (ms)",
            "Network Request Count",
            "Has Text Compression",
            "Has Long Cache TTL Issues",
            "Has Render Blocking Resources",
            "Uses Modern Image Formats",
        )
    }
)

MAIN_ROW_DEFAULTS.update(
    {key: EXTRA_ROW_DEFAULTS[key] for key in EXTRA_ROW_DEFAULTS if key.startswith(("Lighthouse ", "Lab ", "Page Size", "DOM Size", "JS Execution", "Network Request", "Has ", "Uses Modern"))}
)


class MainRowPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    values: dict[str, Any] = Field(default_factory=lambda: dict(MAIN_ROW_DEFAULTS))

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict) and "values" in data:
            candidate = data["values"]
        else:
            candidate = data
        if candidate is None:
            candidate = {}
        if not isinstance(candidate, dict):
            raise TypeError("MainRowPayload requires a dict payload")
        merged = MAIN_ROW_DEFAULTS.copy()
        for key, value in candidate.items():
            if key in MAIN_ROW_DEFAULTS:
                merged[key] = value
        return {"values": merged}

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.values)


class ExtraRowPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    values: dict[str, Any] = Field(default_factory=lambda: dict(EXTRA_ROW_DEFAULTS))

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict) and "values" in data:
            candidate = data["values"]
        else:
            candidate = data
        if candidate is None:
            candidate = {}
        if not isinstance(candidate, dict):
            raise TypeError("ExtraRowPayload requires a dict payload")
        merged = {k: list(v) if isinstance(v, list) else v for k, v in EXTRA_ROW_DEFAULTS.items()}
        for key, value in candidate.items():
            if key in EXTRA_ROW_DEFAULTS:
                merged[key] = value
        return {"values": merged}

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.values)


class CrawlRowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    main: MainRowPayload
    extra: ExtraRowPayload

    def model_dump_rows(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.main.to_dict(), self.extra.to_dict()


class SummaryMetricsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    urls_crawled: int = Field(ge=0)
    seo_pass_rate_pct: float = Field(ge=0.0, le=100.0)
    health_score_pct: float = Field(ge=0.0, le=100.0)
    critical_url_count: int = Field(ge=0)
    warning_url_count: int = Field(ge=0)
    projected_health_score_pct: float = Field(ge=0.0, le=100.0)
    projected_pass_rate_pct: float = Field(ge=0.0, le=100.0)


# ---------------------------------------------------------------------------
# Strict raw-response validators (Sprint 1 Bulletproof Foundation).
#
# Additive only. These models exist alongside the established ``CrawlResult``
# TypedDict and ``CrawlResultModel`` to validate **raw** upstream payloads
# (HTTP fetch result, Google PSI, Google Search Console) before they enter
# the pipeline. Existing dictionary keys in ``main_data`` are unchanged.
# ---------------------------------------------------------------------------


_HTTP_SENTINEL_STATUSES: frozenset[str] = frozenset(
    {"Timeout", "Connection Error", "Unknown"}
)


class HttpCrawlResultModel(BaseModel):
    """Strict raw-fetch envelope: URL, HTTP status, response timing.

    Designed for use at the boundary of the ``crawler/`` HTTP layer to catch
    silent corruption (negative timings, non-numeric statuses, blank URLs).
    Caller is expected to wrap ``model_validate`` in a ``try/except
    ValidationError`` block and degrade gracefully — never crash the loop.

    Sprint 2 additions (additive only): ``field_cls`` and ``field_lcp_ms``
    carry browser-native ``PerformanceObserver`` measurements captured during
    rendered fetch; ``raw_word_count`` / ``rendered_word_count`` /
    ``is_js_dependent`` carry the raw-vs-rendered DOM diff signal.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    url: str = Field(..., min_length=1)
    status_code: int = Field(..., ge=100, le=599)
    response_time_ms: float = Field(..., ge=0.0)
    final_url: str | None = None
    error_kind: str | None = None
    field_cls: float | None = Field(default=None, ge=0.0)
    field_lcp_ms: float | None = Field(default=None, ge=0.0)
    raw_word_count: int | None = Field(default=None, ge=0)
    rendered_word_count: int | None = Field(default=None, ge=0)
    is_js_dependent: bool | None = None
    # Sprint 3 — semantic / answer-engine readiness signals. ``aeo_score``
    # here is the new entity-density + citation-presence weighted average
    # produced by ``hype_frog.extractors.semantic_engine``; it deliberately
    # coexists with the existing ``AEO Readiness Score`` workbook column
    # (computed by ``pipeline.assemble.compute_aeo_readiness_score``) — the
    # two are different signals and both ship in the row payload.
    entity_density: float | None = Field(default=None, ge=0.0)
    top_entities: list[str] | None = None
    citation_count: int | None = Field(default=None, ge=0)
    aeo_score: float | None = Field(default=None, ge=0.0, le=100.0)
    # Sprint 4 — structural / security / link / i18n diagnostics. All
    # additive. ``crawl_depth`` is the BFS hop count from the seed
    # (``0`` = seed). ``hsts_enabled`` / ``csp_defined`` are boolean
    # digests of the raw ``Strict-Transport-Security`` /
    # ``Content-Security-Policy`` headers; ``x_frame_options`` carries
    # the raw header string (or ``None`` when absent).
    # ``internal_link_count`` / ``anchor_text_summary`` summarise the
    # internal ``<a>`` pool extracted on-page. ``hreflang_tags`` is the
    # on-page hreflang cluster joined as ``"lang: url; lang: url"`` —
    # no separate network fetch is performed for validation.
    crawl_depth: int | None = Field(default=None, ge=0)
    hsts_enabled: bool | None = None
    csp_defined: bool | None = None
    x_frame_options: str | None = None
    internal_link_count: int | None = Field(default=None, ge=0)
    anchor_text_summary: str | None = None
    hreflang_tags: str | None = None

    @field_validator("url", "final_url", mode="before")
    @classmethod
    def _strip_url(cls, value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("status_code", mode="before")
    @classmethod
    def _reject_sentinels(cls, value: Any) -> Any:
        if isinstance(value, str) and value in _HTTP_SENTINEL_STATUSES:
            raise ValueError(f"non-numeric HTTP status sentinel: {value!r}")
        return value

    @field_validator("response_time_ms", mode="after")
    @classmethod
    def _finite_response_time(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("response_time_ms must be finite")
        return value

    @field_validator("field_cls", "field_lcp_ms", mode="after")
    @classmethod
    def _finite_field_metric(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if math.isnan(value) or math.isinf(value):
            raise ValueError("field metric must be finite")
        return value

    @field_validator("entity_density", "aeo_score", mode="after")
    @classmethod
    def _finite_semantic_metric(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if math.isnan(value) or math.isinf(value):
            raise ValueError("semantic metric must be finite")
        return value

    @field_validator("top_entities", mode="before")
    @classmethod
    def _normalise_top_entities(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return [item.strip() for item in value.split("|") if item.strip()]
        return value

    @field_validator(
        "x_frame_options",
        "anchor_text_summary",
        "hreflang_tags",
        mode="before",
    )
    @classmethod
    def _normalise_diagnostic_strings(cls, value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class PSIMetricsModel(BaseModel):
    """Strict PageSpeed Insights metrics extracted from a Lighthouse payload.

    Field naming mirrors the flattened keys produced by
    ``hype_frog.crawler.psi_engine._lab_strategy_metrics``. ``fid_ms`` is
    accepted for legacy CrUX snapshots (pre-INP) and remains optional.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    url: str | None = None
    performance_score: int | None = Field(default=None, ge=0, le=100)
    seo_score: int | None = Field(default=None, ge=0, le=100)
    lcp_seconds: float | None = Field(default=None, ge=0.0)
    cls: float | None = Field(default=None, ge=0.0)
    inp_ms: float | None = Field(default=None, ge=0.0)
    fid_ms: float | None = Field(default=None, ge=0.0)
    ttfb_seconds: float | None = Field(default=None, ge=0.0)

    @field_validator(
        "lcp_seconds",
        "cls",
        "inp_ms",
        "fid_ms",
        "ttfb_seconds",
        mode="after",
    )
    @classmethod
    def _finite_or_none(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if math.isnan(value) or math.isinf(value):
            raise ValueError("PSI metric must be finite")
        return value

    @model_validator(mode="after")
    def _require_some_signal(self) -> PSIMetricsModel:
        signal_fields = (
            self.performance_score,
            self.seo_score,
            self.lcp_seconds,
            self.cls,
            self.inp_ms,
            self.fid_ms,
            self.ttfb_seconds,
        )
        if all(field is None for field in signal_fields):
            raise ValueError(
                "PSI payload contained no recognisable Lighthouse/CrUX metrics"
            )
        return self


class GSCMetricsModel(BaseModel):
    """Strict per-page Google Search Console row.

    Mirrors the float/int shape returned by the Search Console
    ``searchanalytics.query`` endpoint. ``ctr`` is the GSC-native ratio in
    [0, 1] (not a percentage). ``position`` allows ``0.0`` because the API
    occasionally returns it for rows with no qualifying impressions.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    url: str | None = None
    clicks: int = Field(..., ge=0)
    impressions: int = Field(..., ge=0)
    ctr: float = Field(..., ge=0.0, le=1.0)
    position: float = Field(..., ge=0.0)

    @field_validator("clicks", "impressions", mode="before")
    @classmethod
    def _coerce_count(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("GSC count field is required")
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                raise ValueError("GSC count must be finite")
            if value < 0:
                raise ValueError("GSC count must be non-negative")
            return int(value)
        return value

    @field_validator("ctr", "position", mode="after")
    @classmethod
    def _finite_metric(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("GSC metric must be finite")
        return value
