# hype-frog Test Suite Audit Report

**Date:** 2026-06-27  
**Original baseline:** 621 passed · 1 skipped · 2 deprecation warnings  
**After phase 1:** 717 passed · 0 skipped · 0 deprecation warnings (+96 tests)  
**After phase 2:** 766 passed · 0 skipped · 0 deprecation warnings (+49 tests)  
**Current baseline:** **771 passed · 0 skipped · 0 deprecation warnings** (+150 net vs original)  
**Phase 3 added:** +5 tests closing critical/high pipeline integration gaps

Verified with:

```powershell
uv run pytest --collect-only -q   # 771 tests collected
uv run pytest -W error::DeprecationWarning
```

---

## Executive Summary

The hype-frog test suite was audited for completeness, correctness, and coverage gaps across three phases.

**Phase 1** fixed a production bug (`datetime.utcnow()` deprecation), resolved a permanently skipped delta-engine test, and added 96 tests across three previously untested critical modules (`AuditCache`, Pydantic validators, freshness extraction) plus expansions to discovery order, crawl log, and checkpoint store.

**Phase 2** closed every medium- and low-priority gap from the original audit, plus partial high/critical coverage via focused unit tests (async HTTP mocks for `link_checks` and `competitor_benchmarks`; pure-function tests for enrichment/export orchestration helpers).

**Phase 3** added offline integration tests for `run_enrichment` and `execute_export` (main-only and full-suite workbook paths), plus smoke tests for the `crawler/engine.py` public re-export surface. All gaps identified in the original audit are now **closed** at unit or integration level.

**Optional follow-up (not blocking):** deeper Playwright browser-session tests in `crawler/network_engine.py` (already has 38 tests) and `extractors/eeat` edge-case expansion.

---

## Phase 1 — What Was Done

### 1. Bug Fix — `datetime.utcnow()` Deprecation (`checkpoint/store.py`)

**File:** `src/hype_frog/checkpoint/store.py`, line 50  
**Problem:** `datetime.utcnow()` is deprecated in Python 3.12 and scheduled for removal. This generated two deprecation warnings on every test run.  
**Fix:** Replaced with `datetime.now(timezone.utc)`.

```python
# Before (broken)
from datetime import datetime
"saved_at": datetime.utcnow().isoformat() + "Z",

# After (correct)
from datetime import datetime, timezone
"saved_at": datetime.now(timezone.utc).isoformat(),
```

The timestamp is still a valid ISO 8601 string; it now includes `+00:00` instead of a bare appended `Z`.

---

### 2. Skipped Test Fixed — `test_load_legacy_xlsx_snapshot_handles_nan_counts`

**File:** `tests/analysis/test_delta_engine.py`  
**Problem:** Test depended on a production workbook not committed to the repo. Permanently skipped in all CI runs.  
**Fix:** Replaced with an in-memory `openpyxl` workbook that replicates the exact sheet structure and the NaN-in-Summary shape that originally motivated the test.

---

### 3. New Test File — `tests/checkpoint/test_cache.py` (15 tests)

`AuditCache` (the SQLite durable crawl store) had **zero test coverage**. New tests cover DB init, upsert/conflict, iteration, chunked iteration, and close/cleanup behaviour.

---

### 4. New Test File — `tests/core/test_models_validators.py` (50 tests)

Strict Pydantic validators in `core/models.py` — previously untested. Covers `HttpCrawlResultModel`, `PSIMetricsModel`, `GSCMetricsModel`, `SummaryMetricsPayload`, and `harden_page_row_metrics`.

---

### 5. New Test File — `tests/extractors/test_freshness.py` (17 tests)

`extractors/freshness.py` had zero test coverage. Covers HTTP header extraction, article meta tags, schema fallback chain, and all five freshness classification buckets.

---

### 6. Expanded — `tests/core/test_discovery_order.py` (+6 tests)

Direct tests for `build_url_rank_index` and `order_main_and_extra_rows` edge cases.

---

### 7. Expanded — `tests/core/test_crawl_log.py` (+5 tests in phase 1)

Covers empty-entry guard, explicit timestamp, recovery-action coercion, sheet rows with real entries, and column completeness.

---

### 8. Expanded — `tests/checkpoint/test_store.py` (+4 tests)

Covers `saved_at` timezone format, legacy `completed_urls` fallback, and zero-results checkpoint round-trip.

---

