# hype-frog

Concurrent **Python 3.12** pipeline for large-scale URL crawling, structured extraction, rule-based scoring, and **workbook** reporting. The CLI drives an asyncio-heavy workflow with optional rendered-page capture for richer DOM-dependent signals.

**Product highlights:** **BFS spider** discovery with depth limits (`HF_MAX_DEPTH`), **semantic AEO** scoring and entity/citation signals, **LLM search-intent** classification with safe fallbacks, **executive ROI** fields (traffic lift, visibility gain, instant priority), and a multi-sheet **audit workbook** with strict sanitization and view-state guardrails.

## What it does

- Ingests a single URL or a sitemap document, deduplicates and optionally caps URL volume.
- Crawls with configurable concurrency and delay profiles; discovers internal links in **breadth-first** order subject to depth and deduplication caps.
- Produces a multi-sheet **audit workbook** (primary inventory, merged diagnostics, optional full suite) with sanitization and governed view state to reduce client corruption risk.
- Generates a **white-label HTML executive report** alongside the xlsx — self-contained, printable to PDF, configurable branding (`HF_EXPORT_HTML=1`).
- Supports checkpointed runs for long crawls and optional comparison against a prior workbook.
- Optional PSI lab + CrUX field data, GSC Search Analytics and URL Inspection, schema validation, E-E-A-T signals, content similarity, third-party script inventory, snippet opportunities, and competitor benchmarking.

## Project structure (Wave 2 modular)

| Directory | Ownership | Responsibility |
|------|-------------------|-------------------|
| `src/hype_frog/core/` | Foundation contracts | Shared models (`core/models.py`), logging, URL normalisation, CLI/run helpers, and cross-layer primitives. |
| `src/hype_frog/orchestration/` | Flow layer | Resolves run configuration and coordinates async crawl -> enrich -> export stages. |
| `src/hype_frog/crawler/` | Crawl engine | Handles network execution, retries/backoff, fetch-mode selection, PSI/GSC, and typed crawl-result assembly. |
| `src/hype_frog/extractors/` | Parsing | HTML/metadata/schema, semantic AEO, E-E-A-T, freshness — no workbook I/O. |
| `src/hype_frog/validators/` | Schema validation | JSON-LD validation during assembly (`schema_validator.py`). |
| `src/hype_frog/analysis/` | Post-crawl analysis | Canonical/hreflang chains, link equity, snippets, topical authority, similarity, competitors, delta. |
| `src/hype_frog/pipeline/` | Enrichment engine | Graph intelligence, scoring glue, image/OG probes, sanitisation, assemble/merge. |
| `src/hype_frog/rules/` | Issue registry | `IssueRule` dataclass, 99 summary rules, playbook metadata. |
| `src/hype_frog/reporter/` | Reporting engine | Excel I/O, formatting, TOC/navigation, guardrails, HTML/PDF executive reports, Catppuccin Mocha theme (`mocha_theme.py`). |
| `src/hype_frog/checkpoint/` | Durable state | Stores resumable crawl progress for long-running jobs. |

Runtime execution follows: **`orchestration/` -> `crawler/` + `extractors/` -> `analysis/` + `pipeline/` -> `reporter/`**.

## Tech stack

| Area | Libraries / tools |
|------|-------------------|
| Async HTTP | `aiohttp` |
| Optional rendering | `playwright.async_api` (install browser binaries separately when using accurate mode) |
| Parsing | `beautifulsoup4`, `lxml` |
| Data | `pandas`, `pydantic` (row/state contracts enforced via `core/models.py`) |
| Workbooks | `openpyxl` (via pandas ExcelWriter and post-processing); optional PDF via `reportlab` |
| Graph / analysis | `networkx`, `scipy`, `simhash` (near-duplicate detection) |
| Dates | `python-dateutil` |
| Config | `python-dotenv`, optional `pyyaml` (`hype_frog.config.yaml`) |
| Logging / terminal UX | `structlog` (structured JSONL logging), `rich` (console progress bars and formatted output) — see [`docs/logging_architecture.md`](docs/logging_architecture.md) |

See `pyproject.toml` and **`uv.lock`** for pinned dependency versions. Install with `uv sync` so the lockfile resolves reproducible builds.

### Dependency policy (D8)

- **Runtime** libraries (`aiohttp`, `openpyxl`, `pandas`, etc.) are pinned to exact versions in `pyproject.toml`.
- **`uv.lock`** is the source of truth for transitive resolution; commit it with application changes.
- Use **`uv sync`** (not `pip install`) to match the locked environment.

## Requirements

