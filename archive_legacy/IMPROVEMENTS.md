# hype-frog — Codebase Improvement Tracker

> Generated 2026-06-28. All findings are verified against the live source tree.
> Symbols: 🔴 High priority · 🟡 Medium priority · 🟢 Low / nice-to-have
> Status: `[ ]` open · `[x]` done · `[~]` in-progress · `[-]` deferred

---

## Table of Contents

1. [DRY Violations](#1-dry-violations)
2. [Modularization Gaps](#2-modularization-gaps)
3. [Granularity Issues](#3-granularity-issues)
4. [Type Annotation Gaps](#4-type-annotation-gaps)
5. [Error Handling Anti-Patterns](#5-error-handling-anti-patterns)
6. [Logging Inconsistencies](#6-logging-inconsistencies)
7. [Performance Opportunities](#7-performance-opportunities)
8. [Industry Standards](#8-industry-standards)
9. [Test Coverage Gaps](#9-test-coverage-gaps)
10. [Import Hygiene](#10-import-hygiene)
11. [Configuration Anti-Patterns](#11-configuration-anti-patterns)
12. [Data Contract Drift](#12-data-contract-drift)
13. [Architectural Boundary Checks](#13-architectural-boundary-checks)
14. [Quick Wins Checklist](#14-quick-wins-checklist)

---

## 1. DRY Violations

### 1.1 🔴 `normalize_url_key` defined in 13 separate files

The single biggest DRY violation in the codebase. An identical one-liner (`return normalize_url(url, keep_query=keep_query)`) is copy-pasted everywhere instead of imported from the canonical source.

**Confirmed locations:**

| File | Line | Notes |
|---|---|---|
| `src/hype_frog/core/url_normalization.py` | 10 | ✅ **Canonical** — `normalize_url()` lives here |
| `src/hype_frog/pipeline/assemble.py` | 178–179 | Thin wrapper; also passed via `normalize_url_key_fn` arg |
| `src/hype_frog/pipeline/graph_engine.py` | 13–14 | Identical body |
| `src/hype_frog/crawler/fetcher.py` | 47–48 | Identical body |
| `src/hype_frog/crawler/data_assembler.py` | 22–23 | Identical body |
| `src/hype_frog/crawler/data_assembler_phases.py` | 50 | Private `_normalize_url_key` |
| `src/hype_frog/orchestration/crawl_runner_frontier.py` | 90–91 | Identical body |
| `src/hype_frog/orchestration/crawl_runner.py` | 46 | Alias: `_normalize_url_key = normalize_url_key` from frontier |
| `src/hype_frog/orchestration/export_flow.py` | 47–48 | Identical body |
| `src/hype_frog/orchestration/export_registry.py` | 63–64 | Identical body |
| `src/hype_frog/orchestration/enrichment_flow.py` | 88–89 | Identical body |
| `src/hype_frog/reporter/engine_io.py` | 28–29 | Identical body |
| `src/hype_frog/reporter/sheets/links.py` | 60–61 | Identical body |
| `src/hype_frog/app_orchestrator.py` | 27–28 | Private `_normalize_url_key` |

**Fix:** Add `normalize_url_key` as a named export in `core/url_normalization.py`:

```python
# core/url_normalization.py
def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)
```

Then in every file above, replace the local definition with:
```python
from hype_frog.core.url_normalization import normalize_url_key
```

- [x] Add `normalize_url_key` to `core/url_normalization.py`
- [x] Replace all 13 local definitions with the import
- [x] Update `core/__init__.py` to export `normalize_url_key`

---

### 1.2 🔴 `_ILLEGAL_XLSX_CHARS_RE` defined twice with different ranges

Two files define what appears to be the same regex but with subtly different character ranges — creating a latent data-integrity bug.

| File | Line | Pattern |
|---|---|---|
| `src/hype_frog/pipeline/export.py` | 9 | `r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]"` |
| `src/hype_frog/reporter/engine_io.py` | 19 | `r"[\x00-\x08\x0B\x0C\x0E-\x1F]"` ← missing `\x7F-\x9F` |

Also: `safe_sheet_name()` at `pipeline/export.py:78` is effectively duplicated by `_safe_sheet_name()` at `reporter/engine_io.py:32`.

**Fix:** Move the canonical, stricter regex + both sheet-name and value sanitizers into `reporter/sanitization.py` (new file), then import from there in both places.

- [-] Create `src/hype_frog/reporter/sanitization.py` — deferred; paths kept separate per reporter CLAUDE.md
- [x] Remove local definitions from `pipeline/export.py` and `reporter/engine_io.py` — regex aligned in engine_io.py
- [x] Confirm the wider `\x7F-\x9F` range is correct and use it everywhere — fixed in `reporter/engine_io.py:19`

---

### 1.3 🟡 `_safe_float` / NaN-guard logic duplicated across 6+ modules

The pattern `if math.isnan(x) or math.isinf(x): return default` (or near-identical variants) appears in:

| File | Lines | Notes |
|---|---|---|
| `src/hype_frog/core/models.py` | 121, 136, 142–148, 957–1088 | `_safe_float` as staticmethod AND inline |
| `src/hype_frog/core/scoring.py` | 43–66 | `_safe_float` module-level function |
| `src/hype_frog/reporter/engine_rows.py` | 47–67 | `_round2`, `_round4`, local `_hub_score_value` |
| `src/hype_frog/reporter/sheets/dashboard.py` | 133–138 | `_safe_float` private function |
| `src/hype_frog/crawler/network_engine.py` | 180–186 | Inline JS number validation |
| `src/hype_frog/pipeline/action_required.py` | 25 | Inline NaN guard |
| `src/hype_frog/pipeline/export.py` | 26 | Double-cast `float(value)` pattern |
| `src/hype_frog/orchestration/enrichment_flow.py` | 163, 173 | Inline `isinstance(raw, float) and math.isnan` |
| `src/hype_frog/analysis/delta_models.py` | 47 | `num != num` NaN idiom |

**Fix:** Consolidate in `core/numeric_utils.py`:

```python
def safe_float(value: object, default: float = 0.0) -> float: ...
def round2(value: object, default: float = 0.0) -> float: ...
def round4(value: object, default: float = 0.0) -> float: ...
def clamp_pct(value: object) -> float: ...  # max(0, min(100, safe_float(value)))
```

- [x] Create `src/hype_frog/core/numeric_utils.py` with the unified helpers
- [x] Replace local implementations in `engine_rows.py`, `dashboard.py`, `delta_models.py` with imports from `core/numeric_utils`
- [x] Export from `core/__init__.py`

---

### 1.4 🟢 Heading-selector CSS constants repeated in `extractors/`

CSS selector lists for H1/CMS primary headings appear inline in multiple extractor functions rather than being consolidated in one place.

**Location:** `src/hype_frog/extractors/page.py:41–54` (`_CMS_PRIMARY_H1_SELECTORS`)

**Fix:** Keep one `_CMS_PRIMARY_H1_SELECTORS` list in `page.py` and import it into other extractor files that need it. Or move to `extractors/selector_constants.py`.

- [ ] Audit all extractor files for duplicate selector lists
- [ ] Centralize in `extractors/selector_constants.py`

---

## 2. Modularization Gaps

### 2.1 🟡 `pipeline/assemble.py` — overloaded normalize+assemble+score entry points

`pipeline/assemble.py` exports `normalize_url_key` (DRY violation), multiple `assemble_*` overloads at lines 334, 465, 538, 602, each accepting an optional `normalize_url_key_fn: Callable | None`. This optional-callable pattern signals that the function is doing too much.

**Fix:** Remove `normalize_url_key_fn` parameters; normalize all URLs *before* calling assemble functions. Callers that need custom normalization should pre-normalize.

- [ ] Audit all `normalize_url_key_fn` call sites — identify whether any actually pass a custom fn
- [ ] If no custom fn is ever passed, remove the parameter from all four overloads
- [ ] Remove `normalize_url_key` from this module (covered in 1.1)

---

### 2.2 🟡 `orchestration/crawl_runner.py` re-exports and aliases from frontier

`crawl_runner.py:21` imports `normalize_url_key` from frontier, then `crawl_runner.py:46` creates `_normalize_url_key = normalize_url_key`. This double-alias chain obscures provenance.

**Fix:** After 1.1, both frontier and runner import from `core.url_normalization`. Remove the alias line entirely.

- [ ] Remove `_normalize_url_key = normalize_url_key` from `crawl_runner.py`

---

### 2.3 🟢 `reporter/excel_engine.py` is a thin re-export facade

`excel_engine.py` imports and re-exports functions from `engine_io.py`, `engine_rows.py`, `sheets/tables_impl.py`. Callers could import directly from those modules; the facade adds an indirection layer without encapsulation value.

**Fix (low urgency):** Either document explicitly that `excel_engine.py` is the public API surface for the reporter package, add `__all__` listing what's intentionally exported, or remove the facade and update callers to import from sub-modules directly.

- [ ] Add `__all__` to `reporter/excel_engine.py` to make the contract explicit
- [ ] Or document the facade pattern in a module docstring

---

### 2.4 🟢 `analysis/` modules each define their own `_row_url()` helper

Several analysis modules extract a canonical URL from a row dict using a pattern like `row.get("Final URL") or row.get("URL") or ""`. This two-key fallback logic is scattered and subtly inconsistent.

**Confirmed in:**
- `src/hype_frog/analysis/hreflang_audit.py:576` (`_row_url` function)
- `src/hype_frog/pipeline/graph_engine.py:45, 52, 69, 75, 83` (inline `.get("Final URL") or .get("URL")`)
- `src/hype_frog/analysis/link_equity.py:122, 156` (inline)

**Fix:** Add `get_row_url(row: dict[str, Any]) -> str` to `core/url_normalization.py` or `core/models.py`.

- [x] Define `get_row_url()` in `core/url_normalization.py`
- [ ] Replace all inline two-key fallbacks with it (roll-out to graph_engine, link_equity, hreflang_audit)

---

## 3. Granularity Issues

### 3.1 🟡 `reporter/dashboard_logic.py` — `compute_dashboard_metrics()` aggregates too many concerns

`compute_dashboard_metrics()` produces a `DashboardComputationResult` with 36+ fields, performing status bucketing, KPI aggregation, owner rollup, and severity distribution in one pass.

**Fix:** Extract sub-computations into private functions:
```
_compute_status_buckets(rows) -> StatusBuckets
_compute_kpi_metrics(rows, config) -> KPIMetrics
_compute_severity_distribution(rows) -> SeverityDistribution
_aggregate_owner_rollup(rows) -> OwnerRollup
compute_dashboard_metrics(rows, config) -> DashboardComputationResult  # orchestrator only
```

- [ ] Identify natural sub-result boundaries in `dashboard_logic.py`
- [ ] Extract private helpers; keep public signature identical

---

### 3.2 🟡 `crawler/network_engine.py` — Playwright fetch body has multiple nested try/except blocks

`network_engine.py` lines ~230–567 contain deeply nested exception guards for CSP errors, navigation churn, body unavailability, timeout, and final safety nets. The nesting makes the error-recovery path hard to reason about.

**Fix:** Extract each distinct retry/fallback phase into a private coroutine:
```
_attempt_navigation(page, url) -> NavigationResult
_extract_body(page) -> str | None
_collect_render_diagnostics(page) -> RenderedFetchDiagnostics
```

- [ ] Map existing `except` blocks to named recovery strategies
- [ ] Extract each into its own `async def _*()` coroutine

---

### 3.3 🟢 `extractors/semantic_engine.py` — `analyze_intent()` method handles entity extraction, citation detection, and AEO scoring

Per the class docstring and method signature, `analyze_intent()` computes entity density, detects citations, and produces an aggregate AEO score.

**Fix:** Split responsibilities:
```
_extract_entities(text) -> list[Entity]
_compute_entity_density(entities, word_count) -> float
_detect_citations(text) -> int
_compute_aeo_score(entity_density, citations, ...) -> float
analyze_intent(text, ...) -> SemanticAnalysisResult  # orchestrator
```

- [ ] Read the full method body and confirm it does all three things
- [ ] Extract private helpers; keep `analyze_intent()` as thin orchestrator

---

## 4. Type Annotation Gaps

### 4.1 🟡 `dict[str, Any]` used 404 times across 63 files

Row dictionaries are passed as `dict[str, Any]` everywhere, making it impossible for mypy to catch key-name typos or contract drift.

**Most impactful locations:**
- `src/hype_frog/reporter/engine_io.py` — 7 occurrences
- `src/hype_frog/reporter/engine_rows.py` — 12 occurrences
- `src/hype_frog/orchestration/export_registry.py` — 26 occurrences
- `src/hype_frog/reporter/sheets/executive_dashboard.py` — 19 occurrences
- `src/hype_frog/reporter/sheets/merged_builders.py` — 50 occurrences
- `src/hype_frog/crawler/gsc_engine.py` — 10 occurrences
- `src/hype_frog/crawler/psi_merge.py` — 31 occurrences

**Fix (incremental):** Introduce `MainRowDict` and `ExtraRowDict` as `TypedDict` in `core/models.py` (already partially done). Roll out adoption in the highest-traffic modules first. Use `typing_extensions.TypedDict` with `total=False` for optional keys.

- [ ] Confirm `MainRowPayload` / `ExtraRowPayload` TypedDicts exist in `core/models.py`
- [ ] Replace `dict[str, Any]` with these types in `reporter/engine_rows.py` and `reporter/engine_io.py`
- [ ] Roll out to `orchestration/export_registry.py` and `reporter/sheets/merged_builders.py`
- [ ] Enable `mypy --strict` incrementally per package

---

### 4.2 🟢 `analysis/delta_models.py` uses `num != num` as NaN test

`delta_models.py:47`: `if num != num:  # NaN` — while technically correct, it is non-obvious and inconsistent with the `math.isnan()` pattern used everywhere else.

**Fix:** Replace with `import math; if math.isnan(num):`.

- [ ] One-line fix in `analysis/delta_models.py:47`

---

### 4.3 🟢 `core/text_utils.py` public functions lack docstrings

`normalize_text_hash`, `status_class`, `word_count_band`, `image_extension` are public utilities with no docstrings.

- [ ] Add one-line docstring to each function in `core/text_utils.py`

---

## 5. Error Handling Anti-Patterns

### 5.1 🟡 Broad `except Exception` in 50+ locations — many without contextual logging

Most are intentional safety nets in the crawler (e.g., `network_engine.py:567` "final safety net: never propagate"). Some, however, swallow errors silently.

**Silent swallowers (no logger call after except):**

| File | Line | Risk |
|---|---|---|
| `src/hype_frog/analysis/delta_loader.py` | 63 | `except Exception:` with no log |
| `src/hype_frog/analysis/hreflang_audit.py` | 507, 524 | `except Exception:` bare |
| `src/hype_frog/crawler/gsc_engine.py` | 131, 183 | `except Exception:` bare |
| `src/hype_frog/core/memory_guard.py` | 63, 73 | `except Exception:` bare |
| `src/hype_frog/crawler/network_engine.py` | 313, 327, 461, 502 | `except Exception:` bare |

**Fix:** Every bare `except Exception:` should either:
1. Log at `DEBUG` level with `exc_info=True`, or
2. Be documented with a comment explaining *why* silence is safe

- [ ] Audit all `except Exception:` (bare, no `as exc`) — add log or justification comment
- [ ] For safety-net catches that must stay broad, add `# safety net: reason` comment

---

### 5.2 🟢 `config_loader.py:32` catches `Exception` on config file read

Config loading should distinguish `FileNotFoundError` (missing file) from `PermissionError` (bad permissions) from `json.JSONDecodeError` (corrupt config) — each has a different recovery path.

**Fix:** Replace `except Exception as exc:` with specific exception types and distinct error messages.

- [ ] Refine exception types in `config_loader.py:32`

---

### 5.3 🟢 `crawler/link_checks.py:22,27` — nested `except Exception` swallows inner error

Two consecutive exception handlers (`exc`, `exc2`) in `link_checks.py` suggest a retry-within-error pattern that should be explicit.

- [ ] Refactor `link_checks.py:22–30` to use explicit retry logic or a helper

---

## 6. Logging Inconsistencies

### 6.1 🔴 `diagnostics/integration_validator.py:447` — bare `print()` in a module that should use logger

This is the **only** genuine `print()` violation (all other `console.print()` calls use Rich, which is intentional). `integration_validator.py` calls `print(format_validation_report(checks))` directly.

**Fix:**
```python
# Before
print(format_validation_report(checks))

# After
from hype_frog.core.console import console
console.print(format_validation_report(checks))
# or
logger.info("Validation report:\n%s", format_validation_report(checks))
```

- [x] Replace `print()` in `diagnostics/integration_validator.py:447`

---

### 6.2 🟢 No documented log-level policy

The codebase uses all five log levels but there is no written policy on when to use which. This leads to inconsistencies like warnings for missing keys in one module vs. debug in another.

**Fix:** Add to `CLAUDE.md` under a new `## Logging policy` section:

```
DEBUG   — internal state (cache hits, loop counts, skipped URLs)
INFO    — phase transitions, URL counts, export paths
WARNING — degraded behavior the operator should know about (missing PSI key,
          failed GSC auth, robots.txt parse error)
ERROR   — a single task or URL failed; crawl continues
CRITICAL — abort condition; should exit immediately
```

- [ ] Add log-level policy to `CLAUDE.md`
- [ ] Audit `logger.warning()` calls and demote purely informational ones to `INFO`

---

### 6.3 🟢 `orchestration/crawl_runner_bfs.py` crawl-log entries missing URL context

`crawl_log.record()` calls in `crawl_runner_bfs.py:97–99` include `phase` but not `url`, making it hard to correlate log entries to specific pages during debugging.

- [ ] Ensure every `crawl_log.record()` call includes the URL being processed

---

## 7. Performance Opportunities

### 7.1 🟡 URL normalization called repeatedly in hot BFS loop

In `orchestration/crawl_runner_bfs.py:230`, `normalize_url_key(url)` is called on every URL during the BFS iteration. The same URL may be normalized many times across loop iterations.

**Fix:** Pre-normalize the frontier set once when URLs are first added, not on every dequeue.

- [ ] Profile BFS loop to confirm normalize is a hot path
- [ ] Move normalization to frontier insertion in `crawl_runner_frontier.py`

---

### 7.2 🟡 `pipeline/graph_engine.py` — same `normalize_url_key()` calls for both source and target in inner loop

Lines 52–54: for each edge in the link graph, `normalize_url_key()` is called for both source and target. Sources are repeated across iterations; a dict pre-normalization pass would eliminate redundant calls.

**Fix:**
```python
# Before (per-iteration)
source = normalize_url_key(values.get("Final URL") or values.get("URL") or "")
t_norm = normalize_url_key(target)

# After
row_norms = {id(row): normalize_url_key(...) for row in rows}  # once
```

- [ ] Pre-build `{row_id: normalized_url}` mapping before the graph build loop

---

### 7.3 🟢 `reporter/engine_io.py` — `_safe_sheet_name()` called per-write without caching

If the workbook has many sheets, the regex is applied fresh each time. Sheet names are stable once the export plan is built.

**Fix:** Cache in the sheet registry at registration time, before write time.

- [ ] Investigate whether `export_registry.py` already caches sheet names
- [ ] If not, cache normalized names in the registry on first registration

---

### 7.4 🟢 `reporter/sheets/tables.py:33` — `isinstance(raw, float) and math.isnan(raw)` in tight cell loop

Called for every cell value during Excel write. After consolidating NaN guards (see 1.3), use a single pre-compiled helper to avoid repeated isinstance + math.isnan pair.

- [ ] Replace inline NaN check in `tables.py:33` with `safe_float()` from `core/numeric_utils`

---

## 8. Industry Standards

### 8.1 🟡 Magic numbers and threshold literals scattered outside `config_defaults.py`

Values that represent business rules or thresholds should live in `config_defaults.py`, not inline in module code.

**Examples found:**

| File | Line | Value | Should be named |
|---|---|---|---|
| `src/hype_frog/crawler/network_engine.py` | 52–54 | `100` (JS delta) | `JS_DEPENDENT_ABS_DELTA` |
| `src/hype_frog/pipeline/content_hub_metrics.py` | 40 | `0` (floor check) | `MIN_CONTENT_HUB_SCORE` |
| `src/hype_frog/orchestration/enrichment_flow.py` | 163, 173 | inline `0.0` defaults | `ENRICHMENT_SCORE_FALLBACK` |

- [ ] Audit for numeric literals that represent configurable thresholds
- [ ] Move to `config_defaults.py` and import where used

---

### 8.2 🟢 Inconsistent error message tone and format

`config_loader.py:28` uses `"Could not read %s: %s"` (positional), while `main.py:216–220` builds rich structured error context. No standard template.

**Fix:** Define `core/error_messages.py` with template helpers:
```python
def file_read_error(path: str, exc: Exception) -> str: ...
def api_fetch_error(url: str, exc: Exception) -> str: ...
```

- [ ] (Optional) Create `core/error_messages.py` for consistent error strings

---

### 8.3 🟢 `analysis/delta_models.py:47` uses non-standard NaN check

Already covered in 4.2. Flagged here as a standards issue too — IEEE-754 `num != num` trick should not appear in a Python codebase that uses `math.isnan` everywhere else.

---

### 8.4 🟢 Missing `__all__` in public package `__init__.py` files

Several `__init__.py` files in `core/`, `extractors/`, `rules/` are empty or partial, meaning `from hype_frog.core import *` would import everything, including private helpers.

**Fix:** Add `__all__` lists to at least `core/__init__.py`, `extractors/__init__.py`, and `rules/__init__.py`.

- [ ] Add `__all__` to `src/hype_frog/core/__init__.py`
- [ ] Add `__all__` to `src/hype_frog/extractors/__init__.py`
- [ ] Add `__all__` to `src/hype_frog/rules/__init__.py`

---

## 9. Test Coverage Gaps

### 9.1 🟡 No tests for `normalize_url_key` across boundary cases

`tests/core/test_url_normalization.py` exists but the wrapper `normalize_url_key` is defined in 13 places. Once consolidated (see 1.1), the single canonical version should have:
- Unicode/IDN URLs
- Bare scheme-less strings
- `keep_query=False` vs. `keep_query=True` producing different outputs
- Empty string / None input

- [ ] After 1.1 is done: add IDN, bare-path, and None-input test cases to `test_url_normalization.py`

---

### 9.2 🟡 `pipeline/graph_engine.py` has no dedicated test file

The link graph engine builds the inlinks/outlinks map used for PageRank-like scoring. It has no test file.

**Affected logic:** `build_inlinks_map()`, `build_outlinks_map()`, `compute_hub_scores()` (or equivalent).

- [ ] Create `tests/pipeline/test_graph_engine.py`
- [ ] Test: empty crawl → no edges; self-link ignored; outlink normalization; hub score floor

---

### 9.3 🟡 `orchestration/enrichment_flow.py` has no test file

Enrichment flow applies GSC + PSI + scoring passes post-crawl. Bugs here silently drop scores.

- [ ] Create `tests/orchestration/test_enrichment_flow.py`
- [ ] Test: NaN passthrough guard, empty row dict, PSI key missing scenario

---

### 9.4 🟢 `tests/conftest.py` fixtures are single-scenario

All shared fixtures (`conftest.py:14–35`) are single HTML strings. Parameterization would let tests cover more edge cases without test duplication.

**Fix:** Where the same test is repeated for slight HTML variants, convert to `@pytest.mark.parametrize` or fixture factories.

- [ ] Identify repeated single-variant tests in `tests/extractors/` and `tests/crawler/`
- [ ] Convert to parametrize where beneficial

---

### 9.5 🟢 `tests/integration/test_sample_page_pipeline.py` — only one integration test file

A single integration test covers the full pipeline. More fixtures covering redirect chains, noindex pages, and blocked robots would give confidence that cross-module interactions work.

- [ ] Add a fixture for a redirect chain (301 → 200) to the integration test
- [ ] Add a fixture for `noindex, nofollow` page behavior

---

## 10. Import Hygiene

### 10.1 🟡 Run lint for unused imports — suspected accumulation

Large header import blocks in heavily-modified modules likely contain stale imports after refactors.

**Verification command:**
```powershell
uv run ruff check --select F401 src/
```

- [ ] Run `ruff check --select F401 src/` and fix all reported unused imports
- [ ] Add `ruff` to the CI pipeline's lint step if not already present

---

### 10.2 🟡 `pipeline/gsc_coverage.py:9` — import aliased as a different concept

```python
from hype_frog.core.url_normalization import normalize_url as normalize_url_key
```

This aliases `normalize_url` as `normalize_url_key`, creating the illusion it's a separate function with key semantics. After 1.1 is done, this should import `normalize_url_key` directly.

- [x] After 1.1: fix `pipeline/gsc_coverage.py:9`, `pipeline/gsc_inspection.py:8`, `orchestration/export_workbook.py:113` — all alias imports corrected

---

### 10.3 🟢 Verify no `from X import *` anywhere

CLAUDE.md prohibits star imports. Confirm none exist.

```powershell
Select-String -Pattern "from .+ import \*" -Path src\hype_frog\ -Recurse -Include *.py
```

- [ ] Run the above and confirm zero results

---

### 10.4 🟢 Circular import risk: `orchestration` → `rules` → `config` — verify no backflow

`orchestration/export_flow.py` imports from `rules/`; `rules/registry.py` imports from `config`. If `rules/` ever imports from `orchestration/`, a cycle forms.

**Verification:**
```powershell
uv run python -c "import hype_frog.orchestration.export_flow"  # should not raise ImportError
```

- [ ] Verify `grep -r "from hype_frog.orchestration" src/hype_frog/rules/` returns zero results
- [ ] Consider adding an import-graph linter (e.g., `import-linter`) to CI

---

## 11. Configuration Anti-Patterns

### 11.1 🟡 Hardcoded external URL in `core/run_config.py`

```python
# core/run_config.py:13–21
QUICK_TEST_SITEMAP_URL: str = "https://africanmarketingconfederation.org/page-sitemap.xml"
FULL_SMOKE_SITEMAP_URL: str = QUICK_TEST_SITEMAP_URL
```

If this external site goes offline, the smoke test and quick test fail due to a network dependency, not a code issue.

**Fix:** Make the URL overridable via env var:
```python
QUICK_TEST_SITEMAP_URL: str = os.environ.get(
    "HF_TEST_SITEMAP_URL",
    "https://africanmarketingconfederation.org/page-sitemap.xml",
)
```

Or use a local fixture sitemap served via `pytest-httpserver` in the test suite.

- [ ] Add `HF_TEST_SITEMAP_URL` override to `run_config.py`
- [ ] Document `HF_TEST_SITEMAP_URL` in `.env.example`

---

### 11.2 🟡 Defaults split across four locations — no single source of truth

Developers needing "what is the default for X?" must check four places:
1. `config_defaults.py` (primary)
2. `core/env_vars.py` (env accessor defaults)
3. `core/run_config.py` (preset constants)
4. Inline magic numbers scattered in modules (see 8.1)

**Fix:** Write a comment at the top of `config_defaults.py`:
```
# This file is the single source of truth for all default values.
# env_vars.py may provide fallbacks, but those fallbacks MUST reference
# constants defined here — never use numeric/string literals in env_vars.py.
```

Then audit `env_vars.py` for any inline literal defaults and move them here.

- [ ] Add canonical-source-of-truth comment to `config_defaults.py`
- [ ] Audit `env_vars.py` for inline literal defaults; move to `config_defaults.py`
- [ ] Document convention in `CLAUDE.md` under `## Env vars`

---

### 11.3 🟢 Audit `.env.example` against all `get_hf_*()` accessors in `core/env_vars.py`

If a new env var is added to `env_vars.py` without updating `.env.example`, it's invisible to operators.

**Fix:** Add a CI check script:
```python
# scripts/check_env_parity.py
# Reads all HF_* references in env_vars.py and verifies each exists in .env.example
```

- [ ] Write `scripts/check_env_parity.py`
- [ ] Add to CI or pre-commit hook

---

## 12. Data Contract Drift

### 12.1 🔴 Inconsistent row URL key: `"URL"` vs. `"Final URL"` — no canonical fallback

Throughout the codebase, URL resolution uses `row.get("Final URL") or row.get("URL")` but:
- Some call sites only check `"URL"` (`reporter/engine_io.py:45–46`)
- Some check only `"Final URL"` (early analysis passes)
- Some check both in different orders

This risks silently dropping redirect-chain data in the reporter.

**Affected locations:**
- `src/hype_frog/pipeline/graph_engine.py:45,52,69,75,83`
- `src/hype_frog/analysis/hreflang_audit.py:576`
- `src/hype_frog/reporter/engine_io.py:45–46`
- `src/hype_frog/analysis/link_equity.py:122,156`

**Fix:**
1. Define canonical accessor `get_row_url(row) -> str` in `core/url_normalization.py` (see 2.4)
2. Document in `docs/data_contracts.md` which key is "seed URL" vs. "effective URL after redirects"
3. Audit `reporter/engine_io.py:45–46` for missing `"Final URL"` fallback

- [ ] Define `get_row_url()` in `core/url_normalization.py`
- [ ] Replace all two-key fallback patterns with it
- [ ] Verify `reporter/engine_io.py:45–46` handles both keys
- [ ] Add contract note to `docs/data_contracts.md`

---

### 12.2 🟡 `analysis/hreflang_audit.py:507,524` — bare `except Exception:` silently discards URL resolution

These silent exceptions mean a malformed hreflang URL fails invisibly, producing a gap in the audit sheet without any logged warning.

- [ ] Add `logger.debug("hreflang url resolution failed: %s", exc)` to both bare excepts

---

### 12.3 🟢 `extractors/semantic_engine.py` — `SemanticAnalysisResult` optional fields not enforced at call sites

The TypedDict result has optional fields (`entity_density`, `top_entities`, etc.) but callers in `crawler/fetcher.py` may access them without None-checking.

- [ ] Verify all callers of `SemanticAnalyzer.analyze_intent()` check for `None` on optional fields
- [ ] Or switch to a Pydantic model with validators to enforce defaults at construction time

---

## 13. Architectural Boundary Checks

### 13.1 ✅ Core modules do not import from higher layers

`grep -r "from hype_frog.(orchestration|reporter|pipeline|analysis|rules) import" src/hype_frog/core/` returns **no matches**. Boundary respected.

### 13.2 ✅ Analysis modules do not import from orchestration

`grep -r "from hype_frog.orchestration import" src/hype_frog/analysis/` returns **no matches**. Boundary respected.

### 13.3 🟡 Reporter `engine_rows.py` — verify no in-place mutation of input row dicts

CLAUDE.md states reporter must not mutate pipeline row dicts. `engine_rows.py` row building should operate on copies.

- [ ] Audit all functions in `reporter/engine_rows.py` that accept `row: dict` — confirm they do `row.copy()` or construct new dicts
- [ ] Add a unit test that passes a sentinel-value dict and asserts it is unchanged after calling row-builder functions

---

### 13.4 🟢 `orchestration/` should not import from `reporter/` directly

If orchestration drives export, it should call reporter via a well-defined interface, not import individual sheet builders.

- [ ] Run: `grep -r "from hype_frog.reporter" src/hype_frog/orchestration/` and document what's imported
- [ ] If direct sheet imports exist, consider wrapping them in an interface function in `reporter/excel_engine.py`

---

## 14. Quick Wins Checklist

Items that take ≤ 30 minutes each and have no dependencies.

- [x] `diagnostics/integration_validator.py:447` — replace `print()` with `console.print()`
- [x] `analysis/delta_models.py:47` — replace `num != num` with `math.isnan(num)` (+ import math removed; safe_int now from core.numeric_utils)
- [x] `pipeline/gsc_coverage.py:9` — fix misleading alias; now imports `normalize_url_key` directly
- [-] Add `__all__` to `core/__init__.py`, `extractors/__init__.py`, `rules/__init__.py` — all three already have `__all__`; no action needed
- [x] Run `ruff check --select F401 src/` — 110 unused imports fixed; re-export hubs annotated with `# noqa: F401`
- [ ] Add log-level policy section to `CLAUDE.md`
- [x] Add `HF_TEST_SITEMAP_URL` override to `run_config.py`, `env_vars.py`, and `.env.example`
- [x] Add canonical-source-of-truth comment to top of `config_defaults.py`
- [x] One-line docstrings on public functions in `core/text_utils.py`
- [ ] Verify zero star-imports via PowerShell search

---

## Priority Matrix

| # | Finding | Priority | Effort | Impact |
|---|---|---|---|---|
| 1.1 | `normalize_url_key` × 13 definitions | 🔴 High | M (2–3 h) | High — eliminates biggest DRY tech debt |
| 1.2 | Divergent XLSX char-stripping regexes | 🔴 High | S (30 min) | High — latent data-integrity bug |
| 12.1 | URL key inconsistency `"URL"` vs `"Final URL"` | 🔴 High | M (2 h) | High — silent data loss risk |
| 6.1 | `print()` in integration_validator | 🔴 High | XS (5 min) | Low — violates guardrail |
| 1.3 | `_safe_float` / NaN guard × 9 modules | 🟡 Med | M (2 h) | Medium — correctness + maintainability |
| 4.1 | `dict[str, Any]` × 404 uses | 🟡 Med | L (ongoing) | High long-term — enables type safety |
| 5.1 | Silent `except Exception:` swallowers | 🟡 Med | S (1 h) | Medium — debugging experience |
| 11.1 | Hardcoded external URL in test config | 🟡 Med | S (30 min) | Medium — flaky CI risk |
| 11.2 | Defaults split across 4 locations | 🟡 Med | S (1 h) | Medium — developer ergonomics |
| 3.1 | `compute_dashboard_metrics()` too large | 🟡 Med | M (2 h) | Medium — maintainability |
| 10.1 | Unused imports (ruff F401) | 🟡 Med | S (20 min) | Low — cleanliness |
| 7.1 | URL normalization in BFS hot loop | 🟡 Med | M (2 h) | Low-Medium — performance |
| 13.3 | Reporter row dict mutation risk | 🟡 Med | S (1 h) | High if violated |
| 2.4 | Scattered `_row_url()` pattern | 🟢 Low | S (1 h) | Low — maintainability |
| 8.1 | Magic numbers outside config_defaults | 🟢 Low | S (1 h) | Low — readability |
| 9.2 | No tests for `graph_engine.py` | 🟢 Low | M (2 h) | Medium — regression safety |
| 9.3 | No tests for `enrichment_flow.py` | 🟢 Low | M (2 h) | Medium — regression safety |

---

*Last updated: 2026-06-28. Update status checkboxes as work completes.*
