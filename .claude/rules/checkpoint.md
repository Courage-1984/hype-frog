---
paths:
  - src/hype_frog/checkpoint/**
---

# Checkpoint (resume)

Durable BFS progress for long runs — **not** crawl-replay snapshots and **not** delta sidecars.

## Ownership
- `store.py` — resume state for `crawl_runner_bfs.py`
- `cache.py` — crawl-scoped cache primitives
- `link_inventory_cache.py` — link inventory during BFS

## Invariants
- Writes must be idempotent/resumable (prefer write-temp-then-replace)
- Crash mid-write must not corrupt resume state
