# System architecture

This document is the **single canonical narrative** for modular layout, runtime pipeline, **BFS spider** behaviour, fetch modes, **semantic AEO**, **LLM search intent**, **ROI** math, executive dashboard aggregation, and cross-links to [data contracts](./data_contracts.md) and [Excel reporting standards](./excel_reporting_standards.md).

## Layers

1. **Orchestration (entry layer)** — `hype_frog/main.py` triggers the flow under `hype_frog/orchestration/`: run configuration, URL set construction, bounded async execution, enrichment/export coordination, runtime policy kept separate from domain logic.
2. **Crawler** — `hype_frog/crawler/` owns HTTP/browser execution and crawl-result assembly (sessions, retries, fetch paths; assemblers normalise payloads into row-ready shapes).
3. **Extractors** — `hype_frog/extractors/` is parsing-only (HTML, metadata, schema, snippets, semantic AEO, E-E-A-T, freshness); no workbook I/O.
4. **Validators** — `hype_frog/validators/` owns JSON-LD schema validation (`schema_validator.py`); invoked during HTML assembly, not from reporters.
5. **Analysis** — `hype_frog/analysis/` owns post-crawl domain passes that mutate row dicts in place (canonical/hreflang chains, link equity, third-party scripts, snippets, topical authority, content similarity, competitor benchmarks, delta engine).
6. **Pipeline** — `hype_frog/pipeline/` owns enrichment glue, graph intelligence, scoring helpers, image/OG probes, export-safe transforms.
7. **Rules** — `hype_frog/rules/` owns `IssueRule` definitions, severity/priority, stable identifiers, playbook metadata.
8. **Reporter** — `hype_frog/reporter/` owns workbook construction (sheets, formatting, guardrails, TOC, navigation, view-state safety).
9. **Checkpoint** — `hype_frog/checkpoint/` persists resumable crawl state for long runs (`store.py`).
10. **Core and config** — `hype_frog/core/` and shared config: logging, URL normalisation, Pydantic contracts, cross-layer helpers.

## Staged async pipeline

1. `hype_frog.orchestration.run_setup` resolves configuration and environment.
2. `hype_frog.orchestration.crawl_runner.execute_crawl` owns URL scheduling, checkpoints, cache writes, crawl concurrency.
3. `hype_frog.crawler.fetcher.fetch_and_parse` fetches HTTP/rendered content, assembles row payloads, records extraction state.
4. `hype_frog.crawler.data_assembler.assemble_from_html` parses HTML into additive `main` and `extra` row dictionaries.
5. `hype_frog.orchestration.enrichment_flow.run_enrichment` runs five phases: GSC analytics context, optional GSC URL Inspection batch, PSI batch, link/image/OG probes and canonical/robots passes, then scoring/graph/issue assembly (including `analysis/*` enrichments and Main merge via `pipeline/assemble.py`).
6. `hype_frog.orchestration.export_flow.execute_export` builds workbook tabs through the reporter layer and merged sheet builders.

## BFS spider

The crawler uses a **breadth-first queue**. Seeds (sitemap or single URL) enter at depth `0`; discovered internal links enqueue at `depth + 1`; a `queued_urls` set prevents duplicate scheduling; **`HF_MAX_DEPTH`** caps discovery (default `3`). Bounded async concurrency is preserved alongside spider-style discovery.

`fetch_and_parse` receives the live `depth` and passes it into `assemble_from_html`, which writes **`Crawl Depth`** so diagnostics distinguish seeds from deeper pages.

### CMS action URL exclusion

URLs whose query string contains CMS/WooCommerce action parameters are **not** enqueued for crawl or internal-link discovery. The canonical list lives in `config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS` (`add-to-cart`, `wc-ajax`, `preview`, etc.) and is enforced via `orchestration/crawl_runner.cms_action_exclusion_keys`. Excluded URLs discovered from inlinks are listed on the **CMS Action URLs** sheet during full-suite export.

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

