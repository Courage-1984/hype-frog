---
paths:
  - src/hype_frog/pipeline/**
---

# Pipeline

Enrichment glue after crawl: assemble/merge, graph, broken links, images/OG, content hubs, export-safe transforms.

## Invariants
- **No `print()`** — use `core` logging only
- Do not re-implement fetch or workbook formatting
- Main merge keys live in `assemble.py` (`*_MAIN_MERGE_KEYS`) — extend carefully, additive only
- Hub Action Required literals computed via `action_required.py::determine_action_required()`: `Complete` | `Needs Copy` | `Needs Optimisation` (British spelling)
- Treat assembled crawler rows as inputs; additive enrichment keys only

## Ownership examples
`assemble.py`, `broken_links.py`, `link_inventory_stream.py`, `graph` helpers, `og_image_consistency.py`, `image_inventory.py`
