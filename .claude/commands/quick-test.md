Run the hype-frog quick-test gate: preflight checks → focused pytest subset → live 10-URL BFS crawl (depth 2, full suite) → workbook audit.

```powershell
uv run hype-frog --quick-test
```

Pass `--quick-test-fast` to skip preflight and pytest (crawl + audit only, ~5 min).
Pass `HF_MAX_DEPTH=1` to reduce crawl depth for faster iteration.
