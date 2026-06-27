"""Competitor benchmark row builder (B5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hype_frog.analysis.competitor_benchmarks import (
    _extract_page_signals,
    _normalise_domain,
    benchmark_competitor_domains,
    build_competitor_benchmark_rows,
)


def test_build_competitor_benchmark_rows_shapes_comparison_table() -> None:
    rows, columns = build_competitor_benchmark_rows(
        client_label="client.example",
        client_metrics={"avg_aeo_proxy_score": 55.0, "title_coverage_pct": 90.0},
        competitor_metrics={
            "rival.example": {
                "avg_aeo_proxy_score": 72.0,
                "title_coverage_pct": 100.0,
            }
        },
    )
    assert columns == ("Metric", "Client Site", "rival.example")
    aeo_row = next(row for row in rows if row["Metric"] == "Average AEO / Readiness Score")
    assert aeo_row["Client Site"] == 55.0
    assert aeo_row["rival.example"] == 72.0


def test_normalise_domain_strips_scheme_and_slashes() -> None:
    assert _normalise_domain("https://Rival.Example/") == "rival.example"


def test_extract_page_signals_reads_title_schema_and_word_count() -> None:
    body_text = "marketing " * 80
    html = (
        "<html><head><title>Conference Guide</title>"
        '<meta name="description" content="Annual marketing conference.">'
        '<script type="application/ld+json">{"@type":"Event","name":"Summit"}</script>'
        f"</head><body><h1>Conference Guide</h1><p>{body_text}</p></body></html>"
    )
    signals = _extract_page_signals(html, "https://example.com/")
    assert signals["title_present"] is True
    assert signals["meta_present"] is True
    assert signals["single_h1"] is True
    assert signals["schema_present"] is True
    assert signals["word_count"] >= 80


@pytest.mark.asyncio
async def test_benchmark_competitor_domains_without_competitors_uses_client_only() -> None:
    rows, columns = await benchmark_competitor_domains(
        client_label="client.example",
        main_rows=[{"URL": "https://client.example/", "Word Count (Body)": 400}],
        extra_rows=[
            {
                "URL": "https://client.example/",
                "Title Missing": False,
                "Meta Description Missing": False,
                "H1 Count": 1,
                "Schema Types Count": 1,
                "Question Heading Count": 2,
                "AEO Readiness Score": 70,
            }
        ],
        competitor_domains=[],
    )
    assert columns == ("Metric", "Client Site")
    assert rows[0]["Metric"] == "No competitor domains configured"


@pytest.mark.asyncio
async def test_benchmark_competitor_domains_samples_competitors_with_mocked_session() -> None:
    competitor_metrics = {
        "pages_sampled": 1.0,
        "title_coverage_pct": 100.0,
        "meta_coverage_pct": 100.0,
        "single_h1_pct": 100.0,
        "schema_coverage_pct": 100.0,
        "avg_word_count": 500.0,
        "avg_question_headings": 1.0,
        "avg_aeo_proxy_score": 80.0,
    }
    with patch(
        "hype_frog.analysis.competitor_benchmarks._aggregate_domain_signals",
        new=AsyncMock(return_value=competitor_metrics),
    ):
        rows, columns = await benchmark_competitor_domains(
            client_label="client.example",
            main_rows=[{"URL": "https://client.example/", "Word Count (Body)": 400}],
            extra_rows=[
                {
                    "URL": "https://client.example/",
                    "Title Missing": False,
                    "Meta Description Missing": False,
                    "H1 Count": 1,
                    "Schema Types Count": 1,
                    "Question Heading Count": 2,
                    "AEO Readiness Score": 70,
                }
            ],
            competitor_domains=["https://rival.example/"],
        )
    assert columns == ("Metric", "Client Site", "rival.example")
    title_row = next(row for row in rows if row["Metric"] == "Title Coverage (%)")
    assert title_row["rival.example"] == 100.0
