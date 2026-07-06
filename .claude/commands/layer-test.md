Run pytest for a single hype-frog layer. Replace `$ARG` with the tests package name (e.g. `reporter`, `crawler`, `orchestration`).

```powershell
uv run pytest tests/$ARG/ -q --tb=short
```

Examples:
- `uv run pytest tests/reporter/ -q --tb=short`
- `uv run pytest tests/crawler/ -q --tb=short`
- `uv run pytest tests/orchestration/ -q --tb=short`
