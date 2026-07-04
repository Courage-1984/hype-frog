"""Content Hub H1 display aligns with Main / extractor counts."""

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.reporter.engine_rows import build_content_optimisation_hub_rows


def test_hub_h1_ok_when_main_has_pipe_in_heading_text() -> None:
    main = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/",
            "H1 Content": "Tips | Tools for SEO",
            "SEO Health Score": 55.0,
        }
    )
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/",
            "H1 Count": 1,
            "Primary H1 Content": "Tips | Tools for SEO",
            "Current H-Tag Structure": "H1: Tips | Tools for SEO",
            "SEO Health Score": 55.0,
        }
    )
    hub_rows, _metrics = build_content_optimisation_hub_rows([main], [extra], [])
    assert len(hub_rows) == 1
    assert hub_rows[0]["H1"] == "Tips | Tools for SEO"
    assert hub_rows[0]["H1 Health"] == "OK"


def test_hub_orders_urls_by_discovery_rank_not_alphabetically() -> None:
    """URLs must follow crawl/sitemap discovery order, not the URL string."""
    main_b = MainRowPayload.model_validate(
        {"URL": "https://example.com/b-page", "SEO Health Score": 50.0}
    )
    main_a = MainRowPayload.model_validate(
        {"URL": "https://example.com/a-page", "SEO Health Score": 50.0}
    )
    extra_b = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/b-page",
            "SEO Health Score": 50.0,
            "Discovery Rank": 1,
        }
    )
    extra_a = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/a-page",
            "SEO Health Score": 50.0,
            "Discovery Rank": 2,
        }
    )
    fixplan_rows = [
        {"URL": "https://example.com/b-page", "Resolution Type": "Manual Content"},
        {"URL": "https://example.com/a-page", "Resolution Type": "Manual Content"},
    ]
    _hub_rows, metrics_rows = build_content_optimisation_hub_rows(
        [main_b, main_a], [extra_b, extra_a], fixplan_rows
    )
    # b-page was discovered first (Discovery Rank 1) even though it sorts after
    # a-page alphabetically — order must follow discovery order, not URL string.
    assert [row["URL"] for row in metrics_rows] == [
        "https://example.com/b-page",
        "https://example.com/a-page",
    ]


def test_hub_h1_missing_when_extractor_found_none() -> None:
    main = MainRowPayload.model_validate(
        {"URL": "https://example.com/about", "SEO Health Score": 40.0}
    )
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/about",
            "H1 Count": 0,
            "SEO Health Score": 40.0,
        }
    )
    hub_rows, _metrics = build_content_optimisation_hub_rows([main], [extra], [])
    assert hub_rows[0]["H1"] == ""
    assert hub_rows[0]["H1 Health"] == "MISSING"


def test_hub_h1_multiple_flag_uses_h1_count_not_pipe_heuristic() -> None:
    main = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/x",
            "H1 Content": "Alpha | Beta",
            "SEO Health Score": 30.0,
        }
    )
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/x",
            "H1 Count": 2,
            "Primary H1 Content": "Alpha",
            "Current H-Tag Structure": "H1: Alpha\nH1: Beta",
            "SEO Health Score": 30.0,
        }
    )
    hub_rows, _metrics = build_content_optimisation_hub_rows([main], [extra], [])
    assert hub_rows[0]["H1"] == "Alpha"
    assert hub_rows[0]["H1 Health"] == "FIX: MULTIPLE"
