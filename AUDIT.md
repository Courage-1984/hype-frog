# hype-frog — Full Codebase Audit
**Date:** 2026-06-27  
**Auditor:** Claude Code (claude-sonnet-4-6)  
**Scope:** All Python source files under `src/hype_frog/`, supporting scripts, config, and tests  
**Method:** File-by-file static analysis + full test suite execution

---

## Executive Summary

| Metric | Value |
|---|---|
| Source files audited | 131 Python files |
| Total source LOC | ~25,635 |
| Test suite result | **621 passed, 1 skipped** — all green |
| Deprecation warnings (pytest) | 2 (same root cause) |
| `os.environ`/`os.getenv` violations outside `config_loader.py` | **45 occurrences across 12 files** |
| Broad `except Exception` / bare `except` clauses | **95 occurrences** |
| Deprecated `datetime` APIs | **4 occurrences** |
| Confirmed bugs | **6** |
| Critical files | 6 |
| Files needing attention | 22 |
| Files in good health | ~103 |

The codebase is functionally solid — the test suite is healthy, module boundaries are largely respected, and workbook integrity patterns are well-guarded. The dominant systemic issue is **env-var access scattered across 12 modules** that should only flow through `config_loader.py` per CLAUDE.md. Secondary concerns are **95 broad exception clauses** that silently swallow errors, **4 deprecated datetime APIs**, and **6 confirmed logic bugs** including one script that will fail with `ModuleNotFoundError` on startup.

---

## Test Suite Results

```
621 passed, 1 skipped, 2 warnings in 16.09s
```

**Warnings (both same root cause):**
```
tests/checkpoint/test_store.py::test_checkpoint_save_load_round_trip
tests/checkpoint/test_store.py::test_checkpoint_delete_removes_file
  DeprecationWarning: datetime.datetime.utcnow() is deprecated …
  Use timezone-aware objects: datetime.datetime.now(datetime.UTC)
  → src/hype_frog/checkpoint/store.py:50
```

---

## File-by-File Findings

### `src/hype_frog/__init__.py` (~3 LOC) ✅ Good
No issues.

---

### `src/hype_frog/main.py` (~281 LOC) ⚠️ Needs Attention

1. **Security/Contract — direct `os.environ` writes (lines 257–275):** `main.py` writes eight env vars (`HF_COMPETITORS`, `HF_EXPORT_PDF`, `CHECK_OG_IMAGES`, `CHECK_CONTENT_IMAGES`, `HF_PREVIOUS_AUDIT_PATH`, `GSC_URL_INSPECTION`, `HF_MAX_MEMORY_MB`, `HF_STREAMING`) directly to `os.environ` before entering `_async_main`. CLAUDE.md designates `config_loader.py` as the sole env reader. These writes bypass that contract and create invisible runtime state mutations.

   **Fix:** Collect CLI overrides into a `CLIOverrides` dataclass and pass it explicitly to `app_orchestrator.run()` / `RunConfig`. Remove the `os.environ` mutations.

2. **Design:** `_parse_args` is ~185 lines of argparse boilerplate. Not a bug, but consider grouping flags into `add_argument_group` sections for readability.

---

### `src/hype_frog/app_orchestrator.py` (~523 LOC) ⚠️ Needs Attention

1. **Design — oversized function:** `_build_aioseo_rows` is ~370 lines, far exceeding the 50-line guideline in CLAUDE.md. It is the largest single function body in the non-reporter codebase.

   **Fix:** Extract logical phases (HTML fetch, signal extraction, row assembly, issue tagging) into private helpers called in sequence.

2. **Typing:** Nested `add_issue` closure inside `_build_aioseo_rows` lacks a return type annotation.

---

### `src/hype_frog/config.py` (~108 LOC) ✅ Good
1. **Typing (minor):** `resolve_project_relative_path` is missing an explicit `-> Path` return annotation.

---

### `src/hype_frog/config_defaults.py` (~210 LOC) ✅ Good
1. **Design (minor):** `get_large_image_size_kb` and `get_high_third_party_script_count` are public getters for keys absent from `USER_CONFIG_KEYS`. Calling `apply_runtime_override` with these keys raises `ValueError`. The inconsistency could confuse future contributors.

---

### `src/hype_frog/config_loader.py` (~73 LOC) ✅ Good
1. **Error Handling (minor):** `_read_yaml` catches broad `except Exception` and returns `{}`. Acceptable as a YAML fallback, but swallows genuinely unexpected errors (e.g., permission denied on config file) silently. Add a `logger.warning` at minimum.

---

### `src/hype_frog/core/api_clients.py` (~275 LOC) 🔴 Critical

1. **Security/Contract — direct `os.getenv` (lines 206, 218):** `os.getenv("OPENAI_API_KEY")` and `os.getenv("OPENAI_MODEL", "gpt-4o-mini")` in a `core/` module violate CLAUDE.md's env-var contract. `core/` modules should receive configuration as injected arguments, not read the environment directly.

   **Fix:** Accept `openai_api_key: str` and `openai_model: str` as parameters; wire from `config_loader.py`.

2. **Performance:** `classify_search_intent_with_llm` creates a new `aiohttp.ClientSession` per call when `session=None` (line 237). Sessions are expensive to create. Callers should always inject a shared session.

3. **Error Handling:** `except Exception as exc` at line 254 is acceptable for LLM fallback, but non-timeout paths deserve a `logger.debug` for diagnosability.

---

### `src/hype_frog/core/cli.py` (~97 LOC) ⚠️ Needs Attention

1. **Design:** `get_user_config` uses 9 blocking `input()` calls. This is appropriate for a CLI, but makes the function untestable without stdin mocking. Consider a thin wrapper pattern.

2. **Typing:** The 9-tuple return type is technically correct but unreadable. A `NamedTuple` (`UserConfig`) or `@dataclass` would improve maintainability and IDE support.

