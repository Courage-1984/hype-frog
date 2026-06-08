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
