---
paths:
  - src/hype_frog/core/models.py
  - docs/data_contracts.md
---

# Data contracts

Source of truth: `docs/data_contracts.md` and `.cursor/rules/architecture.mdc`.

## Row payloads
- `MainRowPayload` / `ExtraRowPayload` whitelist via `MAIN_ROW_DEFAULTS` / `EXTRA_ROW_DEFAULTS`.
- New fields: additive only — update defaults in `models.py`.
- GSC null semantics: no match → `None` (not `0.0`) for clicks/impressions/CTR/position.

## Extraction State
Exactly `complete` | `partial` | `skipped` — tests must assert explicitly.

## Stores (do not conflate)
- BFS checkpoint: `{workbook}_checkpoint.json`
- Crawl replay: `.cache/crawl_snapshots.sqlite`
- Delta sidecar: `_delta_summary.json`