---

### `src/hype_frog/core/console.py` (~90 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/crawl_log.py` (~99 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/discovery_order.py` (~88 LOC) ⚠️ Needs Attention
1. **Typing:** `build_url_rank_index` and `_row_rank` both accept a `normalize_fn` parameter without type annotation. Should be `Callable[[str], str]`.

---

### `src/hype_frog/core/file_utils.py` (~27 LOC) ✅ Good
Uses `datetime.now(timezone.utc)` correctly (not deprecated `utcnow()`).

---

### `src/hype_frog/core/link_constants.py` (~10 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/logger.py` (~66 LOC) ⚠️ Needs Attention

1. **Design:** `logs_dir = Path("logs")` is relative to the process CWD. If hype-frog is invoked from a directory other than the project root (e.g., from `dist/`), logs will land in an unexpected location.

   **Fix:** Anchor the log path relative to the project root using `Path(__file__).resolve().parent.parent.parent / "logs"` or accept it as configuration.

2. **Design (minor):** `global _LOGGING_CONFIGURED` check-then-set is not thread-safe. Two threads could both pass the guard. Low risk in practice given asyncio's concurrency model, but worth noting.

---

### `src/hype_frog/core/memory_guard.py` (~107 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/models.py` (~1091 LOC) ⚠️ Needs Attention

1. **Performance — deepcopy on every row instantiation:** `deepcopy(MAIN_ROW_DEFAULTS)` and `deepcopy(EXTRA_ROW_DEFAULTS)` are called on every `MainRowPayload` and `ExtraRowPayload` construction. For a 500-URL crawl this is 1000+ deep copies of large dicts (~150+ keys each). This is likely the largest CPU hotspot in the model layer.

   **Fix:** Use `MAIN_ROW_DEFAULTS.copy()` (shallow) — all values are primitives (`None`, `str`, `int`, `bool`, `[]`), making a shallow copy safe. For the list values specifically, copy only those keys with `[]` defaults.

2. **Bug — uncoerced string through PSI metric validator:** `PageRowMetricsModel._coerce_optional_psi_metrics` returns the raw `value` unchanged on the success path. A string like `"85"` satisfies `isinstance(value, str)` but is **not** coerced to `int` despite the field being declared `int | None`. This means PSI score fields can silently hold strings downstream.

   **Fix:** Cast the value: `return int(value)` for the numeric branches.

3. **Design:** Line ~792 is an extremely long single-line `MAIN_ROW_DEFAULTS.update(...)` expression. Split across multiple `update()` calls or a plain dict literal for readability.

4. **Typing:** Nested `_safe_float` inside `harden_page_row_metrics` has no annotation.

---

### `src/hype_frog/core/run_config.py` (~112 LOC) 🔴 Critical

1. **Security/Contract — direct `os.getenv` (lines 53, 59, 70):** `RunConfig.__post_init__` calls `os.getenv("PSI_API_KEY", "")` twice and `os.getenv("HF_FULL_SMOKE_URL_COUNT", "")` once. `RunConfig` lives in `core/` and is constructed in multiple callsites. Env access should be resolved once in `config_loader.py` and injected into `RunConfig`.

   **Fix:** Add `psi_api_key: str` and `full_smoke_url_count: int` fields to `RunConfig`; set defaults through `config_loader.load_config()`.

---

### `src/hype_frog/core/scoring.py` (~149 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/status_codes.py` (~87 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/text_utils.py` (~106 LOC) ✅ Good
No issues.

---

### `src/hype_frog/core/url_normalization.py` (~23 LOC) ⚠️ Needs Attention
1. **Error Handling:** `normalize_url` catches `except Exception` and silently returns `raw.rstrip("/")` with no logging. URL parse failures should at minimum emit a `logger.debug`.

---

### `src/hype_frog/crawler/__init__.py` (~17 LOC) ⚠️ Needs Attention
1. **Design:** Content is an exact duplicate of `crawler/engine.py` (see below). One is dead code.

---

### `src/hype_frog/crawler/client.py` (~21 LOC) ⚠️ Needs Attention
1. **Typing:** `create_session` has no return type annotation. Should be `-> aiohttp.ClientSession`.

---

### `src/hype_frog/crawler/data_assembler.py` (~735 LOC) 🔴 Critical

1. **Performance — double HTML parse per URL (lines 307, 400):** `BeautifulSoup(html, "lxml")` is called twice on the same HTML string within `assemble_from_html`. lxml parsing is the most expensive per-URL operation; doubling it adds meaningful latency at scale.

   **Fix:** Parse once into a local `soup` variable at the top of the function and pass it to all downstream extractors.

2. **Performance — redundant `get_text()` calls:** `soup.get_text(...)` is called multiple times on the same soup object across different parts of the function. Cache the result into a local variable after the first call.

3. **Design — oversized function:** `assemble_from_html` is ~420 lines, the single largest function in the project. At this size it is effectively untestable in isolation and very hard to reason about.

   **Fix:** Extract logical phases: link extraction, meta extraction, heading extraction, body text analysis, schema extraction, regional signal extraction — each into a focused private function.

4. **Design — hardcoded constants in function body (lines 493–515):** A 22-item list of African regional terms is embedded mid-function. Move to a module-level constant `_AFRICAN_REGIONAL_TERMS`.

5. **Typing:** `assemble_from_html` lacks a `-> None` return annotation.

---

### `src/hype_frog/crawler/engine.py` (~20 LOC) ⚠️ Needs Attention
1. **Design — dead code:** This file is an exact content-duplicate of `crawler/__init__.py`. One of the two should be removed.

---

### `src/hype_frog/crawler/fetcher.py` (~496 LOC) 🔴 Critical

