# Performance & Concurrency Sprint — Progress Tracker

## Phase 0: Documentation & Analysis

- [x] Architectural analysis (`network_engine.py`, `fetcher.py`, `crawl_runner_bfs.py`)
- [x] Create `docs/performance_benchmarks.md`
- [x] Create `PERF_TODO.md` (this file)

---

## Phase 1: Memory & Allocation Profiling

- [x] Generator-based link inventory pipeline (`link_inventory_stream.py`, `LinkInventoryCache`, streamed Excel write)
- [x] `AuditCache.iter_results_chunked()` wired via `crawl_payload_loader.py` (BFS returns open cache; rows flushed every 500 URLs)
- [x] Memory circuit breaker (`memory_circuit_breaker()` in `core/memory_guard.py`, triggered on batch flush)
- [x] Fix Windows RSS sampling (`OpenProcess` + `GetProcessMemoryInfo`)
- [ ] Profile Link Inventory peak RAM on ~1k / 5k / 11k URL fixtures (live crawl)
- [x] Stream enrichment passes (`load_enrichment_row_pairs()` — no `crawl_rows` intermediate)
- [ ] Evaluate trimming `Link Details` from in-memory extra rows after export sheet build
- [ ] Extend `check_memory_limit` to sample RSS every N URLs (not only batch flush)
- [ ] Audit Playwright context retention on multi-domain crawls (close idle contexts?)

---

## Phase 2: Event Loop Optimisation

- [x] Move `assemble_from_html` / BeautifulSoup parse to `asyncio.to_thread` in `fetcher.py`
- [x] Release worker semaphore before politeness `asyncio.sleep(request_delay)`
- [ ] Offload `apply_search_intent` / spaCy to thread pool (batch or per-URL)
- [ ] Audit enrichment `asyncio.gather` fan-out vs connector `limit_per_host`
- [ ] Measure event-loop lag under 4 workers + accurate mode

---

## Phase 3: Network & Throughput Tuning

- [x] Adaptive back-off: honour numeric `Retry-After` on 429; double base backoff when header absent (`network_engine.py`)
- [ ] Latency-aware jitter (increase delay when p95 TTFB rises)
- [x] Parallelise `sniff_external_domains_head` with semaphore (75 concurrent, 5s timeout, TTL cache)
- [ ] Align `PLAYWRIGHT_MAX_SESSIONS` with interactive worker presets
- [ ] Document / tune `HTTP_CONNECTOR_LIMIT_PER_HOST` vs worker count

---

## Phase 4: Validation

- [x] Create `scripts/benchmark_crawl.py` (100-URL subset, time/RSS)
- [x] `--export` flag for streaming write_only export RSS profiling
- [x] `StreamingExcelWriter` + two-pass format (`write_only` then `load_workbook`)
- [ ] Record baseline metrics in `docs/performance_benchmarks.md`
- [ ] Regression gate: workbook row-hash comparison pre/post optimisation
- [x] Full suite green: `uv run pytest tests/` (881 tests)

---

## Known hotspots (from analysis)

| Priority | Issue | Module | Status |
|----------|-------|--------|--------|
| P0 | Full crawl row reload into RAM after SQLite cache | `crawl_runner_bfs.py` | **Mitigated** — cache handoff; enrichment still reloads |
| P0 | Link Inventory flat list at export | `merged_builders.py` | **Fixed** — SQLite spill + streamed sheet write |
| P1 | Per-URL sleep inside worker semaphore | `fetcher.py` | **Fixed** |
| P1 | Sync BS4/lxml on event loop | `fetcher.py` | **Fixed** (`to_thread`) |
| P2 | 429 retry ignores `Retry-After` | `network_engine.py` | **Fixed** |
| P2 | Serial external HEAD pacing | `link_inventory.py` | Open |
| P3 | Intent analysis on crawl critical path | `crawl_runner_bfs.py` | Open |

---

## Out of scope

- Changing audit scoring rules or row contracts
- Removing Rich terminal UX
- Adding heavy profiling dependencies (prefer stdlib + existing JSONL logs)
