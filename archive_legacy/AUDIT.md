# hype-frog — Full Codebase Audit
**Original audit date:** 2026-06-27  
**Fix-status update:** 2026-06-28  
**Auditor:** Claude Code (claude-sonnet-4-6)  
**Scope:** All Python source files under `src/hype_frog/`, supporting scripts, config, and tests  
**Method:** File-by-file static analysis + full test suite execution

---

## Fix Status Summary (2026-06-28)

Since the original audit, **all P0 bugs**, **most P1 performance/data-quality items**, **P3 deprecations**, and **the env-var contract (P2)** have been addressed. Remaining work is primarily **P4 design debt** (oversized functions, module splits) and **ongoing P5 hygiene** (broad exception handlers in non-critical paths).

| Priority | Original count | Status |
|---|---|---|
| P0 — Breaks functionality | 4 | **All fixed** |
| P1 — Performance / data quality | 8 | **All fixed** |
| P2 — Env-var contract violations | 45 across 12 files | **Resolved** via `core/env_vars.py` + `CliRunOverrides` / `RunConfig` injection |
| P3 — Datetime deprecations | 4 | **All fixed** |
| P4 — Design debt | 12 | **Partial** — dead duplicates/params removed; mega-functions remain |
| P5 — Silent error handling | 95 broad clauses | **Done** — key paths + reporter layer use `logger.debug` |
| P6 — Typing gaps | 9 functions | **Done** — public reporter/core helpers annotated |

**Test suite (2026-06-28):** all green, no deprecation warnings.

### P0 — Fixed

| # | File | Issue | Resolution |
|---|---|---|---|
| 1 | `scripts/crawl_matrix_audit.py:23` | Wrong import path | → `hype_frog.diagnostics.quick_test` |
| 2 | `crawler/network_engine.py:652–653` | TTFB = total time | Uses `headers_received_at` trace hook |
| 3 | `extractors/freshness.py:35–38` | Valid date overwritten | Guarded with `elif last_modified_raw is not None` |
| 4 | `crawler/sitemap.py:17` | No sitemap timeout | `ClientTimeout(total=10)` |

### P1 — Fixed

| # | File | Issue | Resolution |
|---|---|---|---|
| 5 | `core/models.py` | `deepcopy` on every row | Shallow `.copy()` in `MainRowPayload` / `ExtraRowPayload` |
| 6 | `crawler/data_assembler.py` | Double lxml parse | Single `BeautifulSoup` + `parse_html_signals_from_soup`; cached `get_text()` |
| 7 | `orchestration/crawl_runner.py` | Blocking `input()` in async | `_prompt_crawl_options` via `asyncio.to_thread` |
| 8 | `orchestration/export_flow.py:892` | Redundant graph recompute | `enrichment.graph_metrics` passed through |
| 9 | `core/models.py` | PSI string not coerced | `float(value)` in `_coerce_optional_psi_metrics` |
| 10 | `extractors/eeat.py:74` | Phone regex false positives | Tighter pattern with lookarounds + debug logging |

### P2 — Env-var contract (resolved)

All runtime env reads now flow through **`src/hype_frog/core/env_vars.py`** (single permitted reader alongside `config_loader.py` for YAML). Domain modules import typed getters — no direct `os.getenv` in crawler, orchestration, reporter, or core business logic.

**CLI overrides:** `main.py` no longer mutates `os.environ`. Flags are collected into `CliRunOverrides` and merged in `resolve_run_setup()`. Preset/matrix runs pass values via `RunConfig` fields (`output_filename`, `export_pdf`, `gsc_url_inspection`, etc.).

**Remaining env write:** `set_playwright_browsers_path()` in `env_vars.py` — the sole permitted runtime write (Playwright requires `PLAYWRIGHT_BROWSERS_PATH` for frozen builds).

### P3 — Fixed

All four `datetime.utcnow()` / `datetime.now().astimezone()` call sites now use `datetime.now(tz=timezone.utc)`.

### P4 — Remaining design debt

