from __future__ import annotations

from typing import Any, TypedDict


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
