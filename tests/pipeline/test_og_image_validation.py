"""Tests for OG image dimension probing (A1)."""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.core.models import ExtraRowPayload
from hype_frog.pipeline.og_image_validation import (
    _fetch_og_image_probe,
    enrich_og_image_validation,
    og_image_validation_summary,
    read_image_dimensions,
)


def _minimal_png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


def _minimal_jpeg(width: int, height: int) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", height, width)
        + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
        + b"\xff\xd9"
    )


def _minimal_webp_vp8x(width: int, height: int) -> bytes:
    w = width - 1
    h = height - 1
    payload = (
        b"\x00"
        + b"\x00\x00\x00"
        + bytes([w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF])
        + bytes([h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF])
    )
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    body = b"WEBP" + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_read_image_dimensions_png() -> None:
    assert read_image_dimensions(_minimal_png(1200, 630)) == (1200, 630)


def test_read_image_dimensions_jpeg() -> None:
    assert read_image_dimensions(_minimal_jpeg(800, 600)) == (800, 600)


def test_read_image_dimensions_webp() -> None:
    assert read_image_dimensions(_minimal_webp_vp8x(1200, 630)) == (1200, 630)


def test_read_image_dimensions_unknown_format_returns_none() -> None:
    assert read_image_dimensions(b"GIF89a not supported here") is None


def _minimal_webp_vp8_lossy(width: int, height: int) -> bytes:
    return b"RIFF\x00\x00\x00\x00WEBP" b"VP8 " + b"\x00" * 10 + struct.pack("<HH", width, height)


def test_read_image_dimensions_webp_lossy_vp8() -> None:
    """The non-extended ``VP8 `` (lossy) WebP variant — distinct code path
    from the ``VP8X`` (extended) case already covered above."""
    assert read_image_dimensions(_minimal_webp_vp8_lossy(1200, 630)) == (1200, 630)


def test_read_image_dimensions_empty_bytes_returns_none() -> None:
    assert read_image_dimensions(b"") is None


def test_read_image_dimensions_png_signature_but_truncated_returns_none() -> None:
    """PNG signature matches but the buffer is cut before width/height bytes
    — must not raise, must return None."""
    truncated = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
    assert read_image_dimensions(truncated) is None


# ---------------------------------------------------------------------------
# _fetch_og_image_probe
# ---------------------------------------------------------------------------


def _fake_response(status: int, body: bytes = b"") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.content = MagicMock()
    response.content.read = AsyncMock(return_value=body)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.mark.asyncio
async def test_fetch_og_image_probe_success_with_dimensions() -> None:
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(200, _minimal_png(1200, 630)))

    status, width, height = await _fetch_og_image_probe(
        session, "https://example.com/og.png", asyncio.Semaphore(1)
    )

    assert status == 200
    assert (width, height) == (1200, 630)


@pytest.mark.asyncio
async def test_fetch_og_image_probe_non_success_status_skips_dimension_read() -> None:
    session = MagicMock()
    response = _fake_response(404, b"")
    session.get = MagicMock(return_value=response)

    status, width, height = await _fetch_og_image_probe(
        session, "https://example.com/missing.png", asyncio.Semaphore(1)
    )

    assert status == 404
    assert width is None
    assert height is None
    response.content.read.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_og_image_probe_success_but_unparseable_body() -> None:
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(200, b"not image bytes"))

    status, width, height = await _fetch_og_image_probe(
        session, "https://example.com/weird.bin", asyncio.Semaphore(1)
    )

    assert status == 200
    assert width is None
    assert height is None


@pytest.mark.asyncio
async def test_fetch_og_image_probe_transport_exception_returns_all_none() -> None:
    session = MagicMock()
    session.get = MagicMock(side_effect=RuntimeError("connection refused"))

    status, width, height = await _fetch_og_image_probe(
        session, "https://example.com/og.png", asyncio.Semaphore(1)
    )

    assert (status, width, height) == (None, None, None)


# ---------------------------------------------------------------------------
# enrich_og_image_validation
# ---------------------------------------------------------------------------


def _extra_row(**values: object) -> ExtraRowPayload:
    return ExtraRowPayload(values=dict(values))


