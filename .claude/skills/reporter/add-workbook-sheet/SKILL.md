---
name: add-workbook-sheet
description: Add a new Excel workbook sheet with 3-way lock and export wiring. Invoke manually for new tabs.
disable-model-invocation: true
---

# Add workbook sheet

Follow @references/checklist.md end-to-end.

Verify:
```powershell
uv run pytest tests/reporter/ -q --tb=short
```

Rule: `.claude/rules/excel-integrity.md`. Prefer `--regen-report` for iteration.
