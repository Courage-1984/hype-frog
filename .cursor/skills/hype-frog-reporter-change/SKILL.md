---
name: hype-frog-reporter-change
description: Enforce 3-way sheet lock and reporter guardrails when editing hype-frog Excel output.
---

# Reporter change checklist

Before completing any reporter change:

- [ ] Sheet name in `sheets/config.py`, `workbook_layout.py`, `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`
- [ ] No mutation of upstream row dicts
- [ ] String sanitization on all cell writes
- [ ] Hub Action Required literals unchanged unless updating `determine_action_required` + `conditional.py`
- [ ] `uv run pytest tests/reporter/ -q --tb=short`

See `.cursor/rules/excel_engine.mdc`.
