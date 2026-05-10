# System architecture

This document is the **single canonical narrative** for modular layout, runtime pipeline, **BFS spider** behaviour, fetch modes, **semantic AEO**, **LLM search intent**, **ROI** math, executive dashboard aggregation, and cross-links to [data contracts](./data_contracts.md) and [Excel reporting standards](./excel_reporting_standards.md).

## Layers

1. **Orchestration (entry layer)** — `hype_frog/main.py` triggers the flow under `hype_frog/orchestration/`: run configuration, URL set construction, bounded async execution, enrichment/export coordination, runtime policy kept separate from domain logic.
2. **Crawler** — `hype_frog/crawler/` owns HTTP/browser execution and crawl-result assembly (sessions, retries, fetch paths; assemblers normalise payloads into row-ready shapes).
3. **Extractors** — `hype_frog/extractors/` is parsing-only (HTML, metadata, schema, snippets, semantic AEO); no workbook I/O.
4. **Pipeline** — `hype_frog/pipeline/` owns enrichment, scoring glue, export-safe transforms; graph logic stays in dedicated graph modules.
5. **Rules** — `hype_frog/rules/` owns issues, severity/priority, stable identifiers, scoring contracts.
6. **Reporter** — `hype_frog/reporter/` owns workbook construction (sheets, formatting, guardrails, TOC, navigation, view-state safety).
7. **Checkpoint** — `hype_frog/checkpoint/` persists resumable crawl state for long runs.
8. **Core and config** — `hype_frog/core/` and shared config: logging, URL normalisation, cross-layer helpers.

## Staged async pipeline

1. `hype_frog.orchestration.run_setup` resolves configuration and environment.
2. `hype_frog.orchestration.crawl_runner.execute_crawl` owns URL scheduling, checkpoints, cache writes, crawl concurrency.
3. `hype_frog.crawler.fetcher.fetch_and_parse` fetches HTTP/rendered content, assembles row payloads, records extraction state.
4. `hype_frog.crawler.data_assembler.assemble_from_html` parses HTML into additive `main` and `extra` row dictionaries.
5. `hype_frog.orchestration.enrichment_flow.run_enrichment` adds PSI, GSC, link graph, issues, scores.
6. `hype_frog.orchestration.export_flow.execute_export` builds workbook tabs through the reporter layer.

## BFS spider

The crawler uses a **breadth-first queue**. Seeds (sitemap or single URL) enter at depth `0`; discovered internal links enqueue at `depth + 1`; a `queued_urls` set prevents duplicate scheduling; **`HF_MAX_DEPTH`** caps discovery (default `3`). Bounded async concurrency is preserved alongside spider-style discovery.

`fetch_and_parse` receives the live `depth` and passes it into `assemble_from_html`, which writes **`Crawl Depth`** so diagnostics distinguish seeds from deeper pages.

## Async model

URL processing is concurrent under **asyncio**. Blocking work must not run on the event loop in hot paths. Rendered fetching uses async Playwright APIs behind a semaphore cap.

## Fetch modes and extraction contract

| Mode | Behaviour |
|------|------------|
| **HTTP (fast)** | Default: `aiohttp` plus HTML parsers when DOM execution is not required. |
| **Rendered (accurate)** | `playwright.async_api` loads the page and snapshots HTML. If Playwright/Chromium is unavailable or the loop cannot spawn subprocesses, the stack **falls back** to HTTP and marks extraction accordingly. |

Row observability fields (used by scoring; see `rules/scoring.py`):

| Field | Allowed values (conceptual) |
|-------|------------------------------|
| Extraction State | `complete`, `partial`, `skipped` |
| Extraction Source | `raw_http`, `rendered_browser` |
| `skip_reason` (extra row) | Machine-readable token when a URL is skipped without HTML parse (for example `unsupported_mime` when HTTP `200` returns a non-HTML `Content-Type`); otherwise `null` / omitted. |

Fetch sets `partial` when rendering is incomplete or degraded mid-pipeline (timeouts on `networkidle`, selector waits, observer failures, etc.). **`skipped`** is used when the accurate renderer cannot start at all: **subprocess probe failure** (event loop cannot spawn Playwright) or **`get_context` returns `None`** (CDP / Chromium launch failure) — both return empty diagnostics with `extraction_source` still `raw_http` so the row remains inventory-visible.

**MIME dead-letter:** `fetch_and_parse` short-circuits when the HTTP layer returns status `200` with no HTML body because **`text/html` is absent from `Content-Type`**. In that case the row is marked **`skipped`**, `skip_reason` is set to **`unsupported_mime`**, and `assemble_from_html` is not invoked (no parser work on PDFs, images, JSON, etc.).

**Rendered diagnostics are additive.** When rendering fails or is disabled, the HTTP row still completes with partial or raw extraction state; missing rendered metrics stay blank/zero-safe.

## Retries, sessions, Playwright, URL identity

