# Wave 1 refactor plan: `entry_main.py`

This document maps the current `hype_frog/entry_main.py` responsibilities and proposes safe module extraction targets for enterprise hardening. It is a planning artifact only; no runtime flow changes are implied.

## Current logical blocks in `entry_main.py`

1. **Runtime bootstrap and run-mode branching**
   - Loads logging and `.env`.
   - Selects interactive versus preset (`RunConfig`) execution.
   - Resolves crawl profile, suite mode, checkpoint settings, and output filenames.

2. **Target discovery and crawl setup**
   - Parses single URL versus sitemap input.
   - Applies URL dedupe/caps.
   - Creates async session, worker semaphore, cache, and checkpoint state.

3. **Async crawl execution and checkpoint persistence**
   - Schedules `fetch_and_parse` tasks.
   - Streams completion via `asyncio.as_completed`.
   - Flushes batches to cache and periodically writes checkpoint snapshots.

4. **Post-crawl enrichment pipeline orchestration**
   - Loads cached rows and merges optional GSC/PSI telemetry.
   - Resolves unresolved internal-link statuses.
   - Applies canonical/link enrichers, graph metrics, rule scoring, and main/extra sync.

5. **Historical comparison orchestration**
   - Loads previous audit workbook (when provided).
   - Computes issue-id baseline, previous counts, and resolved/new delta context.

6. **Workbook assembly and export orchestration**
   - Builds many sheet-specific row payloads and column lists.
   - Writes dataframes/sheets, applies tab formatting/hyperlinks/guardrails.
   - Emits dashboard, prioritization, glossary, delta and metadata sheets.

7. **Specialized row builders colocated at file end**
   - `_build_aeo_rows(...)`
   - `_build_aioseo_rows(...)`
   - These are pure transforms but currently live inside the entrypoint monolith.

## Proposed extraction targets (Wave 1+ sequence)

### 1) `src/hype_frog/orchestration/run_setup.py`
- **Owns:** run bootstrap, interactive prompt resolution, output/checkpoint path derivation, crawl profile resolution.
- **Inputs:** `RunConfig | None`, environment/config defaults.
- **Outputs:** typed `RunSetup` object (resolved run parameters).
- **Benefit:** isolates CLI/runtime policy from crawl and export mechanics.

### 2) `src/hype_frog/orchestration/crawl_runner.py`
- **Owns:** task fan-out, as-completed aggregation, cache flushing, checkpoint cadence.
- **Inputs:** resolved setup + session + URL list.
- **Outputs:** cached results and crawl execution metadata.
- **Benefit:** makes async bounded-concurrency behavior testable without workbook concerns.

### 3) `src/hype_frog/orchestration/enrichment_flow.py`
- **Owns:** post-crawl data flow (GSC/PSI merge, link checks, SEO scoring, row synchronization).
- **Inputs:** cached rows, sitemap metadata, run options.
- **Outputs:** typed enriched row bundles for export.
- **Benefit:** cleanly separates data enrichment from final report rendering.

### 4) `src/hype_frog/orchestration/export_flow.py`
- **Owns:** previous-audit compare loading plus workbook write orchestration (sheet payload assembly + writer lifecycle + guardrail invocation).
- **Inputs:** enriched data bundle + compare context + output target.
- **Outputs:** persisted workbook and export summary metadata.
- **Benefit:** keeps reporter calls centralized and removes Excel concerns from entry orchestration.

## Recommended near-term boundaries

- Keep `hype_frog/main.py` as thin CLI shell.
- Reduce `entry_main.py` to a coordination facade (`main()` calling the 4 modules above).
- Keep extractors pure and keep reporter mutations inside reporter-facing flow only.
- Prefer explicit dataclasses/typed models for module handoff payloads (`RunSetup`, `CrawlExecutionResult`, `EnrichmentResult`, `ExportInputs`).

## Risk controls for rollout

- Extract in atomic batches (max 3 files per change) by introducing module wrappers first, then moving internals.
- Preserve existing column names and row-key contracts as append-only.
- After each extraction, run focused tests/smoke run to validate checkpoint, async crawl progress, and workbook guardrails.
