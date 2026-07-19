export const meta = {
  name: 'reporter-sheet-lock-audit',
  description:
    'Verify workbook sheet names stay locked across sheets/config.py, workbook_layout.py, and engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS.',
}

const inventory = await agent(
  `Read-only: extract sheet-name string constants / tab-order entries / TOC description keys from:
1) src/hype_frog/reporter/sheets/config.py
2) src/hype_frog/reporter/sheets/workbook_layout.py (VISIBLE_WORKBOOK_TAB_ORDER and ADVANCED_WORKBOOK_TAB_ORDER)
3) src/hype_frog/reporter/engine_guardrails.py (_TOC_FRIENDLY_DESCRIPTIONS keys)

Return JSON with three string arrays: configNames, layoutNames, tocNames. Deduplicate within each array. Exact sheet title strings only.`,
  {
    label: 'inventory',
    schema: {
      type: 'object',
      required: ['configNames', 'layoutNames', 'tocNames'],
      properties: {
        configNames: { type: 'array', items: { type: 'string' } },
        layoutNames: { type: 'array', items: { type: 'string' } },
        tocNames: { type: 'array', items: { type: 'string' } },
      },
    },
  },
)

const diff = await agent(
  `Compare these three sheet-name sets for 3-way lock drift.

configNames: ${JSON.stringify(inventory.configNames)}
layoutNames: ${JSON.stringify(inventory.layoutNames)}
tocNames: ${JSON.stringify(inventory.tocNames)}

Report names present in some sets but not others. Ignore intentional advanced-vs-visible differences only if clearly documented in code comments you read; otherwise flag missing TOC or layout entries.

Return JSON: { "drifts": [ { "name": "...", "missingFrom": ["config"|"layout"|"toc"], "note": "..." } ], "ok": boolean }`,
  {
    label: 'diff',
    schema: {
      type: 'object',
      required: ['drifts', 'ok'],
      properties: {
        ok: { type: 'boolean' },
        drifts: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name', 'missingFrom', 'note'],
            properties: {
              name: { type: 'string' },
              missingFrom: { type: 'array', items: { type: 'string' } },
              note: { type: 'string' },
            },
          },
        },
      },
    },
  },
)

return diff
