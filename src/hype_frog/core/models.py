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
    desktop_psi_score: int = Field(default=0, alias="Desktop PSI Score")
    mobile_psi_score: int = Field(default=0, alias="Mobile PSI Score")
    mobile_lcp_s: float = Field(default=0.0, alias="Mobile LCP (s)")
    cwv_lcp_s: float = Field(default=0.0, alias="CWV LCP (s)")
    gsc_clicks: float = Field(default=0.0, alias="GSC Clicks")
    gsc_impressions: float = Field(default=0.0, alias="GSC Impressions")

    @field_validator(
        "desktop_psi_score",
        "mobile_psi_score",
        "mobile_lcp_s",
        "cwv_lcp_s",
        "gsc_clicks",
        "gsc_impressions",
        mode="before",
    )
    @classmethod
    def _coerce_numeric_defaults(cls, value: Any) -> Any:
        if value is None:
            return 0
        if isinstance(value, str) and not value.strip():
            return 0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0
        if math.isnan(numeric) or math.isinf(numeric):
            return 0
        return value


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
        fallback["Desktop PSI Score"] = int(_safe_float(fallback.get("Desktop PSI Score") or 0))
        fallback["Mobile PSI Score"] = int(_safe_float(fallback.get("Mobile PSI Score") or 0))
        fallback["Mobile LCP (s)"] = _safe_float(fallback.get("Mobile LCP (s)") or 0.0)
        fallback["CWV LCP (s)"] = _safe_float(fallback.get("CWV LCP (s)") or 0.0)
        fallback["GSC Clicks"] = _safe_float(fallback.get("GSC Clicks") or 0.0)
        fallback["GSC Impressions"] = _safe_float(fallback.get("GSC Impressions") or 0.0)
        return fallback
    return validated.model_dump(by_alias=True, exclude_none=False)


MAIN_ROW_DEFAULTS: dict[str, Any] = {
    "URL": "",
    "Extraction State": "skipped",
    "Extraction Source": "raw_http",
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
    "Field vs Lab": "Lab",
    "Regional Authority Score": 0,
    "Desktop PSI Score": 0,
    "Mobile PSI Score": 0,
    "Mobile LCP (s)": 0.0,
    "Mobile CLS": 0.0,
    "Mobile TTFB (s)": 0.0,
    "GSC Clicks": 0.0,
    "GSC Impressions": 0.0,
    "GSC CTR": 0.0,
    "GSC Avg Position": 0.0,
    "Click Depth": None,
    "Orphan Pages": False,
    "Internal PageRank": 0.0,
    "Found via Sitemap": False,
    "Found via Crawl": False,
    "Discovery Source": "Crawl",
    "Technical Health": 0.0,
    "Copy Score": 0.0,
    "SEO Score": 0.0,
    "Action Needed": "No",
}


EXTRA_ROW_DEFAULTS: dict[str, Any] = {
    "URL": "",
    "Extraction State": "skipped",
    "Extraction Source": "raw_http",
    "Status Code": None,
    "Final URL": None,
    "Protocol": None,
    "Redirect Chain Length": 0,
    "Redirect Target": None,
    "Redirect Hops": None,
    "HTTP->HTTPS Redirect": False,
    "Status Class": None,
    "TTFB (ms)": None,
    "Total Request Time (ms)": None,
    "Content-Type": None,
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
    "Current H-Tag Structure": None,
    "Current Page Copy Snippet": None,
    "Missing H1 Flag": False,
    "Multiple H1 Flag": False,
    "Thin Content Flag": False,
    "Body Text-to-HTML Ratio": None,
    "Word Count": 0,
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
    "OG Image": None,
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
    "CWV INP (ms)": None,
    "CWV CLS": None,
    "CWV Data Source": "Lab",
    "Field vs Lab": "Lab",
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
    "Desktop PSI Score": 0,
    "Mobile PSI Score": 0,
    "Mobile LCP (s)": 0.0,
    "Mobile CLS": 0.0,
    "Mobile TTFB (s)": 0.0,
    "GSC Clicks": 0.0,
    "GSC Impressions": 0.0,
    "GSC CTR": 0.0,
    "GSC Avg Position": 0.0,
    "GSC Inspection Coverage": None,
    "GSC Inspection Verdict": None,
    "GSC Inspection Coverage State": None,
    "GSC Inspection Google Canonical": None,
    "GSC Inspection Crawl State": None,
    "GSC Inspection Robots State": None,
    "GSC Inspection Last Crawl": None,
    "Click Depth": None,
    "Orphan Pages": False,
    "Internal PageRank": 0.0,
    "Internal Inlinks": 0,
    "Found via Sitemap": False,
    "Found via Crawl": False,
    "Discovery Source": "Crawl",
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
    "aeo_snippets": [],
}


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
        merged = deepcopy(MAIN_ROW_DEFAULTS)
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
        merged = deepcopy(EXTRA_ROW_DEFAULTS)
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
