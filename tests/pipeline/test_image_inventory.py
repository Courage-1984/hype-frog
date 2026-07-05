"""Site-wide content image inventory row building."""

from __future__ import annotations

from hype_frog.pipeline.image_inventory import build_image_inventory_rows


def test_aggregates_unique_images_with_page_counts_and_probe_data() -> None:
    extra_rows = [
        {
            "URL": "https://s.test/p1",
            "Content Images": [
                {"url": "https://s.test/a.jpg", "alt": "Alt A"},
                {"url": "https://s.test/b.png", "alt": ""},
            ],
        },
        {
            "URL": "https://s.test/p2",
            "Content Images": [{"url": "https://s.test/a.jpg", "alt": ""}],
        },
    ]
    probe_by_url = {
        "https://s.test/a.jpg": {
            "status_code": 200,
            "size_kb": 12.0,
            "width": 800,
            "height": 600,
            "broken": False,
            "oversized": False,
        },
        "https://s.test/b.png": {"status_code": 404, "broken": True, "oversized": False},
    }

    rows = build_image_inventory_rows(extra_rows, probe_by_url)

    assert len(rows) == 2
    # Sorted by most-referenced first: a.jpg (2 pages) precedes b.png (1 page).
    first, second = rows
    assert first["Image URL"] == "https://s.test/a.jpg"
    assert first["Found On Pages"] == 2
    assert first["Status Code"] == 200
    assert first["Size (KB)"] == 12.0
    assert first["Width"] == 800
    assert first["Is Broken"] is False
    assert first["Alt Text"] == "Alt A"
    assert first["File Extension"] == "jpg"
    assert "https://s.test/p1" in first["Found On Pages (first 5)"]

    assert second["Image URL"] == "https://s.test/b.png"
    assert second["Found On Pages"] == 1
    assert second["Status Code"] == 404
    assert second["Is Broken"] is True
    assert second["File Extension"] == "png"


def test_pipe_delimited_images_fallback() -> None:
    extra_rows = [
        {
            "URL": "https://s.test/p",
            "Images": "https://s.test/c.gif|https://s.test/d.webp",
        }
    ]
    rows = build_image_inventory_rows(extra_rows, {})

    urls = {row["Image URL"] for row in rows}
    assert urls == {"https://s.test/c.gif", "https://s.test/d.webp"}
    # No probe data → status blank; "Is Broken"/"Is Oversized" must read
    # "Not Checked" rather than False (M9 fix) — False would misleadingly
    # imply the image was verified and confirmed fine.
    for row in rows:
        assert row["Status Code"] == ""
        assert row["Is Broken"] == "Not Checked"
        assert row["Is Oversized"] == "Not Checked"


def test_no_images_returns_empty_list() -> None:
    assert build_image_inventory_rows([{"URL": "https://s.test/empty"}], {}) == []