## Phase 2 — Remaining Gap Closure (+49 tests)

### Medium priority — all closed

| Module | Tests added | Coverage |
|---|---|---|
| `validators/schema_validator.py` | +9 (now 11) | Article, Event, BreadcrumbList, Product (valid + invalid), `@graph`, malformed JSON |
| `core/models.py` | +1 (validators file now 50) | 15 pipe-separated `top_entities` parsed to list |
| `pipeline/og_image_validation.py` | +3 (now 4) | JPEG, WebP VP8X, unknown format → `None` |
| `config_loader.py` | +2 (now 5) | Malformed YAML and top-level non-dict YAML → `{}` |
| `analysis/content_similarity.py` | +5 (now 7) | `simhash_distance`, `enrich_content_similarity`, `SIMHASH_AVAILABLE=False` path |
| `analysis/topical_authority.py` | +3 (now 4) | `_tokenize`, `_build_idf`, `_top_tfidf_terms` |
| `extractors/semantic_setup.py` | **New file, 3 tests** | `probe_semantic_engine` — spaCy missing, model missing, ready |

### Low priority — all closed

| Module | Tests added | Coverage |
|---|---|---|
| `core/status_normalisation.py` | +2 (now 7) | `200.0` → `200`, `200.5` → `None` |
| `core/crawl_log.py` | +1 (now 8) | Multi-entry `to_row_dicts` |
| `rules/playbook_entries.py` | +1 (now 2) | All registry rules produce complete playbook rows |
| `reporter/workbook_audit.py` | +2 (now 4) | `require_full_suite_sheets=True` — missing and present core tabs |

### High priority — partial (mocked async)

| Module | Tests added | Coverage |
|---|---|---|
| `crawler/link_checks.py` | **New file, 4 tests** | HEAD success, GET fallback, total failure, semaphore limiting |
| `analysis/competitor_benchmarks.py` | +4 (now 5) | `_normalise_domain`, `_extract_page_signals`, `benchmark_competitor_domains` (mocked session) |

### Critical priority — partial (pure helpers)

| Module | Tests added | Coverage |
|---|---|---|
| `orchestration/enrichment_flow.py` | 7 helper tests | `normalize_url_key`, GSC inspection gate, inspection row merge |
| `orchestration/export_flow.py` | 2 helper tests | `normalize_url_key`, `ExportSummary` dataclass |

---

## Phase 3 — Pipeline Integration (+5 tests)

Offline integration tests reuse the synthetic fixtures and network patches from `diagnostics/full_smoke_fixtures.py` — no live HTTP, GSC OAuth, or Playwright.

| Module | Tests added | Coverage |
|---|---|---|
| `orchestration/enrichment_flow.py` | +1 (now 8) | `test_run_enrichment_offline_pipeline` — full `run_enrichment` on 3 synthetic URLs; asserts row counts, extraction state, SEO health scores |
| `orchestration/export_flow.py` | +2 (now 4) | `test_execute_export_main_only_writes_workbook` (Main + TOC); `test_execute_export_full_suite_writes_core_sheets` (all `REQUIRED_FULL_SUITE_SHEETS`, passes `audit_workbook`) |
| `crawler/engine.py` | **New file, 2 tests** | Public re-export surface (`__all__` symbols resolve and match canonical implementations in `client`, `fetcher`, `link_checks`, etc.) |

**Note:** `crawler/engine.py` is a thin re-export facade, not the Playwright implementation. Rendered-fetch logic lives in `crawler/network_engine.py` and is already covered by 38 async tests.

---

## Remaining Coverage Gaps (Prioritised)

All critical, high, medium, and low gaps from the original audit are **closed**.

| Priority | Module | Optional follow-up |
|---|---|---|
| Optional | `crawler/network_engine.py` | Deeper Playwright session edge cases beyond existing 38 tests |
| Optional | `extractors/eeat.py` | Non-empty page fixtures (currently 2 empty-page tests only) |

---

## Test Quality Assessment

