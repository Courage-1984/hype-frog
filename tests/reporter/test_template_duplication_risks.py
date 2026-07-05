"""Template & Duplication Risks sheet builder — probable-duplicate row fallback."""

from __future__ import annotations

from hype_frog.reporter.sheets.merged_builders import build_template_duplication_risks_rows


def test_probable_duplicate_falls_back_to_best_match_url_when_duplicate_of_blank() -> None:
    """Regression (M6): when Duplicate Of URL is blank but the page is still
    flagged Probable Duplicate Flag, the sheet must surface Best Match URL
    instead of leaving "Example URLs" blank with generic redirect advice."""
    duplicate_rows = [
        {
            "URL": "https://example.com/primary",
            "Probable Duplicate Flag": True,
            "Duplicate Of URL": None,
            "Best Match URL": "https://example.com/near-duplicate",
            "Content Similarity %": 100.0,
            "Heading Structure Cluster Size": 2,
        }
    ]
    rows = build_template_duplication_risks_rows(duplicate_rows=duplicate_rows, pattern_rows=[])
    dup_row = next(r for r in rows if r["Risk Category"] == "Duplicate Content")
    assert dup_row["Example URLs"] == "https://example.com/near-duplicate"
    assert "https://example.com/near-duplicate" in dup_row["Issue"]
    assert "best-match candidate" in dup_row["Exact Action"]


def test_probable_duplicate_uses_duplicate_of_when_present() -> None:
    duplicate_rows = [
        {
            "URL": "https://example.com/copy",
            "Probable Duplicate Flag": True,
            "Duplicate Of URL": "https://example.com/original",
            "Best Match URL": "https://example.com/original",
            "Content Similarity %": 94.0,
            "Heading Structure Cluster Size": 2,
        }
    ]
    rows = build_template_duplication_risks_rows(duplicate_rows=duplicate_rows, pattern_rows=[])
    dup_row = next(r for r in rows if r["Risk Category"] == "Duplicate Content")
    assert dup_row["Example URLs"] == "https://example.com/original"
    assert "301 redirect to the primary page" in dup_row["Exact Action"]


def test_probable_duplicate_no_candidate_at_all() -> None:
    duplicate_rows = [
        {
            "URL": "https://example.com/lonely",
            "Probable Duplicate Flag": True,
            "Duplicate Of URL": None,
            "Best Match URL": None,
            "Content Similarity %": None,
            "Heading Structure Cluster Size": 1,
        }
    ]
    rows = build_template_duplication_risks_rows(duplicate_rows=duplicate_rows, pattern_rows=[])
    dup_row = next(r for r in rows if r["Risk Category"] == "Duplicate Content")
    assert dup_row["Example URLs"] == ""
    assert "no specific counterpart" in dup_row["Exact Action"]