@pytest.mark.asyncio
async def test_enrich_og_image_validation_writes_ok_and_dimensions() -> None:
    row = _extra_row(**{"OG Image URL": "https://example.com/og.png"})
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(200, _minimal_png(1200, 630)))

    await enrich_og_image_validation(session, [row], workers=3)

    assert row.values["OG Image OK"] is True
    assert row.values["OG Image Width"] == 1200
    assert row.values["OG Image Height"] == 630
    assert row.values["OG Image Dimensions OK"] is True


@pytest.mark.asyncio
async def test_enrich_og_image_validation_wrong_dimensions_flagged_false() -> None:
    """1200x630 is dead-centre of the accepted band; a far-off aspect ratio
    must come back ``Dimensions OK: False`` while still reporting real
    width/height (distinguishing 'broken' from 'wrong size')."""
    row = _extra_row(**{"OG Image URL": "https://example.com/tiny.png"})
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(200, _minimal_png(100, 100)))

    await enrich_og_image_validation(session, [row], workers=3)

    assert row.values["OG Image OK"] is True
    assert row.values["OG Image Dimensions OK"] is False


@pytest.mark.asyncio
async def test_enrich_og_image_validation_broken_image_sets_ok_false_no_dimensions() -> None:
    row = _extra_row(**{"OG Image URL": "https://example.com/missing.png"})
    session = MagicMock()
    session.get = MagicMock(return_value=_fake_response(404, b""))

    await enrich_og_image_validation(session, [row], workers=3)

    assert row.values["OG Image OK"] is False
    assert row.values["OG Image Width"] is None


@pytest.mark.asyncio
async def test_enrich_og_image_validation_transport_failure_sets_ok_false() -> None:
    row = _extra_row(**{"OG Image URL": "https://example.com/og.png"})
    session = MagicMock()
    session.get = MagicMock(side_effect=RuntimeError("boom"))

    await enrich_og_image_validation(session, [row], workers=3)

    assert row.values["OG Image OK"] is False


@pytest.mark.asyncio
async def test_enrich_og_image_validation_skips_rows_without_og_image() -> None:
    row = _extra_row()  # no OG Image URL / OG Image / OG-Image at all
    session = MagicMock()
    session.get = MagicMock(side_effect=AssertionError("should never fetch"))

    await enrich_og_image_validation(session, [row], workers=3)

    assert row.values["OG Image OK"] is None
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_og_image_validation_no_targets_returns_early() -> None:
    session = MagicMock()
    session.get = MagicMock(side_effect=AssertionError("should never fetch"))

    await enrich_og_image_validation(session, [_extra_row(), _extra_row()], workers=3)

    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_og_image_validation_processes_multiple_rows_independently() -> None:
    good_row = _extra_row(**{"OG Image URL": "https://example.com/good.png"})
    bad_row = _extra_row(**{"OG Image URL": "https://example.com/bad.png"})
    session = MagicMock()
    responses = {
        "https://example.com/good.png": _fake_response(200, _minimal_png(1200, 630)),
        "https://example.com/bad.png": _fake_response(500, b""),
    }
    session.get = MagicMock(side_effect=lambda url, **_kwargs: responses[url])

    await enrich_og_image_validation(session, [good_row, bad_row], workers=3)

    assert good_row.values["OG Image OK"] is True
    assert bad_row.values["OG Image OK"] is False


# ---------------------------------------------------------------------------
# og_image_validation_summary
# ---------------------------------------------------------------------------


def test_og_image_validation_summary_counts_checked_broken_and_wrong_dims() -> None:
    rows = [
        _extra_row(**{"OG Image OK": True, "OG Image Width": 1200, "OG Image Dimensions OK": True}),
        _extra_row(**{"OG Image OK": False}),
        _extra_row(
            **{"OG Image OK": True, "OG Image Width": 100, "OG Image Dimensions OK": False}
        ),
        _extra_row(),  # never checked
    ]

    summary = og_image_validation_summary(rows)

    assert summary == {"checked": 3, "broken": 1, "wrong_dimensions": 1}


def test_og_image_validation_summary_empty_rows() -> None:
    assert og_image_validation_summary([]) == {"checked": 0, "broken": 0, "wrong_dimensions": 0}
