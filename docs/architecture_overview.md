# Architecture overview

This document describes how the repository is structured and how work flows through it. It intentionally avoids deep implementation detail; see sibling files under `./docs/` for crawl and export specifics.

## Layers

1. **Entry and orchestration** — `hype_frog/main.py` (CLI entry) and `hype_frog/entry_main.py` load configuration, build the URL list, schedule asyncio tasks, merge results, coordinate optional metric batches, and invoke reporters. Sanitization runs before Excel emission.
2. **Crawler** — Session factory (`crawler/client.py`), fetch and parse pipeline (`crawler/fetcher.py` and related modules), sitemap ingestion, and optional auxiliary metric clients. Bounded concurrency and retries are configured centrally (`config.py`).
3. **Extractors** — Pure parsing: HTML signals, JSON-LD summaries, indexability hints, snippet extraction. No workbook I/O.
4. **Pipeline** — Shared helpers for enrichment, scoring glue, row sanitization, and Excel-safe sheet naming (`pipeline/`).
5. **Rules** — Issue catalogs, scoring, stable identifiers, owner and workflow metadata (`rules/`).
6. **Reporters** — Workbook assembly: tabs, conditional formats, TOC, navigation, view-state normalization (`hype_frog/reporter/`, including `hype_frog/reporter/sheets/`).
7. **Checkpoint** — Resume metadata and incremental persistence for interrupted crawls (`checkpoint/`).
8. **Core** — Logging, CLI helpers, URL normalization (`core/`).

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
