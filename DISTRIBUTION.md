# hype-frog — Standalone Executable Distribution Guide

No Python installation required. Download `hype-frog.exe` and follow the steps below.

---

## What you get

A single `hype-frog.exe` that includes:
- Full crawl engine (fast HTTP + accurate Playwright rendered mode after setup)
- All reporting: multi-sheet Excel workbook, white-label HTML executive report, PDF summary
- Semantic AEO scoring (spaCy NER bundled — no setup needed)
- PSI Lighthouse + CrUX integration
- Google Search Console (Search Analytics + URL Inspection)
- Issue registry, scoring, Fix Plan, Delta comparison

---

## Folder setup

Place these files in **one folder** — that's it:

```
my_audit_folder/
  hype-frog.exe          ← the binary
  .env                   ← your API keys (copy from .env.example and fill in)
  client_secrets.json    ← OAuth Desktop App credentials from Google Cloud Console
  assets/                ← optional: client_logo.png for HTML/PDF branding
    client_logo.png
```

The following are created automatically on first run:
```
  token.json             ← written by --gsc-auth
  logs/                  ← crawl logs
  reports/               ← output workbooks and reports
  .cache/                ← GSC and PSI SQLite caches (speeds up repeat runs)
```

---

## First-time setup (do once)

### 1. Configure `.env`

Copy the block below into a file named `.env` in your folder:

```dotenv
# PageSpeed Insights — get a free key at console.cloud.google.com
PSI_API_KEY=your_key_here

# Optional: LLM search-intent classification (leave blank to skip)
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=

# Optional: override default output filename
# HF_OUTPUT_FILENAME=

# Optional: HTML executive report
# HF_EXPORT_HTML=1
# HF_REPORT_CLIENT_NAME=Client Corp
# HF_REPORT_PREPARED_BY=Your Name
# HF_REPORT_LOGO_PATH=./assets/client_logo.png
# HF_REPORT_BRAND_COLOUR=#1e293b
# HF_REPORT_ACCENT_COLOUR=#2563eb

# Optional: PDF executive summary (bundled in the exe)
# HF_EXPORT_PDF=1
# HF_PDF_LOGO_PATH=./assets/client_logo.png
```

### 2. Google Search Console (GSC) credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Search Console API** and **Search Console API**
3. Create credentials → **OAuth 2.0 Client ID** → Application type: **Desktop app**
4. Download the JSON → rename it `client_secrets.json` → place it in your folder
5. Run the OAuth flow (opens a browser once):
   ```
   hype-frog.exe --gsc-auth
   ```
   This writes `token.json` to your folder. Done — you won't need to re-auth unless the token expires.

### 3. Accurate rendered crawl mode (optional, one-time)

For JavaScript-heavy sites, enable accurate mode by installing the Chromium browser:

```
hype-frog.exe --install-playwright
```

Downloads ~150 MB to a persistent per-user location (`%LOCALAPPDATA%\hype-frog\ms-playwright`) so the browser survives across runs. The crawl engine falls back to fast/HTTP mode automatically if this step is skipped.

---

## Validate your setup

```
hype-frog.exe --validate
```

Prints a PASS/WARN/FAIL report for: GSC credentials, PSI API key, Playwright browser, spaCy NER model, optional LLM keys. Fix any FAIL items before running an audit.

---

## Running an audit

```
hype-frog.exe
```

Interactive prompts will ask for: target URL or sitemap, crawl depth, max URLs, PSI limit, export options.

### Common flags

```
hype-frog.exe                            # interactive prompts
hype-frog.exe --validate                 # check credentials only
hype-frog.exe --gsc-auth                 # refresh GSC token
hype-frog.exe --install-playwright       # install Chromium for accurate mode
hype-frog.exe --export-pdf               # add PDF executive summary
hype-frog.exe --gsc-url-inspection       # enable GSC URL Inspection (up to 50 URLs)
hype-frog.exe --previous-run old.xlsx    # compare against a prior audit
hype-frog.exe --competitors example.com  # competitor benchmarking
```

---

## Troubleshooting

### Windows Defender / antivirus warning

PyInstaller executables are sometimes flagged by antivirus as false positives because they bundle a Python runtime. To allow the file:

**Windows Defender:** Settings → Virus & threat protection → Add an exclusion → File → select `hype-frog.exe`

The exe contains no malware — it is compiled directly from the [hype-frog source code](https://github.com/Courage-1984/hype-frog).

### "Application failed to start" on first launch

The exe extracts its contents to a temp directory on startup (takes 3–10 seconds on first run). If Windows Defender is scanning files mid-extraction, the first launch may fail. Allow the exe in Defender, then try again.

### GSC token expired

Re-run `hype-frog.exe --gsc-auth` to refresh `token.json`.

### PSI quota exceeded

The `PSI_API_KEY` has a daily request quota. Lower `--max-psi-urls` or wait until the quota resets (midnight Pacific time).

---

## Output files

All output is written into `reports/latest/` inside your folder:

| File | Contents |
|---|---|
| `*_audit.xlsx` | Multi-sheet audit workbook (Main, Fix Plan, Issue Register, Diagnostics, …) |
| `*_executive_report.html` | Self-contained HTML report (if `HF_EXPORT_HTML=1`) |
| `*_executive_summary.pdf` | PDF summary (if `--export-pdf` flag or `HF_EXPORT_PDF=1`) |

---

## Building from source

Developers only — requires Python 3.12 and `uv`:

```powershell
git clone https://github.com/Courage-1984/hype-frog
cd hype-frog
uv sync --extra dev --extra semantic --extra render
uv run python build_exe.py
# Output: dist/hype-frog.exe
```
