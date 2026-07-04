# Performance & Concurrency — Architectural Baseline

Canonical reference for crawl engine tuning, memory guardrails, and event-loop behaviour.

**Related:** [`system_architecture.md`](system_architecture.md), [`logging_architecture.md`](logging_architecture.md), [`data_contracts.md`](data_contracts.md).

---

## Scope

This document captures **measured constraints and code-path profiles** for the hot crawl path:

| Module | Role |
|--------|------|
| `crawler/network_engine.py` | HTTP fetch, retries, Playwright rendering |
| `crawler/fetcher.py` | Per-URL orchestration, row assembly, politeness delay |
| `orchestration/crawl_runner_bfs.py` | BFS scheduler, worker pool, SQLite cache |
| `checkpoint/cache.py` | `AuditCache` — SQLite spill for crawl rows |
| `core/memory_guard.py` | RSS estimation and hard caps |
| `pipeline/link_inventory.py` / `reporter/sheets/merged_builders.py` | Link Inventory materialisation |

---

## Current concurrency model

### BFS worker pool (`crawl_runner_bfs.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  asyncio event loop                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Semaphore(workers)  — default 2–4 (interactive)     │   │
│  │   └─ fetch_and_parse() per URL                      │   │
│  │        ├─ fetch_http (aiohttp, shared session)      │   │
│  │        ├─ optional Playwright render                │   │
│  │        ├─ BeautifulSoup/lxml parse (sync, in-task)  │   │
│  │        ├─ apply_search_intent (async, per URL)      │   │
│  │        └─ asyncio.sleep(request_delay + jitter)     │   │
│  └─────────────────────────────────────────────────────┘   │
│  in_flight capped at `workers`; schedule on FIRST_COMPLETED │
└─────────────────────────────────────────────────────────────┘
```

| Knob | Default (`config_defaults.py`) | Notes |
|------|-------------------------------|-------|
| `MAX_WORKERS` | **3** | Interactive “Balanced” profile |
| Gentle / Faster profiles | 2 / 4 workers | `crawl_runner_interactive.py` |
| `DELAY_BETWEEN_REQUESTS` | **2.5 s** | Applied **inside** semaphore after each URL |
| `request_jitter_seconds` | env-driven | Added to per-URL sleep |

**Starvation risk:** `fetch_and_parse` holds the worker semaphore for the **entire** URL lifecycle (HTTP + render + parse + intent + sleep). Retries in `fetch_http` also sleep while holding the slot. Effective throughput ≈ `workers / (fetch_time + delay)`.

### Playwright gate (`network_engine.py`)

| Knob | Value |
|------|-------|
| `PLAYWRIGHT_MAX_SESSIONS` | **3** (global `asyncio.Semaphore`) |
| `PlaywrightSessionManager` | One per crawl; per-domain `BrowserContext` cache |
| Teardown | `aclose()` in BFS `finally` block ✓ |

Accurate mode: crawl workers (up to 4) compete for Playwright slots (3). Render path includes `networkidle` + hydration settle (400 ms) + selector waits — **seconds per page**, not milliseconds.

### Enrichment concurrency (post-crawl)

| Stage | Semaphore / pacing |
|-------|-------------------|
| Unresolved internal link checks | `min(20, max(5, workers * 3))` |
| OG / content image probes | same formula |
| External domain HEAD | **Sequential** — 2 s sleep between unique hosts |
| GSC / PSI | `asyncio.to_thread` + batch engines |

---

## HTTP connection pooling

`crawler/client.py` → single `aiohttp.ClientSession` per crawl (`execute_crawl` context manager).

| `TCPConnector` setting | Value |
|---------------------|-------|
| `limit` | 100 |
| `limit_per_host` | 20 |
| `keepalive_timeout` | 30 s |

**Assessment:** Pooling is correctly configured. Worker count (≤4) is well below `limit_per_host`. No evidence of per-request session churn.

### Retry / back-off (`fetch_http`)

| Property | Behaviour |
|----------|-----------|
| Retryable statuses | `{408, 425, 429, 500, 502, 503, 504}` |
| Back-off | Exponential: `base * factor^attempt`, capped at 20 s + jitter |
| `429` handling | Retries with **fixed formula** — does **not** parse `Retry-After` header |
| Sleep location | Inside worker semaphore (blocks slot) |

**Gap:** No adaptive back-off from response latency or rate-limit headers.

---

## Memory profile

### Estimation guard (`memory_guard.py`)

| Constant | Value |
|----------|-------|
| `_BYTES_PER_URL_ESTIMATE` | 512 KiB / URL |
| `_WARN_ESTIMATE_MB` | 2 048 MB |
| `check_memory_limit` | RSS check on batch flush (every 250 URLs) |

Pre-crawl warning only; hard abort when `--max-memory-mb` exceeded.

### Row retention

| Phase | Memory behaviour |
|-------|------------------|
| Crawl (`--streaming`) | Rows upserted to SQLite `AuditCache` in batches of 250 |
| Crawl end | **Full reload:** `iter_results()` → `list[CrawlRowPayload]` — all rows in RAM |
| Enrichment | `extra_work` list — duplicate of all extra rows |
| Export | `build_link_inventory_rows(extra_rows)` — **flatten** all `Link Details` anchors |

### Link Inventory scaling (primary RAM hotspot)

Each crawled page stores `Link Details` (anchor list) on the extra row (`data_assembler_phases.py`). At export:

1. `export_workbook.py` iterates all `Link Details` for legacy link rows.
2. `build_link_inventory_rows()` allocates a **flat list** of every anchor row, then dedupes by `(Source URL, Target URL, Anchor Text)`.

**Order-of-magnitude (11 000 URLs):**

| Assumption | Anchors | Flat row dicts (~200 B each) |
|------------|---------|------------------------------|
| 20 links/page | ~220 k | ~44 MB |
| 50 links/page | ~550 k | ~110 MB |
| 100 links/page | ~1.1 M | ~220 MB |

Plus JSON serialisation in SQLite, enrichment copies, and pandas workbook buffers — **512 KiB/URL estimate is optimistic** for link-heavy sites.

`AuditCache.iter_results_chunked()` exists but is **unused** in the crawl → enrichment handoff.

---

## Event-loop blocking profile

Operations that run **synchronously on the main event loop** (no executor):

| Operation | Location | Impact |
|-----------|----------|--------|
| `BeautifulSoup(html, "lxml")` | `data_assembler_phases`, extractors | CPU ∝ page size; holds worker slot |
| `assemble_from_html` pipeline | `fetcher` → `data_assembler` | Multiple parser passes per URL |
| `SemanticAnalyzer.analyze` / spaCy `nlp()` | `apply_search_intent` in BFS loop | Blocks loop between URL completions |
| `json.dumps` / `json.loads` | `AuditCache` upsert/read | Spikes on large `Link Details` payloads |
| SQLite `commit` | `AuditCache.upsert_results` | Sync I/O every 250 URLs |

**Already offloaded:** GSC context load, GSC URL Inspection batch, interactive CLI prompts (`asyncio.to_thread`).

---

## Resource lifecycle audit

| Resource | Created | Destroyed | Risk |
|----------|---------|-----------|------|
| `aiohttp.ClientSession` | `execute_crawl` | `async with` exit ✓ | Low |
| `PlaywrightSessionManager` | BFS loop (accurate mode) | `finally: aclose()` ✓ | Low |
| Ephemeral Playwright manager | `fetch_rendered` when `session_manager=None` | `finally: aclose()` ✓ | Low (per-call overhead) |
| `BrowserContext` per domain | Cached in manager | Closed on `aclose` ✓ | Contexts accumulate for multi-domain crawls |
| `AuditCache` SQLite conn | BFS start | `close(cleanup_file=True)` ✓ | Temp `.db` removed |
| `robots_cache` dict | BFS loop | Returned in result (held for enrichment) | Grows with unique domains |

**No confirmed session leaks** in the primary crawl path. Multi-domain accurate crawls retain Playwright contexts until crawl end (by design).

---

## Throughput bottlenecks (ranked)

1. **Per-URL politeness sleep** inside semaphore (`fetcher.py` L429–434) — dominates at default 2.5 s delay.
2. **Playwright accurate mode** — render waits + global semaphore of 3.
3. **Post-crawl full materialisation** — SQLite → Python lists for all rows.
4. **Link Inventory flatten** — O(total anchors) memory at export.
5. **Sync HTML parsing** on event loop under worker semaphore.
6. **Sequential external HEAD** checks (2 s/host) during enrichment.
7. **Intent classification** serialised per URL on the crawl loop.

---

## Stability vs speed principles

1. Politeness delays and retry caps prioritise **not tripping origin rate limits** over raw QPS.
2. `MemoryLimitExceeded` abort is preferable to OOM on Windows.
3. Playwright subprocess probe prevents Proactor deadlocks on Windows.
4. Performance changes must **not alter audit row payloads** unless explicitly approved (byte-identical Excel is the Phase 4 regression target).

---

## Benchmark placeholder (Phase 4)

Target diagnostic: `scripts/benchmark_crawl.py` — 100-URL subset profile.

| Metric | Capture method |
|--------|----------------|
| Wall time | `time.perf_counter()` per phase |
| Peak RSS | `memory_guard.get_process_rss_mb()` sampled during crawl |
| CPU % | `resource.getrusage` / Windows `GetProcessTimes` |
| Event-loop lag | Optional: `loop.slow_callback_duration` (3.12+) |

Baseline numbers to be recorded after first benchmark run.

---

## Open performance work items

Carried forward from the performance/concurrency sprint tracker (`PERF_TODO.md`, now archived — its completed items are reflected in the sections above):

- Profile Link Inventory peak RAM on ~1k / 5k / 11k URL fixtures (live crawl).
- Evaluate trimming `Link Details` from in-memory extra rows after the export sheet is built.
- Extend `check_memory_limit` to sample RSS every N URLs, not only on batch flush.
- Audit Playwright context retention on multi-domain crawls (close idle contexts?).
- Offload `apply_search_intent` / spaCy to a thread pool (batch or per-URL).
- Audit enrichment `asyncio.gather` fan-out vs. connector `limit_per_host`.
- Measure event-loop lag under 4 workers + accurate mode.
- Latency-aware jitter (increase delay when p95 TTFB rises).
- Align `PLAYWRIGHT_MAX_SESSIONS` with interactive worker presets.
- Document / tune `HTTP_CONNECTOR_LIMIT_PER_HOST` vs. worker count.
- Regression gate: workbook row-hash comparison pre/post optimisation.
- Serial external HEAD pacing in `link_inventory.py` (P2 hotspot, still open).
- Intent classification serialised per URL on the crawl critical path in `crawl_runner_bfs.py` (P3 hotspot, still open).