| # | File | Issue | Status |
|---|---|---|---|
| 1 | `crawler/data_assembler.py` | `assemble_from_html` ~420 lines | **Done** — coordinator + `data_assembler_phases.py` (12 phase helpers) |
| 2 | `orchestration/export_flow.py` | `execute_export` ~850 lines | **Done** — split into `export_flow.py` (~220), `export_workbook.py`, `export_executive_reports.py`, `export_workbook_constants.py` |
| 3 | `orchestration/crawl_runner.py` | `execute_crawl` ~490 lines | **Done** — coordinator (~150), `crawl_runner_frontier.py`, `crawl_runner_interactive.py`, `crawl_runner_bfs.py` |
| 4 | `app_orchestrator.py` | `_build_aioseo_rows` ~370 lines | **Done** — moved to `orchestration/export_row_builders.py` with phase helpers |
| 5 | `analysis/delta_engine.py` | 800 LOC mixed concerns | **Done** — facade + `delta_models.py`, `delta_loader.py`, `delta_sheet_builder.py` |
| 6 | `crawler/psi_engine.py` | 1,266 LOC | **Done** — facade + `psi_cache.py`, `psi_merge.py`, `psi_batch.py` |
| 7 | `crawler/engine.py` | Duplicate of `__init__.py` | **Removed** |
| 8 | `core/cli.py` | 9-tuple return | **Done** — `UserConfig` dataclass |
| 9 | `pipeline/graph_engine.py` | Dead `source_label` param | **Removed** |
| 10 | `pipeline/score.py` | Unused `passthrough_score_rows` | **Removed** |
| 11 | `analysis/delta_engine.py:503` | Unused `typed_extra_rows` param | **Removed** |
| 12 | `crawler/fetcher.py` | Dead `full_suite` param | **Removed** |

---

## Executive Summary (original audit)

| Metric | Value (2026-06-27) | Current (2026-06-28) |
|---|---|---|
| Source files audited | 131 Python files | 131 |
| Test suite result | 621 passed, 1 skipped | All green |
| Deprecation warnings (pytest) | 2 | **0** |
| `os.environ`/`os.getenv` violations outside permitted modules | 45 across 12 files | **0** (centralised in `env_vars.py`) |
| Broad `except Exception` / bare `except` clauses | 95 occurrences | **Reporter + crawl paths log at debug** |
| Confirmed bugs | 6 | **0 open** |
| Critical files | 6 | **0 open critical items** |

The codebase is functionally solid — module boundaries are respected, workbook integrity patterns are well-guarded, and the test suite is healthy. The dominant remaining concern is **maintainability of oversized functions** in orchestration, crawler assembly, and PSI.

---

## Test Suite Results

```
621+ passed, 1 skipped, 0 warnings (2026-06-28)
```

**Original warnings (fixed):**
```
tests/checkpoint/test_store.py — datetime.utcnow() deprecation
→ checkpoint/store.py now uses datetime.now(timezone.utc)
```

---

## Remaining Roadmap

### P4 — maintainability ✅ Complete (2026-06-28)

1. ~~Refactor `execute_export` (~850 lines) into phase functions~~ **Done**
2. ~~Refactor `assemble_from_html` (~420 lines) into phase helpers~~ **Done**
3. ~~Extract interactive vs async body in `execute_crawl`~~ **Done**
4. ~~Split `crawler/psi_engine.py` (1,266 LOC) into focused submodules~~ **Done**
5. ~~Split `analysis/delta_engine.py` into `delta_models.py`, `delta_loader.py`, `delta_sheet_builder.py`~~ **Done**
6. ~~Extract `_build_aioseo_rows` from `app_orchestrator.py`~~ **Done** — `orchestration/export_row_builders.py`

### P5/P6 — hygiene ✅ Complete (2026-06-28)

6. ~~Add `logger.debug` to remaining bare `except Exception: pass` blocks in non-critical paths~~ **Done** (crawler, analysis, reporter)
7. ~~Add type annotations to 9 identified public functions~~ **Done**
8. ~~Write tests for `scripts/crawl_matrix_audit.py`~~ **Done** — `tests/scripts/test_crawl_matrix_audit.py`
9. ~~Refactor `core/cli.py` 9-tuple → `UserConfig` dataclass~~ **Done**

---

## What Is Working Well

