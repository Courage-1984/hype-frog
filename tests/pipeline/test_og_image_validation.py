"""Tests for OG image dimension probing (A1)."""

from __future__ import annotations

import struct

from hype_frog.pipeline.og_image_validation import read_image_dimensions


def _minimal_png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


def test_read_image_dimensions_png() -> None:
    data = _minimal_png(1200, 630)
    assert read_image_dimensions(data) == (1200, 630)
