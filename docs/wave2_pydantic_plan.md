# Wave 2 Pydantic Plan (Batch Mapping)

## Scope and constraints

- Goal: replace loose row dictionaries with strict Pydantic contracts in small, safe batches.
- Guardrail: keep changes additive, preserve existing `main_data` and `extra_rows` keys, and keep the `excel_engine` facade stable.
- Batch policy: no more than three files per implementation batch.

## Current loose-dict assembly map

### Crawler layer

1. `src/hype_frog/crawler/data_assembler.py`
   - `init_rows()` creates both `main_data` and `extra` as large `dict[str, Any]` payloads.
   - `assemble_from_html()` mutates both dictionaries through extraction and enrichment.
   - `finalize_row_state()` performs final state mutation and consistency sync.
2. `src/hype_frog/crawler/fetcher.py`
   - `fetch_and_parse()` orchestrates crawl + parse and passes mutable dicts through:
     - `main_data, extra = init_rows(...)`
     - `assemble_from_html(main_data=main_data, extra=extra, ...)`
     - `finalize_row_state(main_data, extra)`
   - Returns nested loose payload: `{"main": main_data, "extra": extra}`.

### Reporter layer

1. `src/hype_frog/reporter/engine_io.py`
   - `load_cached_rows()` builds `list[dict[str, Any]]` for `main_rows` and `extra_rows`.
   - `build_core_dataframes()` converts those dict lists into pandas DataFrames.
   - `write_dict_rows_sheet()` and `write_cached_sheet_chunked()` consume dict rows by column name.
2. `src/hype_frog/reporter/engine_rows.py` and `src/hype_frog/reporter/summary_builder.py`
   - Build downstream reporting rows from `extra_rows` and `main_rows` using `row.get(...)`.
   - Function signatures currently advertise `list[dict[str, Any]]` or `list[dict[str, object]]`.
3. `src/hype_frog/reporter/excel_engine.py`
   - Facade re-exports dict-based row helpers from `engine_io`/`engine_rows`.
   - This module should remain API-stable while internals migrate to typed models.

## Phased migration strategy (max 3 files per batch)

### Phase 1: Introduce contracts only (no behavioural changes)

- Add/extend row models in `src/hype_frog/models.py` (for main row, extra row, link detail row).
- Add model conversion helpers in `src/hype_frog/crawler/data_assembler.py` (dict -> model and model -> dict adapters).
- Add focused tests for model validation in `tests/hype_frog/crawler/test_data_assembler_models.py`.

### Phase 2: Type crawler assembly boundary

- Update `src/hype_frog/crawler/data_assembler.py` to build model instances internally.
- Update `src/hype_frog/crawler/fetcher.py` to pass model instances across parse/finalise functions.
- Keep fetcher return shape backward-compatible by serialising to dict at boundary (`model_dump`).

### Phase 3: Type reporter ingestion boundary

- Update `src/hype_frog/reporter/engine_io.py` to parse cached dict payloads into row models at load time.
- Update `src/hype_frog/reporter/engine_rows.py` to accept typed rows (or a narrow protocol) and only serialise when writing.
- Keep public exports in `src/hype_frog/reporter/excel_engine.py` unchanged to protect current callers.

### Phase 4: Type summary/dashboard builders

- Update `src/hype_frog/reporter/summary_builder.py` to consume typed extra rows.
- Update `src/hype_frog/reporter/sheets/dashboard.py` for typed metric payloads where currently `dict[str, Any]`.
- Add/extend unit tests around summary and dashboard row computation.

### Phase 5: Contract hardening and cleanup

- Replace remaining `dict[str, Any]` signatures in crawler/reporter with concrete model types.
- Add invariant tests for required fields and safe defaults (especially extraction state and action-required fields).
- Remove transitional adapter helpers only after all call sites are typed.

## Test-first priorities for next batch

1. Add offline unit tests around `init_rows()`, `assemble_from_html()`, and `finalize_row_state()` using fixture HTML.
2. Validate that model defaults preserve current workbook semantics.
3. Confirm `excel_engine` exports and report tabs remain unchanged via existing regression tests.
