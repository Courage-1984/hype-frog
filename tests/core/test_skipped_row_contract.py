"""Skipped-row contract: blank content fields, never fake zeros."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.skipped_row_contract import apply_skipped_row_contract
from hype_frog.crawler.data_assembler import finalize_row_state


def test_apply_skipped_row_contract_clears_content_metrics() -> None:
    main = MainRowPayload.model_validate({"Extraction State": "skipped"})
    extra = ExtraRowPayload.model_validate({"Extraction State": "skipped"})
    apply_skipped_row_contract(main.values, extra.values)
    assert extra.values["H1 Count"] is None
    assert extra.values["Schema Types Count"] is None
    assert extra.values["Paragraphs 40-60 Words Count"] is None
    assert extra.values["Image Alt Coverage (%)"] is None
    assert extra.values["Status Code"] is None or extra.values.get("Status Code") is not None


def test_finalize_row_state_applies_contract_for_skipped() -> None:
    main = MainRowPayload.model_validate({"Extraction State": "skipped", "Status Code": 200})
    extra = ExtraRowPayload.model_validate({"Extraction State": "skipped", "Status Code": 200})
    finalize_row_state(main, extra)
    assert extra.values["H1 Count"] is None
    assert extra.values["Word Count"] is None


def test_scorable_rows_keep_extracted_values() -> None:
    main = MainRowPayload.model_validate({"Extraction State": "partial"})
    extra = ExtraRowPayload.model_validate(
        {"Extraction State": "partial", "H1 Count": 1, "Schema Types Count": 3}
    )
    apply_skipped_row_contract(main.values, extra.values)
    assert extra.values["H1 Count"] == 1
    assert extra.values["Schema Types Count"] == 3