| Rating | Modules |
|---|---|
| **Excellent** | `rules/registry` (103 parametrized tests covering all 99 rules), `crawler/network_engine` (38 tests), `rules/scoring` (24+ boundary/NaN/inf tests), `crawler/psi_engine` (17 tests), `orchestration/crawl_runner` (24 BFS invariant tests) |
| **Good** | `orchestration/enrichment_flow` (8 tests incl. offline pipeline), `orchestration/export_flow` (4 tests incl. full-suite export), `crawler/data_assembler`, `crawler/gsc_engine`, `crawler/engine` (re-export surface), `extractors/semantic_engine`, `reporter/html_report_data`, `reporter/narrative_engine`, `reporter/html_report_writer`, `core/api_clients`, `pipeline/content_duplicates`, `checkpoint/cache`, `core/models` validators, `extractors/freshness`, `validators/schema_validator`, `crawler/link_checks`, `analysis/competitor_benchmarks` |
| **Adequate** | `crawler/sitemap`, `analysis/delta_engine`, `pipeline/broken_links`, `pipeline/graph_engine`, `reporter/pdf_exporter`, `core/url_normalization`, `core/scoring`, `core/discovery_order`, `core/crawl_log`, `checkpoint/store`, `analysis/content_similarity`, `analysis/topical_authority`, `pipeline/og_image_validation`, `config_loader`, `rules/playbook_entries`, `reporter/workbook_audit`, `extractors/semantic_setup` |
| **Still weak (optional)** | `extractors/eeat` (2 tests, empty-page only) |

---

## Files Changed

### Production

| File | Change |
|---|---|
| `src/hype_frog/checkpoint/store.py` | Fixed `datetime.utcnow()` → `datetime.now(timezone.utc)` |

### Phase 1 — tests

| File | Change |
|---|---|
| `tests/checkpoint/test_cache.py` | **New** — 15 tests for `AuditCache` |
| `tests/checkpoint/test_store.py` | +4 tests |
| `tests/core/test_models_validators.py` | **New** — 50 tests for Pydantic validators |
| `tests/core/test_crawl_log.py` | +5 tests (phase 1) |
| `tests/core/test_discovery_order.py` | +6 tests |
| `tests/extractors/test_freshness.py` | **New** — 17 tests |
| `tests/analysis/test_delta_engine.py` | Replaced skipped test with in-memory openpyxl fixture |

### Phase 2 — tests

| File | Change |
|---|---|
| `tests/validators/test_schema_validator.py` | +9 tests |
| `tests/core/test_models_validators.py` | +1 test |
| `tests/pipeline/test_og_image_validation.py` | +3 tests |
| `tests/config/test_config_loader.py` | +2 tests |
| `tests/analysis/test_content_similarity.py` | +5 tests |
| `tests/analysis/test_topical_authority.py` | +3 tests |
| `tests/extractors/test_semantic_setup.py` | **New** — 3 tests |
| `tests/core/test_status_normalisation.py` | +2 tests |
| `tests/core/test_crawl_log.py` | +1 test |
| `tests/rules/test_playbook_entries.py` | +1 test |
| `tests/reporter/test_workbook_audit.py` | +2 tests |
| `tests/crawler/test_link_checks.py` | **New** — 4 async tests |
| `tests/analysis/test_competitor_benchmarks.py` | +4 tests |
| `tests/orchestration/test_enrichment_flow.py` | **New** — 7 helper tests |
| `tests/orchestration/test_export_flow.py` | **New** — 2 helper tests |

### Phase 3 — tests

| File | Change |
|---|---|
| `tests/orchestration/test_enrichment_flow.py` | +1 integration test (`run_enrichment` offline pipeline) |
| `tests/orchestration/test_export_flow.py` | +2 integration tests (`execute_export` main-only and full-suite) |
| `tests/crawler/test_engine.py` | **New** — 2 re-export surface tests |

---

## How to Run the Tests

```powershell
# Full suite (771 tests)
uv run pytest

# Phase 3 pipeline integration tests
uv run pytest tests/orchestration/test_enrichment_flow.py tests/orchestration/test_export_flow.py tests/crawler/test_engine.py -v

# Phase 1 additions
uv run pytest tests/checkpoint/test_cache.py tests/core/test_models_validators.py tests/extractors/test_freshness.py -v

# Phase 2 additions
uv run pytest tests/validators/test_schema_validator.py tests/crawler/test_link_checks.py tests/extractors/test_semantic_setup.py -v

# Deprecation guard (must pass cleanly)
uv run pytest -W error::DeprecationWarning
```

**Note:** A default `-W default` run may still surface occasional `ResourceWarning` entries (unclosed openpyxl handles in delta-engine fixtures, SSL sockets in async tests). These are not deprecation warnings and do not fail the deprecation guard above.
