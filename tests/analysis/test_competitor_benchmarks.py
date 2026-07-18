"""Competitor benchmark row builder (B5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hype_frog.analysis.competitor_benchmarks import (
    _aeo_proxy_score,
    _aggregate_domain_signals,
    _client_aggregate,
    _extract_page_signals,
    _fetch_html,
    _normalise_domain,
    _sample_urls_for_domain,
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


# ---------------------------------------------------------------------------
# _aeo_proxy_score
# ---------------------------------------------------------------------------


def test_aeo_proxy_score_all_signals_present_caps_at_100() -> None:
    score = _aeo_proxy_score(
        title_present=True,
        meta_present=True,
        single_h1=True,
        question_headings=3,
        schema_present=True,
        word_count=500,
    )
    assert score == 100.0


def test_aeo_proxy_score_no_signals_is_zero() -> None:
    score = _aeo_proxy_score(
        title_present=False,
        meta_present=False,
        single_h1=False,
        question_headings=0,
        schema_present=False,
        word_count=0,
    )
    assert score == 0.0


def test_aeo_proxy_score_word_count_below_threshold_excluded() -> None:
    score = _aeo_proxy_score(
        title_present=True,
        meta_present=True,
        single_h1=True,
        question_headings=1,
        schema_present=True,
        word_count=299,
    )
    assert score == 85.0


# ---------------------------------------------------------------------------
# _extract_page_signals — schema edge cases
# ---------------------------------------------------------------------------


def test_extract_page_signals_handles_list_type_ld_json() -> None:
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": ["Article", "NewsArticle"]}</script></head>'
        "<body><h1>Title</h1></body></html>"
    )
    signals = _extract_page_signals(html, "https://example.com/")
    assert signals["schema_present"] is True
    assert signals["schema_count"] == 2


def test_extract_page_signals_ignores_malformed_ld_json() -> None:
    html = (
        '<html><head><script type="application/ld+json">not valid json'
        "</script></head><body><h1>Title</h1></body></html>"
    )
    signals = _extract_page_signals(html, "https://example.com/")
    assert signals["schema_present"] is False


def test_extract_page_signals_ignores_empty_ld_json_script() -> None:
    html = (
        '<html><head><script type="application/ld+json"></script></head>'
        "<body><h1>Title</h1></body></html>"
    )
    signals = _extract_page_signals(html, "https://example.com/")
    assert signals["schema_present"] is False


def test_extract_page_signals_counts_question_style_headings() -> None:
    html = (
        "<html><body><h1>Guide</h1>"
        "<h2>What is SEO?</h2><h3>How does it work?</h3><h2>Overview</h2>"
        "</body></html>"
    )
    signals = _extract_page_signals(html, "https://example.com/")
    assert signals["question_headings"] == 2


def test_extract_page_signals_blank_html_returns_empty_signals() -> None:
    signals = _extract_page_signals("", "https://example.com/")
    assert signals["title_present"] is False
    assert signals["word_count"] == 0


# ---------------------------------------------------------------------------
# _fetch_html
# ---------------------------------------------------------------------------


def _cm_response(status: int, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_fetch_html_non_200_returns_none() -> None:
    session = MagicMock()
    session.get = MagicMock(return_value=_cm_response(404))
    result = await _fetch_html(session, "https://example.com/missing")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_html_200_returns_body_text() -> None:
    session = MagicMock()
    session.get = MagicMock(return_value=_cm_response(200, "<html>ok</html>"))
    result = await _fetch_html(session, "https://example.com/")
    assert result == "<html>ok</html>"


@pytest.mark.asyncio
async def test_fetch_html_transport_exception_returns_none() -> None:
    session = MagicMock()
    session.get = MagicMock(side_effect=RuntimeError("connection refused"))
    result = await _fetch_html(session, "https://example.com/")
    assert result is None


# ---------------------------------------------------------------------------
# _sample_urls_for_domain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sample_urls_for_domain_uses_sitemap_when_available() -> None:
    session = MagicMock()
    sitemap_urls = [f"https://rival.example/page-{i}" for i in range(15)]
    with patch(
        "hype_frog.analysis.competitor_benchmarks.parse_sitemap",
        new=AsyncMock(return_value=(sitemap_urls, {}, [])),
    ):
        result = await _sample_urls_for_domain(session, "rival.example")
    assert result[0] == "https://rival.example/"
    assert len(result) <= 11


@pytest.mark.asyncio
async def test_sample_urls_for_domain_falls_back_to_homepage_only_on_sitemap_failure() -> None:
    session = MagicMock()
    with patch(
        "hype_frog.analysis.competitor_benchmarks.parse_sitemap",
        new=AsyncMock(side_effect=RuntimeError("network error")),
    ):
        result = await _sample_urls_for_domain(session, "rival.example")
    assert result == ["https://rival.example/"]


@pytest.mark.asyncio
async def test_sample_urls_for_domain_dedupes_trailing_slash_variants() -> None:
    session = MagicMock()
    with patch(
        "hype_frog.analysis.competitor_benchmarks.parse_sitemap",
        new=AsyncMock(return_value=(["https://rival.example/", "https://rival.example"], {}, [])),
    ):
        result = await _sample_urls_for_domain(session, "rival.example")
    assert len(result) == 1


# ---------------------------------------------------------------------------
# _aggregate_domain_signals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_domain_signals_all_fetches_fail_returns_none_metrics() -> None:
    session = MagicMock()
    with (
        patch(
            "hype_frog.analysis.competitor_benchmarks._sample_urls_for_domain",
            new=AsyncMock(return_value=["https://rival.example/"]),
        ),
        patch(
            "hype_frog.analysis.competitor_benchmarks._fetch_html",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await _aggregate_domain_signals(session, "rival.example")
    assert result["pages_sampled"] == 0.0
    assert result["title_coverage_pct"] is None


@pytest.mark.asyncio
async def test_aggregate_domain_signals_computes_coverage_from_sampled_pages() -> None:
    session = MagicMock()
    html_with_title = "<html><head><title>Page</title></head><body><h1>H</h1></body></html>"
    with (
        patch(
            "hype_frog.analysis.competitor_benchmarks._sample_urls_for_domain",
            new=AsyncMock(return_value=["https://rival.example/"]),
        ),
        patch(
            "hype_frog.analysis.competitor_benchmarks._fetch_html",
            new=AsyncMock(return_value=html_with_title),
        ),
        patch("asyncio.sleep", new=AsyncMock(return_value=None)),
    ):
        result = await _aggregate_domain_signals(session, "rival.example")
    assert result["pages_sampled"] == 1.0
    assert result["title_coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# _client_aggregate
# ---------------------------------------------------------------------------


def test_client_aggregate_handles_missing_extra_row_with_defaults() -> None:
    """A main row with no matching extra row must not crash. Absent
    ``*_Missing`` flags default to "not missing" (optimistic), while absent
    counts (H1/Schema) default to zero, so single-H1/schema coverage reads
    as 0% even though title/meta coverage reads as 100%."""
    metrics = _client_aggregate(
        main_rows=[{"URL": "https://client.example/orphan"}],
        extra_rows=[],
    )
    assert metrics["pages_sampled"] == 1.0
    assert metrics["title_coverage_pct"] == 100.0
    assert metrics["single_h1_pct"] == 0.0


def test_client_aggregate_multiple_h1_not_counted_as_single() -> None:
    metrics = _client_aggregate(
        main_rows=[{"URL": "https://client.example/"}],
        extra_rows=[{"URL": "https://client.example/", "H1 Count": 3}],
    )
    assert metrics["single_h1_pct"] == 0.0