- **Test suite is healthy:** good coverage across all major modules with clear fixture patterns.
- **Module boundaries are respected:** `reporter/` does not mutate pipeline dicts; `analysis/` is read-only; `extractors/` does not write to the workbook.
- **Workbook integrity patterns are solid:** `engine_guardrails.py`, `workbook_audit.py`, and defensive openpyxl patterns in `sheets/`.
- **Env-var contract is centralised:** `core/env_vars.py` is the single reader; CLI flags inject via `CliRunOverrides` / `RunConfig`.
- **Checkpoint/cache system is clean:** SQLite UPSERT in `checkpoint/cache.py` is correct.
- **Rules engine is well-structured:** 99 rules with clean `IssueRule` contracts; rule-evaluation failures now log at `warning`.
- **Config defaults are comprehensive:** `config_defaults.py` + YAML loading in `config_loader.py`.

---

## Original File-by-File Findings

> **Note:** Sections below reflect the **2026-06-27** audit state. Items marked ✅ in the fix-status tables above supersede individual file notes. Unmarked items in this section may still be open — cross-check the **Fix Status Summary** first.

### `src/hype_frog/__init__.py` (~3 LOC) ✅ Good
No issues.

---

### `src/hype_frog/main.py` (~281 LOC) ✅ Fixed (2026-06-28)

1. ~~**Security/Contract — direct `os.environ` writes:**~~ **Fixed.** CLI flags collected into `CliRunOverrides` and passed to `app_orchestrator.main()`.

2. **Design:** `_parse_args` is ~185 lines of argparse boilerplate. Not a bug, but consider grouping flags into `add_argument_group` sections for readability.

---

### `src/hype_frog/app_orchestrator.py` ✅ Fixed (split)

1. **Design — oversized function:** ~~`_build_aioseo_rows` is ~370 lines.~~ **Done (2026-06-28).** AEO/AIOSEO row builders live in `orchestration/export_row_builders.py`; entrypoint is ~70 lines with re-exported aliases for tests.

2. ~~**Typing:** Nested `add_issue` closure lacks a return type annotation.~~ **Done** — `_AioseoIssueWriter.add_issue` in `export_row_builders.py`.

---

### `src/hype_frog/config.py` (~108 LOC) ✅ Good
1. **Typing (minor):** `resolve_project_relative_path` is missing an explicit `-> Path` return annotation.

---

### `src/hype_frog/config_defaults.py` (~210 LOC) ✅ Good
1. **Design (minor):** `get_large_image_size_kb` and `get_high_third_party_script_count` are public getters for keys absent from `USER_CONFIG_KEYS`.

---

### `src/hype_frog/config_loader.py` (~73 LOC) ✅ Good
1. **Error Handling (minor):** `_read_yaml` now logs warnings on parse/read failures.

---

### `src/hype_frog/core/api_clients.py` (~275 LOC) ✅ Fixed

1. ~~**Security/Contract — direct `os.getenv`:**~~ **Fixed.** Uses `env_vars.get_openai_api_key()` / `get_openai_model()`.

2. **Performance:** Callers should inject a shared `aiohttp.ClientSession` when calling `classify_search_intent_with_llm`.

---

### `src/hype_frog/core/env_vars.py` ✅ New (2026-06-28)

Centralised typed accessors for all environment variables. The **only** module (with `config_loader.py` for YAML) permitted to read `os.environ` / `os.getenv`. Includes `set_playwright_browsers_path()` for the single permitted runtime write.

---

### `src/hype_frog/core/cli.py` ✅ Fixed

1. ~~**Design:** `get_user_config` uses 9 blocking `input()` calls — consider `UserConfig` dataclass.~~ **Done (2026-06-28).** Returns frozen `UserConfig`; `run_setup` consumes typed fields.

---

### `src/hype_frog/core/models.py` (~1091 LOC) ✅ Fixed (performance + PSI coercion)

1. ~~**Performance — deepcopy on every row:**~~ **Fixed.** Shallow copy.

2. ~~**Bug — uncoerced PSI string:**~~ **Fixed.** `float(value)` coercion.

---

### `src/hype_frog/core/run_config.py` (~112 LOC) ✅ Fixed

1. ~~**Security/Contract — direct `os.getenv`:**~~ **Fixed.** Uses `env_vars`. Added `CliRunOverrides`, `output_filename`, `export_pdf` fields.

---

### `src/hype_frog/crawler/data_assembler.py` (~735 LOC) ⚠️ Partial

1. ~~**Performance — double HTML parse:**~~ **Fixed.** Single parse + cached text.

2. ~~**Design — oversized function:**~~ **Done (2026-06-28).** `assemble_from_html` is a ~50-line coordinator; phases live in `data_assembler_phases.py`.

---

