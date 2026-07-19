---
paths:
  - src/hype_frog/validators/**
---

# Validators

- `schema_validator.py` — JSON-LD structured-data validation only
- No workbook I/O; do not import `reporter/`
- Do not raise on malformed LD — annotate/flag the row so one bad block never aborts the crawl
- Treat input as read-only enrichment
