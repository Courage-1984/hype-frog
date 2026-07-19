---
name: reporter-change
description: Checklist before finishing reporter/Excel edits (3-way sheet lock, sanitize, Hub literals). Use when editing reporter/ or workbook tabs.
---

# Reporter change checklist

- [ ] Sheet name in `sheets/config.py`, `workbook_layout.py`, `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`
- [ ] No mutation of upstream row dicts
- [ ] String sanitization on all cell writes
- [ ] Hub Action Required literals unchanged unless updating `determine_action_required` + `conditional.py` + tooltip together: `Complete` | `Needs Copy` | `Needs Optimisation`
- [ ] `uv run pytest tests/reporter/ -q --tb=short`

Rule: `.claude/rules/excel-integrity.md`
