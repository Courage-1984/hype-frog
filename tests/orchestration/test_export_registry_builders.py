"""Row builders and sheet registries in the export registry."""

from __future__ import annotations

from hype_frog.orchestration.export_registry import (
    ExportRegistryConfig,
    build_crawlgraph_rows,
    build_duplicates_rows,
    build_pattern_rows,
    build_priority_rows,
    get_finalization_steps,
    get_merged_sheet_columns,
    get_sheet_sequence,
    get_standard_sheet_columns,
)
from hype_frog.reporter.sheets.config import CONTENT_PLANNER_SHEET


def _value_or_default(value: object, default: float) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def test_get_sheet_sequence_main_only_vs_full_suite() -> None:
    assert get_sheet_sequence(ExportRegistryConfig(full_suite=False)) == ["Main"]
    full = get_sheet_sequence(ExportRegistryConfig(full_suite=True))
    assert "Main" in full
    assert "Executive Briefing" in full
    assert "Dashboard" not in full
    assert "IssueInventory" not in full
    assert len(full) > 25


def test_content_planner_in_full_suite_sequence() -> None:
    full = get_sheet_sequence(ExportRegistryConfig(full_suite=True))
    assert CONTENT_PLANNER_SHEET in full


def test_get_finalization_steps_order_is_stable() -> None:
    assert get_finalization_steps() == (
        "apply_tab_hyperlinks",
        "format_sheets",
        "apply_workbook_export_guardrails",
    )


def test_sheet_column_registries_return_independent_copies() -> None:
    standard = get_standard_sheet_columns()
    assert "Schema & Metadata" in standard
    standard["Schema & Metadata"].append("MUTATED")
    assert "MUTATED" not in get_standard_sheet_columns()["Schema & Metadata"]

    merged = get_merged_sheet_columns()
    assert "Issue Register" in merged
    assert "Link Inventory" in merged


def test_build_duplicates_rows_detects_shared_titles() -> None:
    main_rows = [
        {"URL": "https://s/1", "Title": "Same Title", "Meta Description": "d1"},
        {"URL": "https://s/2", "Title": "Same Title", "Meta Description": "d2"},
        {"URL": "https://s/3", "Title": "Unique", "Meta Description": "d3"},
    ]
    rows = build_duplicates_rows(main_rows)
    by_url = {r["URL"]: r for r in rows}

    assert by_url["https://s/1"]["Title Duplicate Count"] == 2
    assert "https://s/1" in by_url["https://s/1"]["Title Duplicate URLs"]
    assert by_url["https://s/3"]["Title Duplicate Count"] == 1
    assert by_url["https://s/3"]["Title Duplicate URLs"] is None


def test_build_pattern_rows_flags_template_wide_missing_h1() -> None:
    extra_rows = [
        {"URL": f"https://s/blog/{i}", "Final URL": f"https://s/blog/{i}", "Missing H1 Flag": True}
        for i in range(5)
    ]
    cluster_rows, _issue_counts = build_pattern_rows(
        extra_rows, extract_subfolder_fn=lambda _url: "/blog"
    )
    assert cluster_rows[0]["Systemic Issue"] == "Missing H1 is template-wide"
    assert cluster_rows[0]["Affected Ratio"] == 100.0


def test_build_pattern_rows_returns_default_when_clean() -> None:
    extra_rows = [
        {"URL": "https://s/a", "Final URL": "https://s/a", "Missing H1 Flag": False},
    ]
    cluster_rows, _ = build_pattern_rows(extra_rows, extract_subfolder_fn=lambda _url: "/")
    assert cluster_rows[0]["Systemic Issue"].startswith("No systemic")


def test_build_priority_rows_scores_and_sorts() -> None:
    extra_rows = [
        {
            "URL": "https://s/pricing",
            "Critical Issues Count": 2,
            "Warning Issues Count": 0,
            "SEO Health Score": 50.0,
            "Broken Internal Links Count": 0,
        },
        {
            "URL": "https://s/blog",
            "Critical Issues Count": 0,
            "Warning Issues Count": 1,
            "SEO Health Score": 95.0,
            "Broken Internal Links Count": 0,
        },
    ]
    rows = build_priority_rows(
        extra_rows,
        high_value_slugs=["pricing"],
        value_or_default_fn=_value_or_default,
        owner_for_issue_fn=lambda _issue, _sev: "SEO Lead",
    )
    # 2*30 + 0 + (100-50) = 110 for pricing; 0 + 10 + (100-95) = 15 for blog.
    assert rows[0]["URL"] == "https://s/pricing"
    assert rows[0]["Business Risk Score"] == 110
    assert rows[0]["Action Needed"] == "Yes"
    assert rows[0]["Revenue Intent"] == "High"
    assert rows[1]["Business Risk Score"] == 15
    assert rows[1]["Action Needed"] == "No"
    assert rows[1]["Revenue Intent"] == "Standard"


