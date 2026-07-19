---
paths:
  - src/hype_frog/crawler/**
---

# Crawler

## Split
Crawler owns fetch + row assembly; parsers live in `extractors/`. Wire new signals through `data_assembler.py` / `data_assembler_phases.py` — not ad hoc in `crawl_runner.py` or `pipeline/`.

## Fetch
- Playwright: **`playwright.async_api` only** (no sync on the event loop)
- Fast: aiohttp; Accurate: rendered with graceful HTTP fallback
- Extraction State: `complete` | `partial` | `skipped` + `skip_reason` when skipped
- MIME non-HTML 200 → `skipped` / `unsupported_mime`; still export the row

## Assembler
`init_rows()`, `assemble_from_html()`, `finalize_row_state()` — module functions, not a class. Non-integer status codes (`timeout`, `dns error`, …) handled in `finalize_row_state`.

## PSI / GSC
- PSI: `psi_batch` / `psi_cache` / `psi_merge`; short timeout; quota → status not crash; CrUX absent → `None`
- GSC credentials only via `gsc_engine.py` (`secrets/`); never hard-code paths elsewhere

## URL identity
Normalise via `core/url_normalization.py`. CMS action query params excluded per `config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS`.

Detail: `docs/system_architecture.md`
