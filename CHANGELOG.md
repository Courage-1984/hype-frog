# Changelog

All notable changes to **hype-frog** are documented here. The project baseline is the **LI-HF-AUDIT-P0** audit (26 June 2026).

Format: newest entries first. Versions track the `pyproject.toml` package version where applicable.

## [0.2.0] — 2026-06-27

### Added
- **D3 — PSI request jitter:** Jittered delays between PageSpeed Insights API calls; global request pacer; `--psi-delay` CLI flag.
- **D6 — Configuration centralisation:** `config_defaults.py` for tunable thresholds; optional `hype_frog.config.yaml` overrides via `config_loader.py`.
- **D8 — Dependency pinning:** Direct runtime dependencies pinned in `pyproject.toml`; `uv.lock` remains the install source of truth.
- **A5 — robots.txt per-URL mapping** and **Robots.txt Analysis** sheet.
- **D7 — Crawl Log** sheet for fetch/render/PSI/GSC errors.
- **A3 — Redirect chain mapping** and **Redirect Map** sheet.
- **B1 — Canonical chain tracing**; **B4 — GSC URL Inspection** (CLI-gated).
- **D1 — Memory guard** (`--max-memory-mb`, `--streaming`).
- **C1 — Delta tracking** (`--previous-run`, `DeltaFromPreviousRun` tab).

### Changed
- Registry rules, content similarity, freshness, and Quick Wins now read thresholds from central config getters.
- README expanded with environment setup, dependency policy, and YAML config notes.

### Fixed
- Status code normalisation (**D4**) for mixed int/string HTTP statuses.
- Registry trigger matrix coverage for AI crawler rules.

## [0.1.0] — 2026-06-26 (LI-HF-AUDIT-P0 baseline)

- Initial modular Wave 2 architecture: crawl → enrich → export workbook pipeline.
- Pydantic row contracts, BFS spider, PSI/GSC enrichment, rule registry, multi-sheet Excel reporting.
