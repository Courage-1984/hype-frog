"""Crawl row extraction-state and export sanitisation contracts."""

from __future__ import annotations

import re

from hype_frog.crawler.data_assembler import finalize_row_state, init_rows
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.export import sanitize_excel_string, sanitize_rows

_EXTRACTION_STATES: frozenset[str] = frozenset({"complete", "partial", "skipped"})


def test_extraction_state_literals_are_three_way_contract() -> None:
    main_payload, extra_payload = init_rows("https://example.com/", None)
    finalize_row_state(main_payload, extra_payload)
    state = str(main_payload.values.get("Extraction State", "")).lower()
    assert state in _EXTRACTION_STATES


def test_sanitize_excel_string_strips_illegal_control_characters() -> None:
    dirty = "Title\x0bwith\x07controls"
    cleaned = sanitize_excel_string(dirty)
    assert isinstance(cleaned, str)
    assert "\x0b" not in cleaned
    assert "\x07" not in cleaned
    assert "Title" in cleaned


def test_sanitize_rows_never_injects_null_strings_for_missing_values() -> None:
    main_payload, extra_payload = init_rows("https://example.com/page", None)
    MainRowPayload.model_validate(main_payload.values)
    ExtraRowPayload.model_validate(extra_payload.values)
    rows = sanitize_rows([main_payload.values])
    row = rows[0]
    for key, value in row.items():
        assert value is not None, f"Key {key!r} became None after sanitise"
        if isinstance(value, str):
            assert "null" != value.lower().strip()