1. **Security/Contract — direct `os.environ` reads and write (lines 458–470):** `configure_playwright_browsers_path` reads `os.environ.get("PLAYWRIGHT_BROWSERS_PATH")` and `os.environ.get("LOCALAPPDATA")`, then writes `os.environ["PLAYWRIGHT_BROWSERS_PATH"]`. Env mutation in a domain module.

2. **Bug — silently discarded parameter:** `fetch_and_parse` accepts `full_suite: bool = True` (line 159) then immediately executes `del full_suite` (line 180). The parameter appears meaningful to callers but does nothing. This is confusing API surface.

   **Fix:** Either remove the parameter or implement its intended behaviour.

3. **Design — oversized function:** `fetch_and_parse` is ~260 lines.

---

### `src/hype_frog/crawler/gsc_engine.py` (~569 LOC) ⚠️ Needs Attention

1. **Performance — duplicate URL indexing:** `_rows_to_page_metrics` stores each URL under both raw and normalized keys pointing to the same dict object. This doubles the dict size for large GSC exports.

2. **Performance — sequential URL inspections:** `fetch_gsc_url_inspections_batch` inspects URLs one at a time with no concurrency. For batches of 50+ URLs this is a significant latency bottleneck. Consider `asyncio.gather` with a semaphore.

---

### `src/hype_frog/crawler/link_checks.py` (~32 LOC) ⚠️ Needs Attention
1. **Error Handling:** `check_url_status_light` has two bare `except Exception` clauses that return `None` with no logging. Failed link checks are silently dropped.

---

### `src/hype_frog/crawler/network_engine.py` (~732 LOC) ⚠️ Needs Attention

1. **Bug — TTFB equals total request time (lines 652–653):** Both `ttfb_ms` and `total_request_ms` are assigned `round((time.time() - request_start) * 1000, 2)`. True TTFB requires capturing the timestamp when response headers first arrive (i.e., before reading the body). The current implementation makes the TTFB column in the workbook meaningless — it reports the same value as total response time.

   **Fix:** Use `aiohttp`'s `on_response_start` trace hook or capture `time.time()` immediately after `await session.get(...)` returns (before `await resp.read()`).

2. **Performance — module-level asyncio.Semaphore at import time:** Creating a `Semaphore` at module level can cause `DeprecationWarning` or failures in Python 3.10+ when the semaphore is created outside an event loop. Under `pytest-asyncio`, tests using separate event loops may hit `RuntimeError`.

3. **Style:** `out != out` NaN check (line 185) — `math.isnan(out)` is more readable and standard.

---

### `src/hype_frog/crawler/psi_engine.py` (~1266 LOC) ⚠️ Needs Attention

1. **Security/Contract — direct `os.getenv("PSI_API_KEY")` (line 85):** Same env-var contract violation as `run_config.py`.

2. **Design — oversized functions:** `_fetch_strategy_raw` (~100 lines), `fetch_psi_metrics_batch` with nested `_worker` (~110 lines), and `_merge_url_results` (~90 lines) all exceed the 50-line guideline.

3. **Note:** At 1,266 lines this is the largest single file in the project. Consider whether PSI caching, batch management, and metric merging belong in separate modules.

---

### `src/hype_frog/crawler/redirect_chain.py` (~192 LOC) ✅ Good
No issues.

---

### `src/hype_frog/crawler/robots_mapping.py` (~279 LOC) ✅ Good
No issues.

---

### `src/hype_frog/crawler/sitemap.py` (~134 LOC) ⚠️ Needs Attention

1. **Bug/Performance — missing timeout on sitemap fetch (line 17):** `_fetch_sitemap_xml` calls `session.get(url)` with no explicit timeout. A hanging sitemap server will block the crawl indefinitely.

   **Fix:** Add `timeout=aiohttp.ClientTimeout(total=10)`.

2. **Design (minor):** `_strip_default_namespace` applies a regex to the raw XML string. This is fragile if the namespace appears on inner elements and may mangle namespace-prefixed attributes.

---

### `src/hype_frog/extractors/__init__.py` (~23 LOC) ⚠️ Needs Attention
1. **Design:** `parse_jsonld_summary` is imported from `.schema` but missing from `__all__`. Callers relying on `from extractors import *` will not get it.

---

### `src/hype_frog/extractors/eeat.py` (~136 LOC) ⚠️ Needs Attention

1. **Bug — over-permissive phone regex (line 74):** The pattern `r"\+?[\d\s\-\(\)]{7,15}(?:ext|x)?[\d\s]{0,5}"` matches ISO dates (`2023-01-01`), ISBNs, ZIP+4 codes, and other numeric strings. The `Has Phone Number` column will contain systematic false positives on content-heavy sites.

   **Fix:** Require the pattern to start with `+` or `(` or `\d{3}[.\-]` and add negative-lookahead for pure date patterns.

2. **Error Handling:** `except Exception: pass` (line 64) silently swallows malformed JSON-LD. Log at `debug` level at minimum.

3. **Typing:** `extract_eeat_signals` is missing `-> dict[str, Any]` return annotation.

4. **Design:** Function body is ~115 lines. Extract address, phone, email, and schema detection into separate helpers.

---

### `src/hype_frog/extractors/freshness.py` (~78 LOC) ⚠️ Needs Attention

1. **Bug — overwrite of valid date (lines 35–38):** `extra_values["Last Modified Date"]` may be overwritten with `None` from `last_modified_raw` even when an earlier schema-derived value was valid. Guard with `if last_modified_raw is not None`.

2. **Error Handling:** `except Exception: content_age_days = None` (line 57) swallows date-parse failures with no logging.

3. **Typing:** `extract_freshness_signals` is missing `-> None` return annotation.

---

### `src/hype_frog/extractors/og_social.py` (~173 LOC) ✅ Good
No issues.

---