- **Retries:** `config.py` supplies max attempts, base/max delay, backoff factor, jitter, retryable status codes. Logic stays **bounded**; exhausted retries surface as structured row state, not infinite loops.
- **Sessions:** `create_session` wires `aiohttp.TCPConnector` with global and per-host limits and keepalive timeout from configuration. Do not remove limits without a replacement strategy.
- **Playwright:** use **`playwright.async_api`** only in crawler runtime code; launch, navigation, waits, and `page.content()` inside async context managers; semaphore caps parallel browsers.
- **URL identity:** `src/hype_frog/core/url_normalization.py` keeps deduplication, checkpoint resume, and join keys consistent across crawl, enrichment, and reporting.

## Pydantic data contracts

Runtime rows are dictionary pairs wrapped by Pydantic models (details: [data_contracts.md](./data_contracts.md)):

- `MainRowPayload` — primary audit row.
- `ExtraRowPayload` — diagnostics, enrichment, links, AEO, report-only fields.
- `CrawlRowPayload` — carries both through crawl and enrichment.

`ExtraRowPayload` only preserves keys listed in `EXTRA_ROW_DEFAULTS` during validation. New fields (`Search Intent`, `Crawl Depth`, semantic scores, ROI signals, `skip_reason`, etc.) must be **additive defaults** before they survive enrichment and export.

Strict models in `hype_frog.core.models` also validate HTTP, PSI, and GSC payloads via `hype_frog.core.api_clients`; failures log and return `None` so workers continue.

## AEO logic

`hype_frog.extractors.semantic_engine.SemanticAnalyzer` is the core AEO parser, memory-conscious:

- spaCy loads lazily, cached once per process.
- Text to spaCy is capped by `DEFAULT_MAX_CHARS`.
- Missing spaCy or `en_core_web_sm` does not crash the crawl.

**Entity density:** `(named entity count / word count) * 100`. Strategic labels: `ORG`, `PERSON`, `GPE`, `PRODUCT`, `EVENT`. Top three surface forms by frequency → **`Top Entities`**.

**Citation readiness:** counts 40–60 word paragraph or sentence-cluster candidates with definition-style triggers (`is`, `are`, `refers to`, `means`, `provides`, …) → **`Citation Candidate Count`**.

**`Semantic AEO Score` (0–100):** 60% entity-density coverage (capped at 10% density) + 40% citation candidates (capped at five). Distinct from legacy **`AEO Readiness Score`**; both retained.

## LLM search intent

`IntentAnalyzer` labels intent as: `Informational`, `Transactional`, `Navigational`, `Commercial Investigation`, or **`Unknown`**.

Implementation: OpenAI-compatible chat completions in `hype_frog.core.api_clients`; short prompt: *Analyze this text and return one word for the search intent.*

If `OPENAI_API_KEY` is absent, or on HTTP errors, malformed output, empty text, or unexpected labels → **`Unknown`**. Mandatory so LLM enrichment never blocks crawls.

Applied after each crawl result is assembled and before cache persistence, using title, meta description, headings, and page-copy snippet from rendered or raw HTML.

## ROI model

`hype_frog.core.scoring.calculate_executive_roi` returns:

- **`Potential Traffic Lift`** — `GSC Clicks * ((100 - Semantic AEO Score) / 100) * 0.25` (25% max lift cap).
- **`AEO Visibility Gain`** — `100 - Semantic AEO Score`.
- **`Instant Priority`** — `CRITICAL` when `GSC Clicks > 500` **and** (`Semantic AEO Score < 50` **or** `Field LCP > 2500ms`).

All ROI math is None-safe; missing or malformed inputs collapse to neutral values.

## Executive dashboard aggregation

The Content Optimisation Hub appends (without reordering existing columns): `Potential Traffic Lift`, `AEO Visibility Gain`, `Instant Priority`, `Search Intent`.

The Executive Dashboard uses **`INDEX`/`MATCH`** on Hub columns (no hard-coded column letters): total estimated monthly traffic lift sums Hub lifts; critical priority pages counts Hub rows with `Instant Priority == CRITICAL`.

Hub conditional formatting: colour scale on **`Semantic AEO Score`**; **`CRITICAL`** rows highlighted bold white-on-red.

## Workbook integrity

Reporter output stays **openpyxl**-based; do not introduce XlsxWriter on the workbook path. Observe [excel_reporting_standards.md](./excel_reporting_standards.md): string sanitization, freeze-pane guardrails, TOC/tab name alignment, additive columns, numeric/blank-safe conditional-format inputs.

## Extensibility

- New measured fields → **new keys** (additive). Avoid renames/removals without migration.
- New sheets/tabs → TOC and view-state patterns updated.
- New network integrations → retry/backoff and session limits respected.

## Out of scope for automation

- **`./.old/`** — do not scan or treat as routine maintenance targets.
- **`./archive/`** — not live product code unless a task explicitly integrates it.

## Verification note for contributors

Before treating behaviour here as **final** documentation, run the relevant automated checks (for example `uv run pytest`) after material code changes. If a gap exists, mark sections **provisional** and name the missing verification (per `.cursor/rules/auto_documentation.mdc`).
