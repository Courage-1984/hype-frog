# hype-frog — Claude Code context

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
| `core/` | Logging, URL normalisation, Pydantic models (`models.py`), run config (`run_config.py`), CLI helpers |
| `config.py` / `config_defaults.py` / `config_loader.py` | Config loading; only `config_loader.py` reads `os.environ` |
| `crawler/` | HTTP sessions, PSI (`psi_engine.py`), GSC (`gsc_engine.py`), row assembly (`data_assembler.py`) |
| `extractors/` | HTML/metadata parsing — no workbook writes |
| `analysis/` | Post-crawl domain passes — read-only consumers of row dicts |
| `orchestration/` | BFS loop (`crawl_runner.py`), enrichment batching, export sequencing (`export_flow.py`) |
| `pipeline/` | Row assembly (`assemble.py`), scoring glue, graph engine |
| `rules/` | `IssueRule` registry (99 rules), scoring, playbook entries — pure functions only |
| `reporter/` | Excel/HTML/PDF output — do not mutate pipeline dicts here |
| `checkpoint/` | Durable crawl progress |
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
- **Never** read `os.environ` directly in domain modules — wire through `config_loader.py`

## Canonical docs
| Doc | Covers |
|---|---|
| `docs/system_architecture.md` | Pipeline stages, BFS, AEO, PSI/CrUX, orchestration layers |
| `docs/data_contracts.md` | Row shapes, Pydantic, IssueRule scope, GSC null semantics |
| `docs/excel_reporting_standards.md` | Workbook integrity, TOC, view state, conditional formatting |
| `commands.md` | CLI command cheat sheet (PowerShell + bash) |
| `.env.example` | All env vars with purpose and defaults |

## Cursor governance rules
| File | Scope |
|---|---|
| `.cursor/rules/architecture.mdc` | alwaysApply — module boundaries, async, logging, typing, AI governance |
| `.cursor/rules/auto_documentation.mdc` | alwaysApply — doc sync, testing invariants |
| `.cursor/rules/excel_engine.mdc` | alwaysApply — workbook integrity, reporter module ownership |
| `.cursor/rules/crawler_engine.mdc` | glob: crawler / extractors / pipeline / core / orchestration |
| `.cursor/rules/analysis.mdc` | glob: analysis/ |
| `.cursor/rules/orchestration.mdc` | glob: orchestration/ |
| `.cursor/rules/rules_engine.mdc` | glob: rules/ |
| `.cursor/rules/config.mdc` | glob: config*.py |