### `src/hype_frog/extractors/page.py` (~396 LOC) ⚠️ Needs Attention
1. **Performance — double HTML parse:** `parse_html_signals` constructs a `BeautifulSoup` from `html`, then calls `extract_heading_outline(html)` which constructs another. The raw `html` string is passed to both. Fix: parse once, pass the `soup` object to `extract_heading_outline`.

---

### `src/hype_frog/extractors/robots.py` (~14 LOC) ✅ Good
1. **Typing (minor):** `resolve_indexability_directive` is missing a return type annotation.

---

### `src/hype_frog/extractors/schema.py` (~48 LOC) ✅ Good
1. **Design (minor):** Both public functions accept `html: str` and re-parse. Callers with an existing `BeautifulSoup` object pay a redundant parse cost. Consider an overload accepting `BeautifulSoup` directly.

---

### `src/hype_frog/extractors/semantic_engine.py` (~493 LOC) ⚠️ Needs Attention

1. **Design — mutable class-level state is not thread-safe:** `SemanticAnalyzer._model_cache`, `_spacy_unavailable`, and `_fallback_warned` are class-level attributes. The check-then-set pattern in `_load_model` is not thread-safe under concurrent async use (multiple coroutines could both find `_model_cache` empty and both attempt model load).

   **Fix:** Use `asyncio.Lock` or set `_spacy_unavailable = True` atomically before the load attempt.

2. **Performance:** `count_citation_candidates` sliding-window (lines 243–252) may double-count citation triggers across overlapping windows.

---

### `src/hype_frog/extractors/semantic_setup.py` (~116 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/__init__.py` (~14 LOC) ⚠️ Needs Attention
1. **Design:** Only re-exports `content_similarity` members. Eight other analysis submodules (`canonical_chain`, `competitor_benchmarks`, `delta_engine`, `hreflang_audit`, `link_equity`, `snippet_opportunities`, `third_party_scripts`, `topical_authority`) are not exported from the package. Inconsistent discoverability.

---

### `src/hype_frog/analysis/canonical_chain.py` (~144 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/competitor_benchmarks.py` (~308 LOC) ⚠️ Needs Attention

1. **Performance — sequential HTTP fetches:** `_aggregate_domain_signals` fetches pages with `await asyncio.sleep(0.25)` between each of up to 50 requests (5 competitors × 10 pages). Pure serial fetch takes up to 12+ seconds at even 250ms/page. Consider `asyncio.gather` with a per-domain semaphore.

2. **Typing:** `_client_aggregate` is missing a return type annotation.

3. **Error Handling:** `except Exception as exc: continue` (lines 143–145) silently skips sitemap-parse failures.

---

### `src/hype_frog/analysis/content_hub_recommendations.py` (~138 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/content_similarity.py` (~141 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/delta_engine.py` (~798 LOC) ⚠️ Needs Attention

1. **Deprecation — `datetime.now().astimezone()` (line 190):** Relies on the local system timezone rather than an explicit UTC timezone. Use `datetime.now(tz=timezone.utc)`.

2. **Performance — repeated file open:** `_load_snapshot_xlsx` opens a `pd.ExcelFile(path)` but does not reuse it — subsequent `pd.read_excel(path, ...)` calls reopen the same file up to 4 times. Pass the `ExcelFile` object to all `pd.read_excel` calls.

3. **Bug — parameter deleted without use (line 503):** `del typed_extra_rows` immediately after the variable is assigned. Appears to be dead code from an earlier refactor. Either use the variable or remove the parameter.

4. **Design:** At ~800 LOC this module combines snapshot models, loading, delta computation, and workbook output. Consider splitting into `delta_models.py`, `delta_loader.py`, and `delta_sheet_builder.py`.

5. **Design — oversized function:** `build_delta_sheet_rows` is ~130 lines.

---

### `src/hype_frog/analysis/hreflang_audit.py` (~634 LOC) ✅ Good
Note: ~400 lines are embedded ISO 639-1 / ISO 3166-1 data — intentional and appropriate.

---

### `src/hype_frog/analysis/link_equity.py` (~227 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/snippet_opportunities.py` (~160 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/third_party_scripts.py` (~203 LOC) ✅ Good
No issues.

---

### `src/hype_frog/analysis/topical_authority.py` (~150 LOC) ✅ Good
No issues.

---

### `src/hype_frog/orchestration/crawl_runner.py` (~750 LOC) 🔴 Critical

1. **Security/Contract — direct `os.getenv` (lines 191–392):** Four separate `os.getenv` / `os.environ.get` calls: `HF_MAX_DEPTH`, `HF_PREVIOUS_AUDIT_PATH` (×2), `HF_OUTPUT_FILENAME`. Core orchestration should receive these from `RunConfig`, not read env directly.

2. **Bug/Performance — blocking `input()` inside `async def execute_crawl` (lines 349–442):** Five `input()` calls inside an `async def` block block the entire asyncio event loop while waiting for user input. On Python 3.12, this will stall all pending coroutines (PSI cache, checkpoint flushes, etc.) for however long the user takes to respond.

   **Fix:** Move all interactive prompts to a synchronous `_gather_run_options()` function called before entering the async context, or use `loop.run_in_executor(None, input, prompt)`.

3. **Design — oversized function:** `execute_crawl` is ~490 lines — the largest async function in the project.

---

### `src/hype_frog/orchestration/enrichment_flow.py` (~562 LOC) ✅ Good
`run_enrichment` is large (~375 lines) but coherently structured in phase-banner-separated blocks with clear delegation. No critical issues.

---

### `src/hype_frog/orchestration/export_flow.py` (~1048 LOC) 🔴 Critical

