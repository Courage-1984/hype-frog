Run the full pre-export smoke gate before a production crawl: strict preflight (incl. live PSI probe) → pytest subset → ~80 synthetic-URL mocked crawl → real enrichment + export → workbook audit (~8–15 min).

```powershell
uv run hype-frog --full-smoke-test
```

Requires `PSI_API_KEY` and `secrets/token.json` (GSC OAuth). Use `--full-smoke-test-fast` to skip preflight and pytest (~3–6 min). Tune volume: `HF_FULL_SMOKE_URL_COUNT=120`.
