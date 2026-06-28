Run credential and environment validation only — no crawl. Checks .env, GSC OAuth, PSI API key + live probe, Playwright/Chromium, semantic engine, optional LLM keys.

```powershell
uv run hype-frog --validate
```

Add `--validate-url "https://example.com/"` to include a live PSI probe against a specific URL.