1. **Security/Contract — direct `os.getenv` (lines 968–1009):** Reads 11 env vars inline: `HF_EXPORT_PDF`, `HF_EXPORT_HTML`, `HF_REPORT_BRAND_COLOUR`, `HF_PDF_BRAND_COLOUR`, `HF_REPORT_PREPARED_BY`, `HF_PDF_PREPARED_BY`, `HF_REPORT_CLIENT_NAME`, `HF_PDF_CLIENT_NAME`, `HF_PDF_LOGO_PATH`, `HF_REPORT_LOGO_PATH`, `HF_REPORT_ACCENT_COLOUR`.

2. **Deprecation — `datetime.now().astimezone()` (line 287):** Should be `datetime.now(tz=timezone.utc)`.

3. **Design — massive function:** `execute_export` spans ~850 lines and encompasses HTML export, PDF export, delta computation, workbook assembly, chart building, and audit logging. It is impossible to test individual export phases in isolation.

   **Fix:** Extract each export phase into a private function (`_write_html_report`, `_write_pdf_report`, `_build_delta_sheet`, `_finalise_workbook`). `execute_export` becomes a sequencing coordinator of ~50 lines.

4. **Performance — redundant graph computation (line 892):** `compute_internal_link_intelligence(extra_rows, ...)` is called again at export time. This computation was already performed during `run_enrichment` and the result discarded. At 500+ URLs this is a full O(N²) graph traversal for no benefit.

   **Fix:** Pass the `graph_metrics` result forward from `enrichment_flow.py` as part of the pipeline context rather than recomputing it.

5. **Design:** Inline `from hype_frog.reporter.html_report_data import ...` (lines 976–978) deferred to avoid circular imports. This should be documented with a comment explaining why, or the circular import resolved at the module level.

---

### `src/hype_frog/orchestration/export_registry.py` (~860 LOC) ✅ Good
`build_sitemapqa_rows` is ~175 lines but is a single data-transformation with clear sections. No critical issues.

---

### `src/hype_frog/orchestration/run_setup.py` (~145 LOC) ⚠️ Needs Attention
1. **Security/Contract — direct `os.getenv` (lines 25, 28–30, 120–143):** Reads `HF_COMPETITORS`, `CHECK_OG_IMAGES`, `CHECK_CONTENT_IMAGES`, `GSC_URL_INSPECTION`, `HF_MAX_MEMORY_MB`, `HF_STREAMING` outside `config_loader.py`.

---

### `src/hype_frog/pipeline/action_required.py` (~48 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/assemble.py` (~806 LOC) ✅ Good
`row_with_seo_health_enrichment` is ~110 lines but coherently structured. No critical issues.

---

### `src/hype_frog/pipeline/broken_links.py` (~127 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/content_cluster.py` (~30 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/content_duplicates.py` (~294 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/content_hub_metrics.py` (~160 LOC) ✅ Good
1. **Style (minor):** `out != out` NaN check in `_to_positive_float` (line 39). Use `math.isnan(out)` for clarity.

---

### `src/hype_frog/pipeline/context.py` (~11 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/enrich.py` (~19 LOC) ⚠️ Needs Attention
1. **Error Handling:** `value_or_default` catches `except Exception`, which swallows type errors silently. Narrow to `except (TypeError, ValueError)`.

---

### `src/hype_frog/pipeline/export.py` (~94 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/graph_engine.py` (~119 LOC) ✅ Good
1. **Design (minor):** `compute_internal_link_intelligence` accepts `source_label: str` then immediately `del source_label`. The parameter is dead. Remove it or implement the intended use.

---

### `src/hype_frog/pipeline/gsc_coverage.py` (~143 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/gsc_inspection.py` (~172 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/image_inventory.py` (~214 LOC) ⚠️ Needs Attention
1. **Error Handling:** `_probe_image` at lines 98 and 114 catches bare `except Exception: return result` — network/DNS failures are silently discarded. Add `logger.debug` for probe failures.

---

### `src/hype_frog/pipeline/link_inventory.py` (~100 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/og_image_consistency.py` (~156 LOC) ✅ Good
No issues.

---

### `src/hype_frog/pipeline/og_image_validation.py` (~125 LOC) ✅ Good
1. **Error Handling (minor):** `_fetch_og_image_probe` catches bare `except Exception: return None, None, None` — swallows all fetch errors silently.

---

### `src/hype_frog/pipeline/score.py` (~7 LOC) ⚠️ Needs Attention
1. **Design — dead stub:** `passthrough_score_rows` appears to be an unreferenced placeholder. Confirm it is unused and remove it, or document its purpose.

---

### `src/hype_frog/rules/registry.py` (~80 LOC) ⚠️ Needs Attention
1. **Error Handling:** `score_url_health` catches `except Exception: continue` (line 46) inside the rule-evaluation loop. A malformed rule silently contributes a score of 0 with no logging, making bugs in rules invisible at runtime.

   **Fix:** Log at `logger.warning` when a rule raises unexpectedly.

---

### `src/hype_frog/rules/playbook_entries.py` ✅ Good
No critical issues.

---

### `src/hype_frog/rules/scoring.py` (~69 LOC) ✅ Good
No issues.

---

### `src/hype_frog/reporter/excel_engine.py` (~80 LOC) ✅ Good
Clean facade. Correct delegation to sub-modules.

---

### `src/hype_frog/reporter/sheets/config.py` (~126 LOC) ⚠️ Needs Attention
1. **Security/Contract — module-level `os.getenv` (line 65):** The `env_bool` helper calls `os.getenv` at module import time to set six `DEBUG_EXCEL_*` / `DISABLE_*` constants. This is a borderline case — these are truly static toggle flags — but it violates the letter of CLAUDE.md's single-reader contract. The six vars (`HF_DEBUG_EXCEL_ISOLATION_MODE`, `HF_DISABLE_DATA_VALIDATION`, `HF_DISABLE_TOOLTIPS`, `HF_DISABLE_CONDITIONAL_FORMATTING`, `HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES`, `HF_DISABLE_NON_CORE_FREEZE_PANES`) are not documented in `.env.example`.

   **Fix:** Add these six vars to `.env.example`. For strict compliance, inject them via `config_loader` and pass into the reporter as a `ReporterFlags` object.

