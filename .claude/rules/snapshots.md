---
paths:
  - src/hype_frog/snapshots/**
---

# Snapshots (replay)

Backs `--regen-report` / `HF_SNAPSHOT_ID` via `.cache/crawl_snapshots.sqlite`.

## Ownership
- `models.py` — schema + `CRAWL_SNAPSHOT_SCHEMA_VERSION`
- `store.py` — persist/load
- `replay.py` — reconstruct crawl/enrichment results without HTTP/PSI/GSC

## Invariants
- Distinct from BFS checkpoint and from analysis delta `RunSnapshot`
- Breaking payload changes → bump `CRAWL_SNAPSHOT_SCHEMA_VERSION` and fail loudly on mismatch
- Replay path skips crawl/enrichment; optional `HF_REFETCH_SKIPPED` is the only designed live I/O exception

Detail: `docs/system_architecture.md` (report-only replay section)
