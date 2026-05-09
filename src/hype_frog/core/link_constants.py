"""Shared link and anchor text constants (crawler, pipeline, reporter)."""

from __future__ import annotations

GENERIC_ANCHOR_TERMS: frozenset[str] = frozenset(
    {"click here", "read more", "link", "here", "this"}
)

__all__ = ["GENERIC_ANCHOR_TERMS"]
