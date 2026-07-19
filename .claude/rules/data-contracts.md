---
paths:
  - src/hype_frog/core/models.py
  - src/hype_frog/core/skipped_row_contract.py
  - docs/data_contracts.md
---

# Data contracts

## Row payloads
- `MainRowPayload` / `ExtraRowPayload` whitelist via `MAIN_ROW_DEFAULTS` / `EXTRA_ROW_DEFAULTS` (+ `ENRICHMENT_PIPELINE_DEFAULTS`)
- New fields: **additive only** — register defaults in `models.py` before they survive validate/merge
- No renames/removals without migration + human approval

## Extraction State
Exactly `complete` | `partial` | `skipped` (lowercase). Tests must assert explicitly.
Extraction Source: `raw_http` | `rendered_browser`

## GSC null semantics
No match → `None` (not `0.0`) for clicks/impressions/CTR/position

## Stores (do not conflate)
- BFS checkpoint: `{workbook}_checkpoint.json` (`checkpoint/`)
- Crawl replay: `.cache/crawl_snapshots.sqlite` (`snapshots/`)
- Delta sidecar: `_delta_summary.json` (`analysis/`)

Detail: `docs/data_contracts.md`
