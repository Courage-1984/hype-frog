from __future__ import annotations

import math
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


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