- **Python 3.12+** (tested on Windows 10/11 and Linux)
- Recommended: **[uv](https://docs.astral.sh/uv/)** for installs and virtual environments

## Setup

```bash
# From repository root
uv sync

# Development + tests
uv sync --extra dev
```

For **accurate** (rendered) crawl mode install the optional extra and browser binaries:

```bash
uv sync --extra render
playwright install chromium
```

(After `uv sync --extra render`, run `playwright install chromium` once per machine so the browser binaries are present.)

## Configuration

- Copy `.env.example` to `.env` for runtime variables (see the example file for **PSI** and **GSC** setup notes). Do not commit secrets.
- **Optional YAML overrides:** create `hype_frog.config.yaml` in the project root to tune thresholds without editing source (e.g. `THIN_CONTENT_WORD_THRESHOLD`, `PSI_BASE_DELAY_SECONDS`). Keys must match names in `src/hype_frog/config_defaults.py`.
- **PSI pacing:** `--psi-delay SECONDS` sets the base delay between PageSpeed Insights API calls (default **2.5s** with ±30% jitter).
- **PSI:** set `PSI_API_KEY` in `.env` when you want PageSpeed Insights lab data. The key must belong to a Google Cloud project with the PageSpeed Insights API enabled.
- **GSC:** the app uses the **OAuth desktop** flow via `secrets/client_secrets.json` and `secrets/token.json` (see `.env.example`). Run `uv run hype-frog --gsc-auth` once per machine to create or refresh `secrets/token.json`. Legacy fallbacks: the same filenames under `src/hype_frog/` or the repo root. The signed-in user needs Search Console access to a property that matches the crawl target; the code requests read-only scope `https://www.googleapis.com/auth/webmasters.readonly`.
- **Optional flags:** `--check-og-images`, `--check-images`, `--gsc-url-inspection`, `--gsc-url-inspection-full`, `--competitors`, `--benchmarks`, `--previous-run`, `--streaming`, `--max-memory-mb`, `--export-pdf`, `--psi-delay` (see `uv run hype-frog --help`).
- **Environment (crawl/export):** `HF_COMPETITORS`, `HF_STREAMING`, `HF_MAX_MEMORY_MB`, `HF_PREVIOUS_AUDIT_PATH`, `GSC_URL_INSPECTION`, `CHECK_CONTENT_IMAGES`, `CHECK_OG_IMAGES`, `HF_EXPORT_PDF`, `HF_EXPORT_HTML`, `HF_OUTPUT_FILENAME`, `HF_MAX_DEPTH`, `HF_TEST_SITEMAP_URL`, `HF_FULL_SMOKE_URL_COUNT`, `HF_REPORT_THEME`, `HF_EXCEL_THEME`.
- **Environment (crawl replay / `--regen-report`):** `HF_REGEN_REPORT`, `HF_SNAPSHOT_ID`, `HF_REGEN_REENRICH`, `HF_REFETCH_SKIPPED`, `HF_SNAPSHOT_RETENTION_PER_DOMAIN`, `HF_SNAPSHOTS_DB_PATH` — see [`commands.md`](commands.md#report-only-regeneration-crawl-replay).
- **Environment (workbook rendering toggles, diagnostic — leave unset for full styling):** `HF_DISABLE_CONDITIONAL_FORMATTING`, `HF_DISABLE_DATA_VALIDATION`, `HF_DISABLE_TOOLTIPS`, `HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES`, `HF_DISABLE_NON_CORE_FREEZE_PANES`, `HF_DEBUG_EXCEL_ISOLATION_MODE`.
- **Environment (logging/observability):** `HF_RUN_ID`, `HF_LOG_LEVEL`, `HF_CONSOLE_LOG_LEVEL` — see [`docs/logging_architecture.md`](docs/logging_architecture.md).

Full reference for every variable above: [`.env.example`](.env.example).
- **HTML/PDF report branding (optional):** `HF_REPORT_PREPARED_BY`, `HF_REPORT_CLIENT_NAME`, `HF_REPORT_LOGO_PATH`, `HF_REPORT_BRAND_COLOUR`, `HF_REPORT_ACCENT_COLOUR`, `HF_REPORT_THEME` (HTML); `HF_PDF_CLIENT_NAME`, `HF_PDF_PREPARED_BY`, `HF_PDF_LOGO_PATH`, `HF_PDF_BRAND_COLOUR` (PDF). **Catppuccin Mocha:** `HF_REPORT_THEME=mocha` (dark HTML + JetBrains Mono) and/or `HF_EXCEL_THEME=mocha` (workbook RAG palette). See [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) and `.env.example`.
- Interactive runs prompt for crawl profile, suite mode, checkpoint interval, and optional previous workbook path.

## Running

**CLI source of truth:** structured subcommands below. Legacy flags (`--quick-test`, `--validate`, `--gsc-auth`, …) remain supported for scripts and CI.

| Command | Purpose |
|---------|---------|
| `uv run hype-frog crawl` | Interactive crawl (prompts for URL, limits, profile) |
| `uv run hype-frog crawl --url https://example.com/` | Non-interactive crawl with defaults |
| `uv run hype-frog validate` | Check GSC/PSI/LLM credentials (no crawl) |
| `uv run hype-frog auth gsc` | OAuth desktop flow for Search Console |
| `uv run hype-frog setup playwright` | Install Chromium for accurate crawl mode |
| `uv run hype-frog test quick` | Comprehensive smoke gate (preflight + pytest + crawl + audit) |
| `uv run hype-frog test full-smoke` | Pre-export scale simulation |

Full flag reference: [`commands.md`](commands.md).

From the repository root, install the package into the uv environment (once per clone or after layout changes), then start the CLI:

```bash
uv sync
uv run hype-frog crawl
# equivalent entrypoints:
uv run hype-frog          # legacy interactive (same as crawl)
uv run python -m hype_frog.main
```

Follow CLI prompts for target URL or sitemap, limits, and profiles when running without `--url`.

### Distribution bundle (`dist/`)

To ship a self-contained copy for internal teams (requires **uv** and **Python 3.12+** on the target machine — no PyInstaller executable):

```bash
uv run python scripts/build.py
cd dist/hype-frog-0.3.0
uv sync
uv run hype-frog --help
```

The bundle includes `src/`, `docs/`, `scripts/`, `README.md`, `commands.md`, `pyproject.toml`, `uv.lock`, and `.env.example`.

For end users **without** Python/`uv` installed, a separate zero-dependency
standalone `.exe` build exists instead (`uv run python build_exe.py`, PyInstaller)
— see [`DISTRIBUTION.md`](DISTRIBUTION.md).

### Validate secrets and APIs (no crawl)

Check GSC OAuth files, PSI API access, and optional LLM keys before a full run:

```bash
uv run hype-frog validate
# legacy equivalent:
uv run hype-frog --validate

# Also confirm a crawl target matches a visible Search Console property
uv run hype-frog validate --validate-url "https://example.com/"
```

Exit code `0` means all required checks passed; `1` means at least one failed.

## Type-safe philosophy

- Hype Frog uses a **Chain of Trust** model: row/state payloads are validated through Pydantic models in `src/hype_frog/core/models.py` before they move between engine boundaries.
- Contracts are **additive-first**: introduce new fields instead of renaming/removing established keys that scoring, checkpoints, or reporting rely on.
- Reporter modules treat incoming payload dictionaries as read-only and focus on workbook layout/format integrity.

### Non-interactive quick test (comprehensive smoke gate)

Run between code changes to exercise preflight checks, a focused pytest subset, a **10-URL page-sitemap crawl** (Playwright accurate mode, BFS depth 2, full workbook suite), and a post-export workbook audit:

```bash
uv sync --extra render --extra dev
playwright install chromium
uv run hype-frog --quick-test
```

**What `--quick-test` runs (in order):**

1. **Preflight** — GSC OAuth files, property match for the crawl target, PSI key presence (no slow PSI live probe).
2. **Pytest regression** — focused reporter/crawler/extractor tests (~30 cases).
3. **Pipeline** — `page-sitemap.xml` seed (max 10 URLs), external-link checks, PSI on up to 3 URLs when `PSI_API_KEY` is set.
4. **Workbook audit** — TOC at index 0, tab order, freeze panes, Main `Extraction State` contract, Content Hub literals, merged diagnostic sheets when present.

Exit code `0` only when all non-skipped phases pass. A summary block is printed at the end.

**Faster variant** (crawl + workbook audit only, ~3–8 minutes):

```bash
uv run hype-frog --quick-test-fast
```

**Optional flags** (combine with `--quick-test`):

| Flag | Effect |
|------|--------|
| `--quick-test-skip-preflight` | Skip GSC/PSI preflight |
| `--quick-test-skip-pytest` | Skip pytest subset |
| `--quick-test-skip-audit` | Skip workbook audit |

Override BFS depth for the preset: `HF_MAX_DEPTH=1 uv run hype-frog --quick-test-fast`

### Pre-export full smoke (uncapped sitemap simulation)

Run **before** a long production crawl to catch late export/enrichment failures (e.g. SitemapQA status coercion, workbook integrity at scale):

```bash
uv run hype-frog --full-smoke-test
```

**What it runs:**

1. **Preflight (strict)** — GSC OAuth files, property match, `PSI_API_KEY`, and one **live PSI probe**.
2. **Pytest regression** — orchestration, reporter, PSI, and pipeline tests.
3. **Pipeline** — `max_urls=None`, **80 synthetic sitemap URLs** (representative of uncapped runs), transport edge cases (`Timeout`, 404, redirects), mocked crawl/PSI/OG/link probes, **real GSC analytics** when OAuth is ready, full enrichment + export.
4. **Workbook audit** — same integrity checks as production.

Faster variant (skip preflight + pytest):

```bash
uv run hype-frog --full-smoke-test-fast
```

Output: `reports/full_smoke_test/`. Tune synthetic sitemap volume: `HF_FULL_SMOKE_URL_COUNT=120 uv run hype-frog --full-smoke-test-fast`

If Playwright is not installed, accurate mode falls back to fast HTTP with a warning; the run still completes. Output lands under `reports/latest/` unless `HF_OUTPUT_FILENAME` overrides it.

### Report-only regeneration (`--regen-report`)

After a normal crawl, post-enrichment row data is saved to `.cache/crawl_snapshots.sqlite`. Re-run export only (no crawl) when iterating on reporter or workbook layout:

```bash
uv run hype-frog --regen-report
uv run hype-frog --regen-report --snapshot-id <uuid>
```

Replay uses the same `export_flow` as a live run and writes a new workbook under `reports/latest/` with a `_regen_` suffix. See [`commands.md`](commands.md) for env vars (`HF_REGEN_REPORT`, `HF_SNAPSHOT_RETENTION_PER_DOMAIN`) and the manual regression workflow.

**`ModuleNotFoundError: No module named 'hype_frog'`** means the editable project is not installed in the active venv. Run **`uv sync`** from the repo root (not only `uv venv` without syncing the project). Then retry `uv run …`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `PSI_API_KEY` missing / PSI columns empty | Key not set or API disabled | Add key to `.env`; enable PageSpeed Insights API in Google Cloud |
| GSC columns empty or auth errors | Missing OAuth files or wrong property | Run `uv run hype-frog auth gsc`; confirm the signed-in user has access to the crawl domain |
| `403` / `429` from PSI | Quota or rate limiting | Increase `--psi-delay`; reduce URL cap; retry later |
| Playwright / accurate mode unavailable | Browser binaries not installed | `uv sync --extra render` then `uv run hype-frog setup playwright` |
| Workbook won't open / TOC mismatch | Client edited protected view state | Re-export; see [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) |
| High memory on large crawls | Full in-memory row retention | Use `--streaming` or `HF_STREAMING=1`; lower URL cap or `--max-memory-mb` |
| Permission denied writing reports | Output path not writable | Set `HF_OUTPUT_FILENAME` to a writable directory; ensure parent folders exist |

For credential validation without a crawl: `uv run hype-frog validate`.

## Tests

```bash
uv run pytest
```

Re-run the suite after substantive changes to crawl, pipeline, or reporting code.

## Architecture and documentation

Canonical technical manuals (keep in sync with code changes):

- [`docs/system_architecture.md`](docs/system_architecture.md) — layers, staged pipeline, **BFS spider**, fetch modes, **AEO**, **search intent**, **ROI**, executive dashboard, workbook integrity pointers.
- [`docs/data_contracts.md`](docs/data_contracts.md) — `main` / `extra` envelopes, Pydantic contracts, additive keys, checkpoints, **crawl replay snapshots**.
- [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) — reporter module split, sanitization, ghost/nuclear view state, TOC, Content Hub literals.
- [`docs/workbook_tabs.md`](docs/workbook_tabs.md) — per-tab audience, content, and end-user descriptions for all 31 workbook tabs.
- [`docs/logging_architecture.md`](docs/logging_architecture.md) — structured logging stack, `run_id`, JSONL schema.
- [`docs/performance_benchmarks.md`](docs/performance_benchmarks.md) — concurrency model, memory profile, throughput bottlenecks.
- [`DISTRIBUTION.md`](DISTRIBUTION.md) — standalone `.exe` distribution and first-run setup guide.

## Governance

- **Root contract:** [`.cursorrules`](.cursorrules) — ownership, chain-of-trust, logic vs layout, `uv` toolchain, **continuous documentation sync**.
- **Cursor rules (consolidated):** [`.cursor/rules/`](.cursor/rules/) — 12 `.mdc` files. `architecture.mdc` and `auto_documentation.mdc` are path-scoped via `globs` (not always-on); layer rules (`crawler_engine`, `excel_engine`, `analysis`, `orchestration`, `rules_engine`, `config`, `checkpoint`, `validators`, `diagnostics`, `snapshots`) attach when matching files are edited.

## Policy notes

- **`./.old/`** is excluded from automated documentation and analysis in this project.
- Prefer **additive** changes to established pipeline row keys unless a migration is explicitly approved.
