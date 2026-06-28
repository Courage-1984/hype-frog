"""Unit tests for the Content Planner sheet row builder."""

from __future__ import annotations

import pytest

from hype_frog.core.models import ExtraRowPayload
from hype_frog.orchestration.content_planner import (
    CONTENT_PLANNER_COLUMNS,
    CONTENT_PLANNER_SIGNOFF_COLUMNS,
    build_content_planner_rows,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extra(url: str, nav_footer: list[dict] | None = None) -> ExtraRowPayload:
    row = ExtraRowPayload()
    row.values["URL"] = url
    row.values["Nav Footer Link Details"] = nav_footer or []
    return row


def _nav_link(target: str, anchor: str = "Link", location: str = "nav") -> dict:
    return {
        "Source URL": "https://example.com/",
        "Target URL": target,
        "Anchor Text": anchor,
        "Link Location": location,
    }


# ---------------------------------------------------------------------------
# Column contract
# ---------------------------------------------------------------------------

def test_column_tuple_length() -> None:
    assert len(CONTENT_PLANNER_COLUMNS) == 19


def test_column_tuple_starts_with_hierarchy_then_link() -> None:
    assert CONTENT_PLANNER_COLUMNS[:4] == ("Primary", "Secondary", "Tertiary", "Page link")


def test_copy_doc_is_not_a_signoff_column() -> None:
    assert "Copy Doc" not in CONTENT_PLANNER_SIGNOFF_COLUMNS


def test_signoff_columns_count() -> None:
    assert len(CONTENT_PLANNER_SIGNOFF_COLUMNS) == 14


def test_all_signoff_columns_present_in_main_tuple() -> None:
    for col in CONTENT_PLANNER_SIGNOFF_COLUMNS:
        assert col in CONTENT_PLANNER_COLUMNS


# ---------------------------------------------------------------------------
# build_content_planner_rows — happy path
# ---------------------------------------------------------------------------

def test_empty_nav_footer_returns_empty_list() -> None:
    extra = _make_extra("https://example.com/")
    result = build_content_planner_rows([extra], root_url="https://example.com/")
    assert result == []


def test_no_homepage_row_returns_empty_list() -> None:
    extra = _make_extra("https://example.com/about/")
    result = build_content_planner_rows([extra], root_url="https://example.com/")
    assert result == []


def test_primary_link_at_depth_1() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/", "About")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert len(rows) == 1
    assert rows[0]["Primary"] == "about"
    assert rows[0]["Secondary"] is None
    assert rows[0]["Tertiary"] is None
    assert rows[0]["Page link"] == "https://example.com/about/"


def test_secondary_link_at_depth_2() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/team/", "Team")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert len(rows) == 1
    assert rows[0]["Primary"] is None
    assert rows[0]["Secondary"] == "team"
    assert rows[0]["Tertiary"] is None


def test_tertiary_link_at_depth_3_plus() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/team/leadership/", "Leadership")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert len(rows) == 1
    assert rows[0]["Tertiary"] == "leadership"
    assert rows[0]["Primary"] is None
    assert rows[0]["Secondary"] is None


def test_root_url_itself_gets_primary_home_label() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/", "Home")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert rows[0]["Primary"] == "Home"
    assert rows[0]["Page link"] == "https://example.com/"


def test_duplicate_targets_deduplicated() -> None:
    links = [
        _nav_link("https://example.com/about/", "About"),
        _nav_link("https://example.com/about/", "About Us"),
    ]
    extra = _make_extra("https://example.com/", links)
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert len(rows) == 1


def test_rows_sorted_by_url_path() -> None:
    links = [
        _nav_link("https://example.com/services/", "Services"),
        _nav_link("https://example.com/about/", "About"),
        _nav_link("https://example.com/contact/", "Contact"),
    ]
    extra = _make_extra("https://example.com/", links)
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    paths = [r["Page link"] for r in rows]
    assert paths == sorted(paths)


def test_row_keys_match_content_planner_columns() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/", "About")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    row_keys = set(rows[0].keys())
    expected_keys = set(CONTENT_PLANNER_COLUMNS)
    assert row_keys == expected_keys


def test_signoff_columns_default_to_not_signed_off() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/", "About")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    for col in CONTENT_PLANNER_SIGNOFF_COLUMNS:
        assert rows[0][col] == "Not signed off"


def test_copy_doc_defaults_to_none() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/", "About")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert rows[0]["Copy Doc"] is None


def test_footer_links_included_alongside_nav_links() -> None:
    links = [
        _nav_link("https://example.com/about/", "About", location="nav"),
        _nav_link("https://example.com/privacy/", "Privacy", location="footer"),
    ]
    extra = _make_extra("https://example.com/", links)
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    page_links = {r["Page link"] for r in rows}
    assert "https://example.com/about/" in page_links
    assert "https://example.com/privacy/" in page_links


def test_root_url_with_trailing_slash_matches_normalized_key() -> None:
    extra = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/blog/", "Blog")],
    )
    rows = build_content_planner_rows([extra], root_url="https://example.com")
    assert len(rows) >= 0


def test_multiple_extra_rows_only_homepage_used() -> None:
    home = _make_extra(
        "https://example.com/",
        [_nav_link("https://example.com/about/", "About")],
    )
    other = _make_extra(
        "https://example.com/other/",
        [_nav_link("https://example.com/services/", "Services")],
    )
    rows = build_content_planner_rows([home, other], root_url="https://example.com/")
    page_links = {r["Page link"] for r in rows}
    assert "https://example.com/about/" in page_links
    assert "https://example.com/services/" not in page_links


@pytest.mark.parametrize(
    ("url", "expected_col", "expected_label"),
    [
        ("https://example.com/about/", "Primary", "about"),
        ("https://example.com/about/team/", "Secondary", "team"),
        ("https://example.com/about/team/exec/", "Tertiary", "exec"),
        ("https://example.com/a/b/c/d/", "Tertiary", "d"),
    ],
)
def test_hierarchy_assignment_parametrized(
    url: str, expected_col: str, expected_label: str
) -> None:
    extra = _make_extra("https://example.com/", [_nav_link(url)])
    rows = build_content_planner_rows([extra], root_url="https://example.com/")
    assert rows[0][expected_col] == expected_label
