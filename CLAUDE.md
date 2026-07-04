# hype-frog — Claude Code context

# NB | CRITICAL ALWAYS APPLY RULE: YOU ARE NEVER TO TOUCH GIT NOR COMMIT AND OR PUSH!

## What this is
Concurrent Python 3.12 SEO/AEO audit pipeline → multi-sheet Excel workbook + optional HTML/PDF executive reports.

## How to run
```
uv run pytest                       # full test suite
uv run hype-frog --quick-test       # smoke gate: preflight + pytest + 10-URL crawl + workbook audit
uv run hype-frog --full-smoke-test  # pre-export gate: representative sitemap scale (mocked crawl)
uv run hype-frog --validate         # credential/env validation only (no crawl)
```

## Module dependency direction
```
config/core → crawler/extractors → analysis → pipeline → rules → reporter
orchestration drives the loop across all layers
diagnostics/ provides CLI gates (--quick-test, --full-smoke-test, --validate)
```

## Module map
| Package | Ownership |
|---|---|
| `core/` | Logging, URL normalisation, Pydantic models (`models.py`), run config (`run_config.py`), CLI helpers, centralised env var accessors (`env_vars.py`), URL discovery ranking (`discovery_order.py`) |
| `config.py` / `config_defaults.py` / `config_loader.py` | Config loading; only `config_loader.py` and `core/env_vars.py` read `os.environ` |
| `crawler/` | HTTP sessions, PSI (`psi_engine.py` + `psi_batch.py` batch fetching + `psi_cache.py` SQLite TTL cache + `psi_merge.py` payload parsing), GSC (`gsc_engine.py`), row assembly (`data_assembler.py`, `data_assembler_phases.py`) |
| `extractors/` | HTML/metadata parsing — no workbook writes |
| `analysis/` | Post-crawl domain passes — read-only consumers of row dicts; delta comparison (`delta_engine.py`, `delta_loader.py`, `delta_models.py`, `delta_sheet_builder.py`) |
| `orchestration/` | BFS loop (`crawl_runner.py` → `crawl_runner_bfs.py` core loop, `crawl_runner_frontier.py` URL eligibility, `crawl_runner_interactive.py` runtime prompts), enrichment batching (`enrichment_flow.py`), export sequencing (`export_flow.py`, `export_executive_reports.py`), workbook assembly (`export_workbook.py`, `export_row_builders.py`, `export_workbook_constants.py`), export registry (`export_registry.py`) |
| `pipeline/` | Row assembly (`assemble.py`), scoring glue, graph engine |
| `rules/` | `IssueRule` registry (99 rules), scoring, playbook entries — pure functions only |
| `reporter/` | Excel/HTML/PDF output — do not mutate pipeline dicts here |
| `checkpoint/` | Durable crawl progress |
| `snapshots/` | Crawl-replay snapshot store (`models.py`, `replay.py`, `store.py`) backing `--regen-report` / `HF_SNAPSHOT_ID` |
| `validators/` | Schema validation (`schema_validator.py`) |
| `diagnostics/` | CLI validation gates: `quick_test.py`, `full_smoke_test.py`, `full_smoke_fixtures.py`, `integration_validator.py` |

## Critical guardrails (non-obvious)
- `print()` is **prohibited** in `pipeline/` and `orchestration/` — use `core/` logging (`get_logger`) only
- Pipeline row dicts (`main_data` / row keys) are **append-only**: no key renames/removals without explicit approval
- Changes spanning **more than 3 files** require explicit human confirmation before proceeding
- All new or changed **public functions must have explicit type annotations**
- LLM/PSI HTTP calls: **≤5 s timeout**, no blocking retries, fall back to `"Unknown"` on failure
- Workbook integrity is **highest priority** in `reporter/` — prefer defensive openpyxl over shortcuts
- Never treat `archive/`, `archive_legacy/`, or `.old/` as live code

## Env vars
- All hype-frog knobs are prefixed `HF_` (e.g. `HF_EXPORT_HTML=1`, `HF_OUTPUT_FILENAME`)
- Third-party keys use vendor convention without prefix (`PSI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- **Canonical list**: `.env.example` — update it whenever a new var is added
- **Never** read `os.environ` directly in domain modules — wire through `core/env_vars.py` (the single env-accessor module) via `config_loader.py`

## Canonical docs
| Doc | Covers |
|---|---|
| `docs/system_architecture.md` | Pipeline stages, BFS spider split, PSI/CrUX split, AEO, discovery ordering, orchestration layers |
| `docs/data_contracts.md` | Row shapes, Pydantic, IssueRule scope, GSC null semantics, delta models and sheet columns |
| `docs/excel_reporting_standards.md` | Workbook integrity, TOC, view state, conditional formatting, orchestration export builders, Mocha theme |
| `docs/logging_architecture.md` | Structured logging stack, `run_id`, JSONL schema, console/file split |
| `docs/performance_benchmarks.md` | Concurrency model, memory profile, event-loop/throughput bottlenecks, benchmark methodology |
| `commands.md` | CLI command cheat sheet (PowerShell + bash), delta/previous-run flags |
| `.env.example` | All env vars with purpose and defaults |
| `DISTRIBUTION.md` | Standalone `.exe` distribution/setup guide for end users |

## Cursor governance rules
| File | Scope |
|---|---|
| `.cursor/rules/architecture.mdc` | alwaysApply — module boundaries, async, logging, typing, AI governance |
| `.cursor/rules/auto_documentation.mdc` | alwaysApply — doc sync, testing invariants |
| `.cursor/rules/excel_engine.mdc` | glob: `reporter/**/*.py` — workbook integrity, reporter module ownership |
| `.cursor/rules/crawler_engine.mdc` | glob: crawler / extractors / pipeline / core / orchestration |
| `.cursor/rules/analysis.mdc` | glob: analysis/ |
| `.cursor/rules/orchestration.mdc` | glob: orchestration/ |
| `.cursor/rules/rules_engine.mdc` | glob: rules/ |
| `.cursor/rules/config.mdc` | glob: config*.py |
