# hype-frog

Concurrent **Python 3.12** pipeline for large-scale URL crawling, structured extraction, rule-based scoring, and **workbook** reporting. The CLI drives an asyncio-heavy workflow with optional rendered-page capture for richer DOM-dependent signals.

## What it does

- Ingests a single URL or a sitemap document, deduplicates and optionally caps URL volume.
- Crawls with configurable concurrency and delay profiles.
- Produces a multi-sheet **audit workbook** (primary inventory, technical and content tabs, optional full suite) with sanitization and governed view state to reduce client corruption risk.
- Supports checkpointed runs for long crawls and optional comparison against a prior workbook.

## Tech stack

| Area | Libraries / tools |
|------|-------------------|
| Async HTTP | `aiohttp` |
| Optional rendering | `playwright.async_api` (install browser binaries separately when using accurate mode) |
| Parsing | `beautifulsoup4`, `lxml` |
| Data | `pandas`, `pydantic` (validation for select row shapes) |
| Workbooks | `openpyxl` (via pandas ExcelWriter and post-processing) |
| Graph / analysis | `networkx`, `numpy` |
| Config | `python-dotenv` |

See `pyproject.toml` for pinned dependency ranges.

## Requirements

- **Python 3.12+**
- Recommended: **[uv](https://docs.astral.sh/uv/)** or `pip` for installs.

## Setup

```bash
# From repository root
uv sync
# or: pip install -e .
```

For **accurate** (rendered) crawl mode install the optional extra and browser binaries:

```bash
uv sync --extra render
playwright install chromium
```

(`pip install playwright` plus `playwright install chromium` is equivalent if you do not use uv extras.)

## Configuration

- Copy `.env.example` to `.env` for runtime variables (see the example file for **PSI** and **GSC** setup notes). Do not commit secrets.
- **PSI:** set `PSI_API_KEY` in `.env` when you want PageSpeed Insights lab data. The key must belong to a Google Cloud project with the PageSpeed Insights API enabled.
- **GSC:** the app uses the **OAuth desktop** flow via `client_secrets.json` and `token.json` beside the `hype_frog` package (see `.env.example`). The signed-in user needs Search Console access to a property that matches the crawl target; the code requests read-only scope `https://www.googleapis.com/auth/webmasters.readonly`.
- Interactive runs prompt for crawl profile, suite mode, checkpoint interval, and optional previous workbook path.

## Running

From the repository root, install the package into the uv environment (once per clone or after layout changes), then start the CLI:

```bash
uv sync
uv run hype-frog
# equivalent:
uv run python -m hype_frog.main
```

Follow CLI prompts for target URL or sitemap, limits, and profiles.

### Non-interactive quick test (10 URLs)

Smoke-test the full pipeline (sitemap cap, faster profile, full workbook suite, PSI disabled, no checkpoint prompts) without typing at the console:

```bash
uv sync --extra render   # optional: real Playwright rendering for accurate mode
playwright install chromium
uv run python -m hype_frog.main --quick-test
```

If Playwright is not installed, accurate mode falls back to fast HTTP with a warning; the run still completes. The preset uses the African Marketing Confederation page sitemap (10 URLs), crawl mode **accurate**, safety profile **faster** (4 workers, 1.5s delay), and **full** SEO suite output under `reports/latest/` unless `HF_OUTPUT_FILENAME` overrides it.

**`ModuleNotFoundError: No module named 'hype_frog'`** means the editable project is not installed in the active venv. Run **`uv sync`** from the repo root (not only `uv venv` / manual `pip install` of dependencies). Then retry `uv run …`.

## Tests

```bash
uv run pytest
```

Re-run the suite after substantive changes to crawl, pipeline, or reporting code.

## Architecture (summary)

Detailed breakdown lives under **`./docs/`** (modular markdown only):

- [`docs/architecture_overview.md`](docs/architecture_overview.md) — layers and data flow.
- [`docs/crawler_engine.md`](docs/crawler_engine.md) — fetch modes, retries, extraction contract.
- [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) — integrity, TOC, hub rules.
- [`docs/data_contracts.md`](docs/data_contracts.md) — row shapes and additive key policy.

## Governance

Cursor rules live in **`.cursor/rules/`** as scoped `.mdc` modules (`crawler_agent.mdc`, `excel_agent.mdc`). The root **`.cursorrules`** file summarizes stack and safety expectations; deeper reporting and crawler invariants are documented under **`./docs/`** and should stay consistent with those rules.

## Policy notes

- **`./.old/`** is excluded from automated documentation and analysis in this project.
- Prefer **additive** changes to established pipeline row keys unless a migration is explicitly approved.
