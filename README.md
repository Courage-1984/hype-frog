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

For **accurate** (rendered) crawl mode you typically need:

```bash
pip install playwright
playwright install chromium
```

(Exact commands may match your environment manager.)

## Configuration

- Copy or create a `.env` file for environment variables used at runtime (output paths, optional API credentials for auxiliary metrics, etc.). Do not commit secrets.
- Interactive runs prompt for crawl profile, suite mode, checkpoint interval, and optional previous workbook path.

## Running

```bash
python main.py
```

Follow CLI prompts for target URL or sitemap, limits, and profiles.

## Tests

```bash
python -m pytest tests test_excel_engine.py -q
```

Re-run the suite after substantive changes to crawl, pipeline, or reporting code.

## Architecture (summary)

Detailed breakdown lives under **`./docs/`** (modular markdown only):

- [`docs/architecture_overview.md`](docs/architecture_overview.md) — layers and data flow.
- [`docs/crawler_engine.md`](docs/crawler_engine.md) — fetch modes, retries, extraction contract.
- [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) — integrity, TOC, hub rules.
- [`docs/data_contracts.md`](docs/data_contracts.md) — row shapes and additive key policy.

## Governance

Cursor rules live in **`.cursor/rules/`** as `.mdc` modules (`architecture`, `crawler_engine`, `excel_reporters`, `auto_documentation`, `vibe_coding_guardrails`, plus legacy `*_agent` stubs that point to the expanded files).

## Policy notes

- **`./.old/`** is excluded from automated documentation and analysis in this project.
- Prefer **additive** changes to established pipeline row keys unless a migration is explicitly approved.