### `src/hype_frog/crawler/engine.py` ✅ Removed (was duplicate of `crawler/__init__.py`)

---

### `src/hype_frog/crawler/fetcher.py` (~496 LOC) ✅ Fixed

1. ~~**Security/Contract — direct env read/write:**~~ **Fixed.** Reads via `env_vars`; writes via `set_playwright_browsers_path()`.

2. ~~**Bug — dead `full_suite` param:**~~ **Removed.**

---

### `src/hype_frog/crawler/network_engine.py` (~732 LOC) ✅ Fixed (TTFB)

1. ~~**Bug — TTFB equals total request time:**~~ **Fixed.**

2. **Performance — module-level asyncio.Semaphore at import time:** Low risk; monitor under pytest-asyncio.

---

### `src/hype_frog/crawler/sitemap.py` ✅ Fixed (timeout)

---

### `src/hype_frog/extractors/freshness.py` ✅ Fixed (date overwrite guard)

---

### `src/hype_frog/extractors/eeat.py` ✅ Fixed (phone regex + debug logging)

---

### `src/hype_frog/extractors/page.py` ✅ Improved

Added `parse_html_signals_from_soup()` for callers that already hold a `BeautifulSoup` tree.

---

### `src/hype_frog/orchestration/crawl_runner.py` ✅ Fixed (async input + env + split)

1. ~~**Security/Contract — direct `os.getenv`:**~~ **Fixed.** Uses `env_vars` + `RunSetup.output_filename`.

2. ~~**Bug — blocking `input()` in async:**~~ **Fixed.** `asyncio.to_thread`.

3. ~~**Design — oversized `execute_crawl`:**~~ **Done (2026-06-28).** Thin coordinator; frontier helpers in `crawl_runner_frontier.py`; interactive prompts in `crawl_runner_interactive.py`; BFS loop in `crawl_runner_bfs.py`. Test patch targets re-exported from `crawl_runner`.

---

### `src/hype_frog/orchestration/export_flow.py` ⚠️ Partial

1. ~~**Security/Contract — direct `os.getenv`:**~~ **Fixed.** Branding via `env_vars`; export flags via `RunSetup`.

2. ~~**Deprecation — datetime:**~~ **Fixed.**

3. ~~**Performance — redundant graph computation:**~~ **Fixed.**

4. **Design — `execute_export` ~850 lines:** **Done (2026-06-28).** Coordinator in `export_flow.py`; full-suite sheets in `export_workbook.py`; PDF/HTML in `export_executive_reports.py`.

---

### `src/hype_frog/orchestration/run_setup.py` ✅ Fixed

Merges `CliRunOverrides` into `RunSetup` for interactive runs.

---

### `src/hype_frog/analysis/delta_engine.py` ✅ Fixed (split)

1. ~~**Deprecation — datetime:**~~ **Fixed.**

2. ~~**Performance — repeated file open:**~~ **Fixed.** Reuses `pd.ExcelFile` object.

3. ~~**Bug — unused `typed_extra_rows` param:**~~ **Removed.**

4. ~~**Design — 800 LOC module split:**~~ **Done (2026-06-28).** Facade in `delta_engine.py`; models in `delta_models.py`; load/save in `delta_loader.py`; sheet builders in `delta_sheet_builder.py`.

---

### `src/hype_frog/checkpoint/store.py` ✅ Fixed (utcnow deprecation)

---

### `src/hype_frog/rules/scoring.py` ✅ Fixed (rule failure logging)

---

### `src/hype_frog/reporter/sheets/config.py` ✅ Fixed

Uses `env_vars` getters; all six `HF_DISABLE_*` / `HF_DEBUG_*` flags documented in `.env.example`.

---

### `scripts/crawl_matrix_audit.py` ✅ Fixed

1. ~~**Bug — broken import:**~~ **Fixed.**
2. ~~**Security/Contract — `os.environ` writes:**~~ **Fixed.** Passes `output_filename` via `RunConfig`.

---

### `.env.example` ✅ Complete

All previously missing vars (`HF_MAX_DEPTH`, `HF_OUTPUT_FILENAME`, `HF_DISABLE_*`, `HF_DEBUG_*`) are now documented.

---

## Original Prioritised Issue Registry

See **Fix Status Summary** at the top of this document for current state. The original P0–P3 items are resolved. P4–P6 items are tracked in **Remaining Roadmap**.
