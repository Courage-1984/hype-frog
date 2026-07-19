export const meta = {
  name: 'layer-boundary-audit',
  description:
    'Fan out read-only agents across hype-frog packages to flag layer-boundary smells (reporter mutating rows, orchestration domain logic, print in pipeline/orchestration).',
}

const packages = [
  'core',
  'crawler',
  'extractors',
  'validators',
  'analysis',
  'pipeline',
  'rules',
  'reporter',
  'orchestration',
  'checkpoint',
  'snapshots',
  'diagnostics',
]

const audits = await pipeline(packages, (pkg) =>
  agent(
    `Read-only audit of src/hype_frog/${pkg}/ for layer-boundary violations.

Dependency direction: core/config → crawler/extractors → validators/analysis → pipeline/rules → reporter; orchestration coordinates only.

Flag only concrete smells with file paths:
1) reporter/ mutating upstream row dicts
2) orchestration/ implementing extraction/scoring/formatting domain logic
3) print() in pipeline/ or orchestration/
4) extractors/ or validators/ importing reporter/
5) os.environ outside core/env_vars.py
6) conflating checkpoint vs snapshots vs delta stores

Return JSON: { "package": "${pkg}", "findings": [ { "severity": "high|medium|low", "path": "...", "issue": "..." } ] }. Empty findings array if clean.`,
    {
      label: pkg,
      schema: {
        type: 'object',
        required: ['package', 'findings'],
        properties: {
          package: { type: 'string' },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              required: ['severity', 'path', 'issue'],
              properties: {
                severity: { type: 'string' },
                path: { type: 'string' },
                issue: { type: 'string' },
              },
            },
          },
        },
      },
    },
  ),
)

const merged = audits
  .filter(Boolean)
  .flatMap((a) => (a.findings || []).map((f) => ({ ...f, package: a.package })))

const rank = { high: 0, medium: 1, low: 2 }
merged.sort((a, b) => (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9))

return {
  findingCount: merged.length,
  findings: merged.slice(0, 50),
}
