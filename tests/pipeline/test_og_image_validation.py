"""Tests for OG image dimension probing (A1)."""

from __future__ import annotations

import struct

from hype_frog.pipeline.og_image_validation import read_image_dimensions


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
