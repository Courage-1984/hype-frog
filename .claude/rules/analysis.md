---
paths:
  - src/hype_frog/analysis/**
---

# Analysis

Post-crawl domain passes that enrich row dicts. No workbook I/O. No live PSI/GSC/LLM network from this layer.

## Invariants
- Additive keys only; do not rename/remove crawler/pipeline keys
- Delta store (`_delta_summary.json` / `delta_*`) ≠ crawl-replay snapshots (`snapshots/`) ≠ BFS checkpoint
- Competitor data is pre-loaded — never live-fetch competitors mid-run
- Scoring weight changes belong in `rules/scoring.py`, not here

## Modules
canonical/hreflang chains, link equity, third-party scripts, snippets, topical authority, content similarity, content hub recommendations, delta engine/loader/models/sheet builder
