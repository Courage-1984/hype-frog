# Architecture overview

This document describes the current enterprise modular structure and the runtime flow between modules. It intentionally avoids low-level implementation detail; see sibling files under `./docs/` for crawl and reporting specifics.

## Layers

1. **Orchestration (entry layer)** — `hype_frog/main.py` triggers the modular orchestration flow under `hype_frog/orchestration/`. This layer resolves run configuration, builds the target URL set, drives bounded async execution, coordinates enrichment/export stages, and keeps runtime policy separate from domain logic.
2. **Crawler (network + assembly split)** — `hype_frog/crawler/` owns HTTP/browser network execution and crawl-result assembly as distinct concerns. Network modules handle sessions, retries, and fetch paths; assembler modules normalize crawl payloads into stable row-ready shapes.
3. **Extractors** — `hype_frog/extractors/` performs parsing-only work (HTML, metadata, schema, snippet signals) and never performs workbook I/O.
4. **Pipeline (enrichment + graph separation)** — `hype_frog/pipeline/` owns row enrichment, scoring glue, and export-safe transforms, with graph-specific logic isolated in dedicated graph modules instead of mixed into generic enrichment code.
5. **Rules** — `hype_frog/rules/` owns issue definitions, severity/priority logic, stable identifiers, and scoring contracts consumed downstream.
6. **Reporter** — `hype_frog/reporter/` owns workbook construction (sheet population, formatting, guardrails, TOC, navigation, and view-state safety) with dedicated submodules for I/O, formatting, rows, and guardrails.
7. **Checkpoint** — `hype_frog/checkpoint/` persists resumable crawl state and recovery metadata for long-running jobs.
8. **Core and config foundations** — `hype_frog/core/` and shared config modules provide logging, URL normalization, and cross-layer helpers used by higher layers.

## Runtime flow

The standard flow is:

1. **`orchestration/`** resolves run inputs and orchestrates stage execution.
2. **`crawler/`** fetches pages and assembles crawl outputs with bounded retries/concurrency.
3. **`pipeline/`** enriches and scores data, including separated graph analysis paths.
4. **`reporter/`** emits a guarded Excel workbook with strict sanitization and view-state rules.

## Async model

URL processing is concurrent under asyncio. Blocking calls must not run on the event loop in hot paths. Rendered fetching uses async Playwright APIs behind a semaphore cap.

## Data shapes

Crawl output is conceptually a list of **`CrawlResult`**-like structures: a **main** row dictionary and an **extra** dictionary per URL. Downstream code and reporters expect certain canonical column names; see [data_contracts.md](./data_contracts.md).

## Extensibility guidelines

- Add new **measured fields** as new keys (additive). Avoid renaming or removing keys consumers rely on.
- New **sheets** or **tabs** require TOC updates and view-state application consistent with existing patterns.
- New **network integrations** should follow retry/backoff configuration and respect session limits.

## Out of scope for automation

The `./.old/` directory must not be scanned or documented as part of routine maintenance. Historical snapshots may live under `./archive/` without being treated as active modules unless a task says otherwise.