---

### `src/hype_frog/reporter/html_report_writer.py` ⚠️ Needs Attention
1. **Security/Contract — direct `os.environ.get("HF_REPORT_LOGO_PATH")` (line 33):** Same env-var contract violation as other modules.

---

### Other `reporter/` and `reporter/sheets/` files
The remaining reporter files (`chart_compat.py`, `dashboard_logic.py`, `engine_formatting.py`, `engine_guardrails.py`, `engine_io.py`, `engine_rows.py`, `help_layer.py`, `html_report_data.py`, `html_report_renderer.py`, `narrative_engine.py`, `pdf_exporter.py`, `summary_builder.py`, `workbook_audit.py`, and all `sheets/` builders) were reviewed at the structural level. No env-var violations, `print()` statements in prohibited modules, or pipeline dict mutations were found in these files. The `pdf_exporter.py` uses `datetime.now().astimezone()` (see deprecation list below).

---

### `src/hype_frog/checkpoint/store.py` (~77 LOC) ⚠️ Needs Attention
1. **Deprecation — `datetime.utcnow()` (line 50):** `datetime.utcnow()` is scheduled for removal. Replace with `datetime.now(timezone.utc).isoformat()`. This is the root cause of both pytest deprecation warnings.

   ```python
   # Before
   "saved_at": datetime.utcnow().isoformat() + "Z",
   # After
   "saved_at": datetime.now(timezone.utc).isoformat(),
   ```

---

### `src/hype_frog/checkpoint/cache.py` (~89 LOC) ✅ Good
SQLite UPSERT pattern is correct. No issues.

---

### `src/hype_frog/validators/schema_validator.py` (~254 LOC) ✅ Good
Recursive validation is clean. No issues.

---

### `src/hype_frog/diagnostics/quick_test.py` (~367 LOC) ⚠️ Needs Attention
1. **Security/Contract — `os.environ.setdefault("HF_MAX_DEPTH", ...)` (line 92):** Env write in `diagnostics/`, not `config_loader.py`.
2. **Design:** `run_quick_test_gate` (~70 lines) imports private helpers from `app_orchestrator` (`_build_aeo_rows`, `_build_aioseo_rows`) — tight coupling to private internals.

---

### `src/hype_frog/diagnostics/full_smoke_test.py` (~339 LOC) ⚠️ Needs Attention
1. **Design:** Imports `_audit_phase`, `_run_pipeline`, `_crawl_property_url`, `_validate_crawl_rows` from `quick_test.py` — these are private helpers. Any refactor of `quick_test.py` silently breaks `full_smoke_test.py`.

---

### `src/hype_frog/diagnostics/integration_validator.py` (~454 LOC) ⚠️ Needs Attention
1. **Security/Contract — direct `os.getenv` (lines 333–352):** Reads `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` outside `config_loader.py`.
2. **Style:** `print(format_validation_report(checks))` in `run_validation_cli` (line 443) — bare `print()` consistent with a CLI tool but inconsistent with the logger-first convention. Not a prohibited location per CLAUDE.md (restriction is `pipeline/` and `orchestration/`), but worth noting.

---

### `scripts/crawl_matrix_audit.py` (~389 LOC) 🔴 Critical

1. **Bug — broken import (line 23):** `from hype_frog.core.quick_test import _run_pipeline` — the module `hype_frog.core.quick_test` does not exist. `_run_pipeline` lives in `hype_frog.diagnostics.quick_test`. This script will raise `ModuleNotFoundError` immediately on launch.

   **Fix:** `from hype_frog.diagnostics.quick_test import _run_pipeline`

2. **Security/Contract — direct `os.environ` writes (lines 314–322):** Sets `HF_OUTPUT_FILENAME`, `HF_MAX_DEPTH`, `GSC_URL_INSPECTION`, `HF_STREAMING` directly.

3. **Design:** `deep_audit` is ~85 lines — over guideline.

4. **Test Coverage:** No tests exercise this script.

---

### `pyproject.toml` ✅ Good
Dependencies are pinned to specific versions (good for reproducibility). `scipy` is a core dependency used only for simhash distance — consider moving to an optional group if not universally needed by all users.

---

### `pytest.ini` ✅ Good
`asyncio_mode = auto` and `--strict-markers` are correct. No issues.

---

### `.env.example` ✅ Good — with gap
Canonical and complete for documented vars. **Missing** from the example:
- `HF_MAX_DEPTH` (read in `crawl_runner.py`)
- `HF_OUTPUT_FILENAME` (read in `crawl_runner.py`)
- `HF_DEBUG_EXCEL_ISOLATION_MODE`
- `HF_DISABLE_DATA_VALIDATION`
- `HF_DISABLE_TOOLTIPS`
- `HF_DISABLE_CONDITIONAL_FORMATTING`
- `HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES`
- `HF_DISABLE_NON_CORE_FREEZE_PANES`

---

## Prioritised Issue Registry

### P0 — Fix Immediately (Breaks Functionality)

| # | File | Issue |
|---|---|---|
| 1 | `scripts/crawl_matrix_audit.py:23` | `ModuleNotFoundError` on startup — wrong import path for `_run_pipeline` |
| 2 | `crawler/network_engine.py:652–653` | TTFB equals total response time — TTFB column is misleading for all crawls |
| 3 | `extractors/freshness.py:35–38` | Valid `Last Modified Date` from schema overwritten with `None` |
| 4 | `crawler/sitemap.py:17` | No timeout on sitemap fetch — can hang crawl indefinitely |

### P1 — High Impact (Performance / Data Quality)

