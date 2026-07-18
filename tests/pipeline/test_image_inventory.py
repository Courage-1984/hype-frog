"""Site-wide content image inventory row building."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.core.models import ExtraRowPayload
from hype_frog.pipeline.image_inventory import (
    _content_images_for_row,
    _image_category,
    _normalise_images,
    _probe_image,
    build_image_inventory_rows,
    enrich_content_image_inventory,
)


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


def test_tracking_images_sort_after_content_regardless_of_page_count() -> None:
    """Tracking pixels sort last even when they appear on more pages than a
    genuine content image — the sort key puts the Tracking bucket after
    everything else before falling back to page-count/URL."""
    extra_rows = [
        {
            "URL": "https://s.test/p1",
            "Content Images": [
                {"url": "https://www.facebook.com/tr?id=123", "alt": ""},
                {"url": "https://s.test/hero.jpg", "alt": ""},
            ],
        },
        {
            "URL": "https://s.test/p2",
            "Content Images": [{"url": "https://www.facebook.com/tr?id=123", "alt": ""}],
        },
    ]

    rows = build_image_inventory_rows(extra_rows, {})

    assert rows[0]["Image URL"] == "https://s.test/hero.jpg"
    assert rows[-1]["Image Category"] == "Tracking"


# ---------------------------------------------------------------------------
# _image_category
# ---------------------------------------------------------------------------


def test_image_category_tracking_pixel() -> None:
    assert _image_category("https://www.facebook.com/tr?id=1&ev=PageView") == "Tracking"
    assert _image_category("https://www.google-analytics.com/collect") == "Tracking"


def test_image_category_avatar() -> None:
    assert _image_category("https://secure.gravatar.com/avatar/abc123") == "Avatar"


def test_image_category_icon_by_extension() -> None:
    assert _image_category("https://s.test/favicon.ico") == "Icon"
    assert _image_category("https://s.test/logo.svg") == "Icon"


def test_image_category_default_content() -> None:
    assert _image_category("https://s.test/hero-banner.jpg") == "Content"


# ---------------------------------------------------------------------------
# _normalise_images
# ---------------------------------------------------------------------------


def test_normalise_images_non_list_returns_empty() -> None:
    assert _normalise_images(None) == []
    assert _normalise_images("not a list") == []
    assert _normalise_images(42) == []


def test_normalise_images_dict_entries() -> None:
    result = _normalise_images([{"url": "https://s.test/a.jpg", "alt": "Alt A"}])
    assert result == [{"url": "https://s.test/a.jpg", "alt": "Alt A"}]


def test_normalise_images_plain_string_entries() -> None:
    result = _normalise_images(["https://s.test/a.jpg", "https://s.test/b.png"])
    assert result == [
        {"url": "https://s.test/a.jpg", "alt": ""},
        {"url": "https://s.test/b.png", "alt": ""},
    ]


def test_normalise_images_filters_blank_urls() -> None:
    result = _normalise_images([{"url": "", "alt": "orphan alt"}, {"url": "  ", "alt": ""}])
    assert result == []


# ---------------------------------------------------------------------------
# _content_images_for_row
# ---------------------------------------------------------------------------


def test_content_images_for_row_prefers_structured_over_pipe_delimited() -> None:
    row = {
        "Content Images": [{"url": "https://s.test/structured.jpg", "alt": ""}],
        "Images": "https://s.test/should-be-ignored.jpg",
    }
    assert _content_images_for_row(row) == [{"url": "https://s.test/structured.jpg", "alt": ""}]


def test_content_images_for_row_falls_back_to_pipe_delimited() -> None:
    row = {"Images": "https://s.test/a.jpg|https://s.test/b.png"}
    result = _content_images_for_row(row)
    assert [item["url"] for item in result] == ["https://s.test/a.jpg", "https://s.test/b.png"]


def test_content_images_for_row_neither_present_returns_empty() -> None:
    assert _content_images_for_row({"URL": "https://s.test/p"}) == []


# ---------------------------------------------------------------------------
# _probe_image
# ---------------------------------------------------------------------------


def _head_response(status: int, content_length: str | None = None) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.headers = {"Content-Length": content_length} if content_length else {}
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


def _get_response(status: int, body: bytes = b"") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.content = MagicMock()
    response.content.read = AsyncMock(return_value=body)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


def _png_bytes(width: int, height: int) -> bytes:
    import struct

    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


@pytest.mark.asyncio
async def test_probe_image_success_not_broken_not_oversized() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200, "12000"))
    session.get = MagicMock(return_value=_get_response(200, _png_bytes(800, 600)))

    result = await _probe_image(session, "https://s.test/a.jpg", asyncio.Semaphore(1))

    assert result["status_code"] == 200
    assert result["broken"] is False
    assert result["oversized"] is False
    assert result["width"] == 800
    assert result["height"] == 600


@pytest.mark.asyncio
async def test_probe_image_head_non_success_status_skips_get() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(404))
    session.get = MagicMock(side_effect=AssertionError("GET should not run after a failed HEAD"))

    result = await _probe_image(session, "https://s.test/missing.jpg", asyncio.Semaphore(1))

    assert result["status_code"] == 404
    assert result["broken"] is True
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_probe_image_head_exception_returns_broken_default() -> None:
    session = MagicMock()
    session.head = MagicMock(side_effect=RuntimeError("connection refused"))
    session.get = MagicMock(side_effect=AssertionError("GET should not run after a HEAD exception"))

    result = await _probe_image(session, "https://s.test/a.jpg", asyncio.Semaphore(1))

    assert result["broken"] is True
    assert result["status_code"] is None
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_probe_image_get_exception_returns_broken_default() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200))
    session.get = MagicMock(side_effect=RuntimeError("connection reset"))

    result = await _probe_image(session, "https://s.test/a.jpg", asyncio.Semaphore(1))

    assert result["broken"] is True


@pytest.mark.asyncio
async def test_probe_image_unparseable_body_marked_broken() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200))
    session.get = MagicMock(return_value=_get_response(200, b"not an image"))

    result = await _probe_image(session, "https://s.test/a.jpg", asyncio.Semaphore(1))

    assert result["broken"] is True
    assert result["width"] is None


@pytest.mark.asyncio
async def test_probe_image_oversized_flagged_when_over_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("hype_frog.pipeline.image_inventory.get_large_image_size_kb", lambda: 1)
    big_body = _png_bytes(800, 600) + b"\x00" * 2048  # comfortably over a 1KB threshold
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200))
    session.get = MagicMock(return_value=_get_response(200, big_body))

    result = await _probe_image(session, "https://s.test/huge.jpg", asyncio.Semaphore(1))

    assert result["oversized"] is True
    assert result["broken"] is False


@pytest.mark.asyncio
async def test_probe_image_malformed_content_length_header_does_not_raise() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200, content_length="not-a-number"))
    session.get = MagicMock(return_value=_get_response(200, _png_bytes(800, 600)))

    result = await _probe_image(session, "https://s.test/a.jpg", asyncio.Semaphore(1))

    assert result["broken"] is False  # did not raise; malformed header simply ignored


# ---------------------------------------------------------------------------
# enrich_content_image_inventory
# ---------------------------------------------------------------------------


def _extra_row(**values: object) -> ExtraRowPayload:
    return ExtraRowPayload(values=dict(values))


@pytest.mark.asyncio
async def test_enrich_no_images_anywhere_sets_zero_defaults_on_every_row() -> None:
    rows = [_extra_row(URL="https://s.test/p1"), _extra_row(URL="https://s.test/p2")]
    session = MagicMock()
    session.head = MagicMock(side_effect=AssertionError("should never probe"))

    result = await enrich_content_image_inventory(session, rows, workers=3)

    assert result == {}
    for row in rows:
        assert row.values["Broken Image Count"] == 0
        assert row.values["Large Image Count"] == 0
        assert row.values["Has Broken Images"] is False


@pytest.mark.asyncio
async def test_enrich_dedupes_probe_calls_across_rows_sharing_an_image() -> None:
    shared_url = "https://s.test/shared.jpg"
    rows = [
        _extra_row(URL="https://s.test/p1", **{"Content Images": [{"url": shared_url, "alt": ""}]}),
        _extra_row(URL="https://s.test/p2", **{"Content Images": [{"url": shared_url, "alt": ""}]}),
    ]
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(200))
    session.get = MagicMock(return_value=_get_response(200, _png_bytes(800, 600)))

    await enrich_content_image_inventory(session, rows, workers=3)

    session.head.assert_called_once()  # probed once, not once per referencing row


@pytest.mark.asyncio
async def test_enrich_broken_image_populates_count_and_urls() -> None:
    row = _extra_row(
        URL="https://s.test/p1",
        **{"Content Images": [{"url": "https://s.test/broken.jpg", "alt": ""}]},
    )
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(404))
    session.get = MagicMock(side_effect=AssertionError("should not run after failed HEAD"))

    await enrich_content_image_inventory(session, [row], workers=3)

    assert row.values["Broken Image Count"] == 1
    assert row.values["Has Broken Images"] is True
    assert row.values["Broken Image URLs"] == "https://s.test/broken.jpg"


@pytest.mark.asyncio
async def test_enrich_caps_broken_urls_joined_string_at_three() -> None:
    urls = [f"https://s.test/broken{i}.jpg" for i in range(5)]
    row = _extra_row(
        URL="https://s.test/p1",
        **{"Content Images": [{"url": u, "alt": ""} for u in urls]},
    )
    session = MagicMock()
    session.head = MagicMock(return_value=_head_response(404))

    await enrich_content_image_inventory(session, [row], workers=3)

    assert row.values["Broken Image Count"] == 5
    assert row.values["Broken Image URLs"].count("|") == 2  # 3 URLs joined = 2 separators
