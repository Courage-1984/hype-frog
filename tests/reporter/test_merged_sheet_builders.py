"""Merged workbook tabs must populate from paired Main + Extra crawl rows."""

from __future__ import annotations

from hype_frog.reporter.sheets.merged_builders import (
    build_content_ai_readiness_rows,
    build_issue_register_rows,
    build_link_intelligence_rows,
    build_link_inventory_rows,
    build_technical_diagnostics_rows,
)


def _sample_main_extra() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    url = "https://example.com/about"
    main_rows = [
        {
            "URL": url,
            "Title": "About Example Co",
            "Meta Description": "Learn about our team and mission.",
            "Word Count (Body)": 420,
            "H1 Content": "About Us",
            "Has Valid JSON-LD": True,
            "Mobile PSI Score": 88,
            "Desktop PSI Score": 92,
        }
    ]
    extra_rows = [
        {
            "URL": url,
            "Status Code": 200,
            "Severity Badge": "Warning",
            "SEO Health Score": 72.0,
            "Critical Issues Count": 0,
            "Warning Issues Count": 2,
            "Matched Issues": "Missing FAQ/QA Schema | Low AEO Readiness Score",
            "Internal Links Count": 12,
            "Broken Internal Links Count": 1,
            "Internal Inlinks": 3,
            "Generic Anchor Text Count": 2,
            "AEO Readiness Score": 55,
            "Question Heading Count": 1,
            "Word Count": 0,
            "PSI Data Status": "Lab only",
            "Mobile PSI Score": None,
            "Link Details": [
                {
                    "Source URL": url,
                    "Target URL": "https://example.com/missing",
                    "Anchor Text": "old team page",
                    "Status Code": 404,
                }
            ],
        }
    ]
    return main_rows, extra_rows


def test_technical_diagnostics_uses_main_fallbacks() -> None:
    main_rows, extra_rows = _sample_main_extra()
    rows = build_technical_diagnostics_rows(extra_rows, main_rows=main_rows)
    assert len(rows) == 1
    row = rows[0]
    assert row["URL"] == "https://example.com/about"
    assert row["Desktop PSI Score"] == 92
    assert row["Mobile PSI Score"] == 88
    assert row["SEO Health Score"] == 72
    assert "Performance" in str(row["Diagnostic Category"])


def test_content_ai_readiness_backfills_word_count_and_title() -> None:
    main_rows, extra_rows = _sample_main_extra()
    rows = build_content_ai_readiness_rows(extra_rows, main_rows=main_rows)
    assert len(rows) == 1
    row = rows[0]
    assert row["Word Count"] == 420
    assert row["Title Missing"] is False
    assert row["H1 Count"] == 1
    assert "AEO" in str(row["Content Category"])


def test_link_intelligence_summary_and_detail_rows() -> None:
    main_rows, extra_rows = _sample_main_extra()
    link_detail_rows = [
        {
            **extra_rows[0]["Link Details"][0],
            "Target Status (if crawled)": 404,
            "Crawlable": False,
        }
    ]
    graph_rows = [
        {
            "URL": "https://example.com/about",
            "Inlinks Count": 3,
            "Inlinks URLs": "https://example.com/",
            "Orphan Candidate": False,
            "Click Depth": 1,
            "Internal PageRank": 0.12,
        }
    ]
    rows = build_link_intelligence_rows(
        extra_rows=extra_rows,
        link_detail_rows=link_detail_rows,
        crawlgraph_rows=graph_rows,
        main_rows=main_rows,
    )
    summaries = [r for r in rows if r["Record Type"] == "Summary"]
    details = [r for r in rows if r["Record Type"] == "Detail"]
    assert len(summaries) == 1
    assert summaries[0]["Broken Internal Links Count"] == 1
    assert summaries[0]["Inlinks Count"] == 3
    assert len(details) == 1
    assert details[0]["Target URL"] == "https://example.com/missing"


def test_issue_register_includes_summary_and_inventory() -> None:
    summary_rows = [
        {
            "Section": "Issue Counts",
            "Severity": "Warning",
            "Issue": "Missing Meta Description",
            "Affected URL Count": 2,
            "Reference Tab": "Content & AI Readiness",
            "Affected URLs (sample)": "https://example.com/a",
        }
    ]
    issue_inventory_rows = [
        {
            "URL": "https://example.com/a",
            "Issue": "Missing Meta Description",
            "Severity": "Warning",
            "Reference Tab": "Content & AI Readiness",
            "Stable Issue ID": "https://example.com/a::missing_meta_description",
            "Owner": "Copy Writer",
            "Sprint": "",
            "Status": "Open",
        }
    ]
    rows = build_issue_register_rows(
        summary_rows=summary_rows,
        issue_inventory_rows=issue_inventory_rows,
    )
    assert any(r["Section"] == "Issue Counts" for r in rows)
    assert any(r["Section"] == "Issue Inventory" for r in rows)


def test_link_inventory_deduplicates_source_target_anchor() -> None:
    url = "https://example.com/page"
    target = "https://example.com/about"
    anchor = "About us"
    extra_rows = [
        {
            "URL": url,
            "Link Details": [
                {
                    "Target URL": target,
                    "Anchor Text": anchor,
                    "Status Code": 200,
                },
                {
                    "Target URL": target,
                    "Anchor Text": anchor,
                    "Status Code": 200,
                },
            ],
        }
    ]
    rows = build_link_inventory_rows(extra_rows)
    assert len(rows) == 1
    assert rows[0]["Source URL"] == url
    assert rows[0]["Target URL"] == target
    assert rows[0]["Anchor Text"] == anchor
