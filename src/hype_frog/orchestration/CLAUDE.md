# orchestration/ — scoped Claude Code context

Inherits root `CLAUDE.md`. Additional invariants for this layer only. Cursor-side equivalent: `.cursor/rules/orchestration.mdc` — keep both in sync when module ownership or entry points change (this drifted once already: an `.mdc` rule referenced a `build_standard_sheets()` function that no longer exists).

## Purpose and boundaries

`orchestration/` coordinates crawl, enrichment, and export — it must not own business logic. It calls into `crawler/`, `analysis/`, `pipeline/`, and `reporter/`; it does not implement extraction, scoring, or formatting itself.

## Module ownership

| Module | Role |
|--------|------|
| `crawl_runner.py` | BFS crawl loop entry point; delegates to the split modules below |
| `crawl_runner_bfs.py` | Core BFS loop: checkpoint resume, memory-guard enforcement, Rich progress bars, semantic intent enrichment, `CrawlExecutionResult` |
| `crawl_runner_frontier.py` | URL eligibility: `candidate_internal_links()`, CMS action-URL exclusion, `normalize_url_key()` |
| `crawl_runner_interactive.py` | Runtime prompts: `CrawlRuntimeOptions`, `prompt_crawl_options_sync()` |
| `enrichment_flow.py` | Batched PSI/GSC enrichment after the crawl phase |
| `export_flow.py` | Sequences xlsx/HTML/PDF export; non-fatal on individual export failures |
| `export_executive_reports.py` | Non-fatal HTML/PDF generation via a shared `ReportContext` |
| `export_workbook.py` | `write_full_suite_workbook()` drives all 20+ tab builders and integrates the delta engine; `apply_deferred_readwrite_export_steps()` runs formula injection and briefing layout after a write-only streaming pass |
| `export_row_builders.py` | Sheet-specific row builders (AEO rows, AIOSEO rows, pattern rows, template risk rows) |
| `export_workbook_constants.py` | Playbook legend/quick-reference constant tables |
| `export_registry.py` | Registry of named export artefacts for delta comparison and run history |
| `run_setup.py` | Initialises run context (config validation, output path resolution, logging bootstrap) before the crawl starts |

**Entry-point names drift** — verify function names against the actual file before citing them elsewhere (docs, Cursor rules); the previous drift was caught only because the fabricated name returned zero grep matches.

## CMS action URL filtering

`crawl_runner_frontier.py` enforces `config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS` to drop WooCommerce/CMS action URLs from the BFS queue and internal-link discovery. Extend the frozenset in `config_defaults.py`, not with hard-coded patterns in the frontier module.

## BFS budget

The crawl loop must respect `max_pages`/`max_depth` from `RunConfig`. When exhausted, log at `INFO` and stop cleanly — never silently truncate without a log message.

## Enrichment batching

`enrichment_flow.py` must batch PSI/GSC calls (never one request per URL serially), respect per-service rate limits, and propagate `skip_reason` tokens on quota exhaustion rather than leaving rows blank.

## Export sequencing

`export_flow.py` writes xlsx first (must not be blocked by HTML/PDF failures), then attempts HTML (`HF_EXPORT_HTML=1`) and PDF (`HF_EXPORT_PDF=1`) — failures in either log at `WARNING` and continue. Never let step 2/3 abort step 1 or skip subsequent steps.

## No print()

Same as pipeline: `print()` is prohibited here — use `core/` logging exclusively.