**Non-integer status codes:** `data_assembler.finalize_row_state` treats string statuses such as `timeout`, `error`, `connection error`, and `dns error` as not indexable and records them in `Indexability Reason` before scoring.

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

`ExtraRowPayload` only preserves keys listed in `EXTRA_ROW_DEFAULTS` (including `ENRICHMENT_PIPELINE_DEFAULTS`) during validation. New fields must be **additive defaults** before they survive enrichment and export.

## Rules engine

`rules/registry.py` defines **`IssueRule`** (`severity`, `name`, `fn`, `scope` defaulting to `"url"`). `get_summary_rules()` returns **99** rules: **90** URL-scoped, **8** site-scoped, **1** server-scoped.

- **URL scope** — one IssueInventory / FixPlan row per affected URL.
- **Site / server scope** — aggregated rows in **Issue Register** (canonical backlog) with labels `(site-wide)` / `(server config)` and **`Affected URL Count`**. Legacy **IssueInventory** remains exported for delta/history tooling but is hidden and excluded from the TOC.

## PSI, Lighthouse, and CrUX

`crawler/psi_engine.py` fetches PageSpeed Insights for **mobile** and **desktop** strategies with all four Lighthouse categories: **performance**, **accessibility**, **best-practices**, **seo**.

- Responses are cached in SQLite (`psi_cache`) with TTL from config.
- Lab metrics project to `PSI_LIGHTHOUSE_EXPORT_KEYS` on extra rows; network items support third-party script inventory.
- **CrUX level:** URL-level field data when `loadingExperience` is present; otherwise **origin** fallback when `originLoadingExperience` is available (`CrUX Level` = `URL` | `Origin`).
- **`PSI Data Status`**, **`Field vs Lab`**, and **`CWV Data Source`** are derived in `_resolve_cwv_labelling` (for example `PSI + CrUX Field (URL)`, `PSI Lab`, `Not available`).
- Registry rules such as **CWV LCP Above 4.0s (Field Data)** require `CrUX Level == "URL"` so origin-only CrUX does not false-trigger URL-level CWV criticals.

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

### Full-suite workbook tabs

Tab order and visibility are defined in `reporter/sheets/workbook_layout.py`.

**Primary (visible):** Table of Contents, Dashboard, Executive Dashboard, Summary, Priority URLs, FixPlan, Quick Wins, Content Optimisation Hub, Content Hub Metrics, Main, AIOSEO Recommendations, Link Inventory, Broken Link Impact, SitemapQA, Template & Duplication Risks, Playbook.

**Advanced (hidden by default, linked from Dashboard/TOC):** Issue Register (canonical backlog), Technical Diagnostics, Content & AI Readiness, Link Intelligence, CMS Action URLs, Redirects, Redirect Map, Robots.txt Analysis, Crawl Log, Link Equity Map, Anchor Text Audit, Snippet Opportunities, Competitor Benchmarks (when `--competitors` / `HF_COMPETITORS` set), Script Inventory, Image Inventory, ResolvedIssues, DeltaFromPreviousRun, Audit Run Details. Legacy **IssueInventory** is still exported for delta tooling but hidden and omitted from the TOC.

Legacy standalone Technical/Content/AEO tabs are **not** emitted in full-suite mode; merged **Technical Diagnostics** and **Content & AI Readiness** supersede them.

### CMS Action URLs

Lists URLs excluded from crawl because they carry CMS action query parameters (see BFS exclusion above), with the triggering parameter keys and discovery parent URL.

## Extensibility

- New measured fields → **new keys** (additive). Avoid renames/removals without migration.
- New sheets/tabs → TOC and view-state patterns updated.
- New network integrations → retry/backoff and session limits respected.

## HTML executive report

Every crawl can produce a self-contained HTML executive report alongside the xlsx workbook, triggered by `HF_EXPORT_HTML=1`.

The HTML report is **white-label**: no tool-internal naming appears in the rendered output. Branding, logo, and colours are configurable via environment variables (`HF_REPORT_PREPARED_BY`, `HF_REPORT_CLIENT_NAME`, `HF_REPORT_LOGO_PATH`, `HF_REPORT_BRAND_COLOUR`, `HF_REPORT_ACCENT_COLOUR`, `HF_REPORT_THEME`). All are optional; defaults produce an unbranded light report.