| # | File | Issue |
|---|---|---|
| 5 | `core/models.py` | `deepcopy` of large row defaults on every instantiation — major CPU cost at scale |
| 6 | `crawler/data_assembler.py:307,400` | Double lxml parse of same HTML per URL |
| 7 | `orchestration/crawl_runner.py:349–442` | Blocking `input()` inside `async def` — stalls event loop |
| 8 | `orchestration/export_flow.py:892` | Redundant full graph recomputation at export time |
| 9 | `core/models.py` | PSI metric validator returns un-coerced string as `int` field |
| 10 | `extractors/eeat.py:74` | Over-permissive phone regex produces false positives on dates/ISBNs |

### P2 — Security/Contract (Env-Var Violations)

45 direct `os.environ`/`os.getenv` accesses outside `config_loader.py` across 12 files:

| File | Variables |
|---|---|
| `core/api_clients.py` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `core/run_config.py` | `PSI_API_KEY` (×2), `HF_FULL_SMOKE_URL_COUNT` |
| `crawler/fetcher.py` | `PLAYWRIGHT_BROWSERS_PATH`, `LOCALAPPDATA` |
| `crawler/psi_engine.py` | `PSI_API_KEY` |
| `main.py` | `HF_COMPETITORS`, `HF_EXPORT_PDF`, `CHECK_OG_IMAGES`, `CHECK_CONTENT_IMAGES`, `HF_PREVIOUS_AUDIT_PATH`, `GSC_URL_INSPECTION`, `HF_MAX_MEMORY_MB`, `HF_STREAMING` (writes) |
| `orchestration/crawl_runner.py` | `HF_MAX_DEPTH`, `HF_PREVIOUS_AUDIT_PATH`, `HF_OUTPUT_FILENAME` |
| `orchestration/export_flow.py` | 11 branding/export vars |
| `orchestration/run_setup.py` | `HF_COMPETITORS`, `CHECK_OG_IMAGES`, `CHECK_CONTENT_IMAGES`, `GSC_URL_INSPECTION`, `HF_MAX_MEMORY_MB`, `HF_STREAMING` |
| `reporter/html_report_writer.py` | `HF_REPORT_LOGO_PATH` |
| `reporter/sheets/config.py` | 6 `HF_DISABLE_*` / `HF_DEBUG_*` flags |
| `diagnostics/quick_test.py` | `HF_MAX_DEPTH` (write) |
| `diagnostics/integration_validator.py` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| `scripts/crawl_matrix_audit.py` | `HF_OUTPUT_FILENAME`, `HF_MAX_DEPTH`, `GSC_URL_INSPECTION`, `HF_STREAMING` (writes) |

**Resolution path:** Define fields for all missing vars in `config_loader.py`/`config_defaults.py`, wire through `RunConfig`, and inject as function arguments. For the six reporter `DISABLE_*` flags, create a `ReporterFlags` dataclass populated by `config_loader` and passed into `excel_engine.build_workbook()`.

### P3 — Deprecations (Will Break on Future Python)

| File | Line | Issue |
|---|---|---|
| `checkpoint/store.py` | 50 | `datetime.utcnow()` → `datetime.now(timezone.utc)` |
| `analysis/delta_engine.py` | 190 | `datetime.now().astimezone()` → `datetime.now(tz=timezone.utc)` |
| `orchestration/export_flow.py` | 287 | Same |
| `reporter/pdf_exporter.py` | 88 | Same |

### P4 — Design Debt (Maintainability)

| # | File | Issue |
|---|---|---|
| 1 | `crawler/data_assembler.py` | `assemble_from_html` is ~420 lines — extract into phase helpers |
| 2 | `orchestration/export_flow.py` | `execute_export` is ~850 lines — split into phase functions |
| 3 | `orchestration/crawl_runner.py` | `execute_crawl` is ~490 lines — split pre-crawl prompts from async crawl loop |
| 4 | `app_orchestrator.py` | `_build_aioseo_rows` is ~370 lines |
| 5 | `analysis/delta_engine.py` | 800 LOC mixing models, loading, computation, and output |
| 6 | `crawler/psi_engine.py` | 1,266 LOC — largest file; consider module split |
| 7 | `crawler/engine.py` | Exact duplicate of `crawler/__init__.py` — remove one |
| 8 | `core/cli.py` | Return 9-tuple → `NamedTuple` or `@dataclass` |
| 9 | `pipeline/graph_engine.py` | `source_label` parameter deleted immediately — remove it |
| 10 | `pipeline/score.py` | `passthrough_score_rows` appears unused — confirm and remove |
| 11 | `analysis/delta_engine.py:503` | `typed_extra_rows` deleted immediately after assignment |
| 12 | `crawler/fetcher.py:159–180` | `full_suite` parameter deleted immediately after being accepted |

### P5 — Error Handling (Silent Failures)

95 broad `except Exception` clauses in source code. Key ones that affect data quality:

| File | Impact |
|---|---|
| `rules/registry.py` | Silent rule failure scores 0, no warning logged |
| `crawler/link_checks.py` | Broken link checks silently return `None` |
| `extractors/eeat.py:64` | Malformed JSON-LD silently skipped |
| `pipeline/image_inventory.py:98,114` | Image probe failures silently swallowed |
| `url_normalization.py:22` | URL parse failures silently return raw string |
| `analysis/competitor_benchmarks.py:143` | Competitor sitemap failures silently skipped |

**Convention to adopt:** Bare `except Exception: pass` → `except Exception as exc: logger.debug("...", exc_info=exc)`. Reserve silent swallowing only for genuinely expected and harmless failure modes (e.g., optional enrichment that has a safe default).

### P6 — Typing Gaps (Public Functions Missing Annotations)