def test_build_priority_rows_ties_break_by_discovery_rank() -> None:
    """Equal Business Risk Score rows fall back to Discovery Rank ascending."""
    extra_rows = [
        {
            "URL": "https://s/later",
            "Critical Issues Count": 1,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "Discovery Rank": 5,
        },
        {
            "URL": "https://s/earlier",
            "Critical Issues Count": 1,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "Discovery Rank": 2,
        },
        {
            "URL": "https://s/no-rank",
            "Critical Issues Count": 1,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "Discovery Rank": "",
        },
    ]
    rows = build_priority_rows(
        extra_rows,
        high_value_slugs=[],
        value_or_default_fn=_value_or_default,
        owner_for_issue_fn=lambda _issue, _sev: "SEO Lead",
    )
    # All three share the same Business Risk Score, so order must follow
    # Discovery Rank ascending, with a missing/empty rank sorting last.
    assert [row["URL"] for row in rows] == [
        "https://s/earlier",
        "https://s/later",
        "https://s/no-rank",
    ]
    assert "Discovery Rank" not in rows[0]


def test_build_priority_rows_revenue_intent_from_search_intent() -> None:
    """High-intent Search Intent labels mark Revenue Intent High even off-slug."""
    extra_rows = [
        {
            "URL": "https://s/some-page",
            "Critical Issues Count": 0,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "Search Intent": "Transactional",
        },
        {
            "URL": "https://s/other-page",
            "Critical Issues Count": 0,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "Search Intent": "Informational",
        },
    ]
    rows = build_priority_rows(
        extra_rows,
        high_value_slugs=[],
        value_or_default_fn=_value_or_default,
        owner_for_issue_fn=lambda _issue, _sev: "SEO Lead",
    )
    by_url = {row["URL"]: row for row in rows}
    assert by_url["https://s/some-page"]["Revenue Intent"] == "High"
    assert by_url["https://s/other-page"]["Revenue Intent"] == "Standard"


def test_build_priority_rows_revenue_intent_from_top_quartile_traffic() -> None:
    """A page whose GSC Impressions sit in the crawl's top quartile is High."""
    extra_rows = [
        {
            "URL": f"https://s/page-{i}",
            "Critical Issues Count": 0,
            "Warning Issues Count": 0,
            "SEO Health Score": 100.0,
            "Broken Internal Links Count": 0,
            "GSC Impressions": i * 10,
        }
        for i in range(1, 9)
    ]
    rows = build_priority_rows(
        extra_rows,
        high_value_slugs=[],
        value_or_default_fn=_value_or_default,
        owner_for_issue_fn=lambda _issue, _sev: "SEO Lead",
    )
    by_url = {row["URL"]: row for row in rows}
    # Highest-impressions page must be flagged High; a low-traffic page Standard.
    assert by_url["https://s/page-8"]["Revenue Intent"] == "High"
    assert by_url["https://s/page-1"]["Revenue Intent"] == "Standard"


def test_build_priority_rows_unmeasured_skips_health_penalty() -> None:
    extra_rows = [
        {
            "URL": "https://s/unmeasured",
            "Severity Badge": "Unmeasured",
            "Critical Issues Count": None,
            "Warning Issues Count": None,
            "SEO Health Score": None,
            "Broken Internal Links Count": 0,
        },
        {
            "URL": "https://s/healthy",
            "Severity Badge": "Pass",
            "Critical Issues Count": 0,
            "Warning Issues Count": 0,
            "SEO Health Score": 95.0,
            "Broken Internal Links Count": 0,
        },
    ]
    rows = build_priority_rows(
        extra_rows,
        high_value_slugs=[],
        value_or_default_fn=_value_or_default,
        owner_for_issue_fn=lambda _issue, _sev: "SEO Lead",
    )
    unmeasured = next(row for row in rows if row["URL"] == "https://s/unmeasured")
    healthy = next(row for row in rows if row["URL"] == "https://s/healthy")
    assert unmeasured["Business Risk Score"] == 0
    assert unmeasured["SEO Health Score"] is None
    assert healthy["Business Risk Score"] == 5


def test_build_crawlgraph_rows_identifies_orphans_and_inlinks() -> None:
    main_urls = ["https://s/a", "https://s/b"]
    extra_rows = [
        {
            "URL": "https://s/a",
            "Internal Links List": ["https://s/b"],
            "Click Depth": 0,
            "Internal PageRank": 0.5,
        },
        {
            "URL": "https://s/b",
            "Internal Links List": [],
            "Click Depth": 1,
            "Internal PageRank": 0.2,
        },
    ]
    rows = build_crawlgraph_rows(main_urls=main_urls, extra_rows=extra_rows)
    by_url = {r["URL"]: r for r in rows}

    assert by_url["https://s/a"]["Inlinks Count"] == 0
    assert by_url["https://s/a"]["Orphan Candidate"] is True
    assert by_url["https://s/b"]["Inlinks Count"] == 1
    assert by_url["https://s/b"]["Orphan Candidate"] is False
    assert "https://s/a" in by_url["https://s/b"]["Inlinks URLs"]