**Catppuccin Mocha theme:** set `HF_REPORT_THEME=mocha` for a dark Mocha HTML layout with JetBrains Mono (Google Fonts CDN). Optional companion `HF_EXCEL_THEME=mocha` applies mocha-inspired RAG/heatmap colours to the xlsx. Full palette tables, env examples, and module references are in [`docs/excel_reporting_standards.md`](excel_reporting_standards.md) (*Catppuccin Mocha theme*).

The default output file is self-contained — all CSS is inline in a `<style>` block, no external stylesheets or scripts. The **mocha** theme is the only exception (Google Fonts link for JetBrains Mono). It renders identically from disk or HTTP, and produces a clean 4–6 page PDF via Print → Save as PDF from any browser.

**Module structure (under `reporter/`):**
- `html_report_data.py` — aggregates enriched pipeline data into a `ReportContext` dataclass; read-only consumer of pipeline rows.
- `html_report_renderer.py` — renders `ReportContext` to a self-contained HTML string; pure computation, no I/O.
- `html_report_writer.py` — writes the rendered HTML to disk.

HTML report generation is **non-fatal**: failures are logged at `WARNING` level but do not prevent xlsx delivery.

## Validation and smoke-test infrastructure

Non-crawl entrypoints in `core/` provide preflight and regression gates (wired through `main.py` flags):

| Module | Flag(s) | Behaviour |
|--------|---------|-----------|
| `core/integration_validator.py` | `--validate` (`--validate-url`, `--psi-probe-url`) | Checks `.env`, GSC OAuth files + Search Console API, PSI key + one live probe, Playwright/Chromium, semantic engine, optional LLM keys. `IntegrationCheck` carries `CheckStatus` (`PASS`/`WARN`/`FAIL`/`SKIP`); exit `1` on any `FAIL`. |
| `core/quick_test.py` | `--quick-test` (+ `--quick-test-fast`, `--quick-test-skip-{preflight,pytest,audit}`) | Preflight (no live PSI) → focused pytest subset → live 10-URL BFS crawl (accurate mode, depth 2, full suite) → post-export workbook audit. |
| `core/full_smoke_test.py` + `core/full_smoke_fixtures.py` | `--full-smoke-test` (+ `--full-smoke-test-fast`, `--full-smoke-test-skip-{preflight,pytest,audit}`) | Strict preflight (incl. live PSI) → pytest subset → ~80 synthetic-URL **mocked** crawl (timeout/404/redirect status mix) → real enrichment + export → workbook audit. Output under `reports/full_smoke_test/`; volume via `HF_FULL_SMOKE_URL_COUNT`. |
| `core/run_config.py` | — | Frozen `RunConfig` presets (`quick_test_run_config`, `full_smoke_run_config`) and `ResumeCheckpointMode` consumed by `orchestration/run_setup.resolve_run_setup` for non-interactive runs. |

`reporter/workbook_audit.py` (`audit_workbook`, `count_main_rows`) backs the audit phase: TOC at index 0, tab order, freeze panes, Main `Extraction State` contract, Content Hub literals, merged-diagnostic sheet presence.

Sheet ordering, column registries, and shared row builders for export live in `orchestration/export_registry.py` (`get_sheet_sequence`, `get_standard_sheet_columns`, `get_finalization_steps`, `build_*_rows`), consumed by `orchestration/export_flow.execute_export`.

## Out of scope for automation

- **`./.old/`** — do not scan or treat as routine maintenance targets.
- **`./archive/`** — not live product code unless a task explicitly integrates it.

## Verification note for contributors

Before treating behaviour here as **final** documentation, run the relevant automated checks (for example `uv run pytest`) after material code changes. If a gap exists, mark sections **provisional** and name the missing verification (per `.cursor/rules/auto_documentation.mdc`).