| File | Function | Missing |
|---|---|---|
| `config.py` | `resolve_project_relative_path` | `-> Path` |
| `crawler/client.py` | `create_session` | `-> aiohttp.ClientSession` |
| `core/discovery_order.py` | `build_url_rank_index`, `_row_rank` | `normalize_fn: Callable[[str], str]` |
| `extractors/eeat.py` | `extract_eeat_signals` | `-> dict[str, Any]` |
| `extractors/freshness.py` | `extract_freshness_signals` | `-> None` |
| `extractors/robots.py` | `resolve_indexability_directive` | return type |
| `analysis/competitor_benchmarks.py` | `_client_aggregate` | return type |
| `app_orchestrator.py` | `add_issue` (closure) | `-> None` |
| `crawler/data_assembler.py` | `assemble_from_html` | `-> None` |

---

## .env.example Gaps

The following env vars are read by source code but not documented in `.env.example`:

```
HF_MAX_DEPTH                        # crawl_runner.py — max BFS depth override
HF_OUTPUT_FILENAME                  # crawl_runner.py — output file path override
HF_DEBUG_EXCEL_ISOLATION_MODE       # reporter/sheets/config.py — debug toggle
HF_DISABLE_DATA_VALIDATION          # reporter/sheets/config.py — removes dropdown validation
HF_DISABLE_TOOLTIPS                 # reporter/sheets/config.py — removes cell comments
HF_DISABLE_CONDITIONAL_FORMATTING   # reporter/sheets/config.py — strips all CF rules
HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES # reporter/sheets/config.py — strips external refs
HF_DISABLE_NON_CORE_FREEZE_PANES    # reporter/sheets/config.py — unfreezes non-core panes
```

---

## Actionable Improvement Roadmap

### Immediate (P0/P1) — 1–2 hours
1. Fix `scripts/crawl_matrix_audit.py:23` import path: `hype_frog.core.quick_test` → `hype_frog.diagnostics.quick_test`
2. Fix `checkpoint/store.py:50`: `datetime.utcnow()` → `datetime.now(timezone.utc)` (eliminates both pytest warnings)
3. Fix `crawler/sitemap.py:17`: add `timeout=aiohttp.ClientTimeout(total=10)` to sitemap fetch
4. Fix `extractors/freshness.py:35–38`: guard `Last Modified Date` overwrite with `if last_modified_raw is not None`
5. Add 8 missing vars to `.env.example`

### Short-term (P1/P2) — 1 sprint
6. Replace `deepcopy(MAIN_ROW_DEFAULTS)` with shallow `.copy()` in `core/models.py` — significant performance gain
7. Fix `crawler/data_assembler.py`: parse HTML once, cache `soup`, cache `get_text()` result
8. Move all `input()` prompts in `orchestration/crawl_runner.py` to a synchronous pre-crawl setup function
9. Fix TTFB measurement in `crawler/network_engine.py` using aiohttp trace hooks
10. Fix phone regex in `extractors/eeat.py` to exclude dates/ISBNs
11. Fix `core/models.py` PSI coercion: coerce string values in `_coerce_optional_psi_metrics`
12. Pass `graph_metrics` forward from `enrichment_flow.py` instead of recomputing in `export_flow.py`

### Medium-term (P2/P3) — 2 sprints
13. Consolidate all env-var reads into `config_loader.py` (45 violations across 12 files): define a `Config` dataclass with all `HF_*` and vendor key fields; inject via function arguments everywhere else
14. Fix remaining 3 deprecated `datetime.now().astimezone()` calls
15. Refactor `execute_export` (~850 lines) into phase functions
16. Refactor `execute_crawl` (~490 lines): extract interactive prompts and async crawl body
17. Refactor `assemble_from_html` (~420 lines): extract to phase helpers
18. Remove duplicate `crawler/engine.py`

### Ongoing (P4/P5)
19. Add `logger.debug` to all bare `except Exception: pass` blocks — treat silent swallowing as a code smell
20. Add type annotations to 9 identified public functions lacking them
21. Add `except` logging to `rules/registry.py` rule-evaluation loop
22. Write tests for `scripts/crawl_matrix_audit.py`
23. Consider splitting `crawler/psi_engine.py` (1,266 LOC) into `psi_cache.py`, `psi_batch.py`, `psi_merge.py`
24. Consider splitting `analysis/delta_engine.py` (~800 LOC) into `delta_models.py`, `delta_loader.py`, `delta_sheet_builder.py`

---

## What Is Working Well

- **Test suite is healthy:** 621 tests, all green, good coverage across all major modules. Tests cover edge cases (empty pages, malformed schema, hreflang errors) and have clear fixture patterns.
- **Module boundaries are largely respected:** `reporter/` does not mutate pipeline dicts; `analysis/` is read-only; `extractors/` does not write to the workbook. The dependency direction is well-maintained.
- **Workbook integrity patterns are solid:** `engine_guardrails.py`, `workbook_audit.py`, and the defensive openpyxl patterns in `sheets/` show disciplined handling of the workbook as the primary output artefact.
- **Checkpoint/cache system is clean:** SQLite UPSERT in `checkpoint/cache.py` is correct; `checkpoint/store.py` is straightforward (one fixable deprecation aside).
- **Rules engine is well-structured:** 99 rules in `rules/registry.py` with clean `IssueRule` contracts and pure functions; `scoring.py` is simple and correct.
- **Content analysis modules are clean:** `content_similarity.py`, `snippet_opportunities.py`, `topical_authority.py`, `link_equity.py`, `third_party_scripts.py`, and `hreflang_audit.py` are all clean and well-tested.
- **Config defaults are comprehensive:** `config_defaults.py` is a well-designed single source of truth for defaults; the YAML config loading in `config_loader.py` is clean.
- **Logging is consistent in core modules:** `get_logger` is used correctly throughout `core/`, `analysis/`, and `pipeline/` with no bare `print()` violations in prohibited locations.
