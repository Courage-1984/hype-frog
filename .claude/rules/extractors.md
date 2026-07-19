---
paths:
  - src/hype_frog/extractors/**
---

# Extractors

Parse-only layer: HTML, metadata, schema, AEO/semantic, E-E-A-T, OG, freshness.

## Invariants
- No workbook I/O; do not import `reporter/`
- No HTTP/PSI/GSC calls — receive content from crawler
- Map outcomes into Extraction State (`complete` | `partial` | `skipped`) when contributing skip/partial signals
- Additive keys only on row dicts

Primary modules: `page.py`, `schema.py`, `semantic_engine.py`, `eeat.py`, `og_social.py`, `freshness.py`
