import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

interface RouteRow {
  stage: string
  provider: string
  model: string
  fallback: string
  cost: string
}

const initialRoutes: RouteRow[] = [
  { stage: 'Input Layer', provider: 'Anthropic', model: 'claude-sonnet-4', fallback: 'gpt-4o', cost: '$0.08' },
  { stage: 'C-Suite Analysis', provider: 'Anthropic', model: 'claude-sonnet-4', fallback: 'gpt-4o', cost: '$0.24' },
  { stage: 'Synthesis', provider: 'Anthropic', model: 'claude-sonnet-4', fallback: 'gpt-4o', cost: '$0.12' },
  { stage: 'Spec Layer', provider: 'OpenAI', model: 'gpt-4o', fallback: 'claude-sonnet-4', cost: '$0.15' },
  { stage: 'Bootstrap', provider: 'Anthropic', model: 'claude-sonnet-4', fallback: 'gpt-4o', cost: '$0.10' },
  { stage: 'Build (10 agents)', provider: 'Anthropic', model: 'claude-sonnet-4', fallback: 'gpt-4o', cost: '$0.14' },
]

const providers = ['Anthropic', 'OpenAI', 'Google']
const models: Record<string, string[]> = {
  Anthropic: ['claude-sonnet-4', 'claude-opus-4', 'claude-haiku'],
  OpenAI: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
  Google: ['gemini-2.5-pro', 'gemini-2.5-flash'],
}

export default function ModelRoutingPage() {
  const [routes, setRoutes] = useState(initialRoutes)

  const updateRoute = (index: number, field: keyof RouteRow, value: string) => {
    setRoutes((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r))
    )
  }

  const selectStyle: React.CSSProperties = {
    background: '#080812',
    border: '1px solid rgba(255,255,255,0.08)',
    color: '#e8e8f0',
    padding: '4px 9px',
    borderRadius: 5,
    fontSize: 11,
    outline: 'none',
    cursor: 'pointer',
  }

  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Model Routing</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/model-routing</span>
          </div>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 26 }}>
            Configure which AI model handles each pipeline stage
          </p>

          {/* Routing table */}
          <div
            id="routing-table"
            style={{
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              overflow: 'hidden',
              marginBottom: 18,
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Stage', 'Provider', 'Model', 'Fallback', 'Est. Cost'].map((h) => (
                    <th
                      key={h}
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 9,
                        textTransform: 'uppercase',
                        letterSpacing: 1,
                        color: 'rgba(232,232,240,0.30)',
                        padding: '10px 14px',
                        textAlign: 'left',
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        fontWeight: 500,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {routes.map((r, i) => (
                  <tr key={i} style={{ borderBottom: i < routes.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: 700, color: '#e8e8f0' }}>
                      {r.stage}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <select style={selectStyle} value={r.provider} onChange={(e) => updateRoute(i, 'provider', e.target.value)}>
                        {providers.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <select style={selectStyle} value={r.model} onChange={(e) => updateRoute(i, 'model', e.target.value)}>
                        {(models[r.provider] ?? []).map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <select style={selectStyle} value={r.fallback} onChange={(e) => updateRoute(i, 'fallback', e.target.value)}>
                        {Object.values(models).flat().map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#63d9ff', fontWeight: 700 }}>
                      {r.cost}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cost estimator */}
          <div
            id="cost-estimator"
            style={{
              background: 'rgba(99,217,255,0.06)',
              border: '1px solid rgba(99,217,255,0.18)',
              borderRadius: 10,
              padding: 18,
              marginBottom: 18,
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: '#63d9ff', marginBottom: 4 }}>
              Estimated cost per full pipeline run
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#63d9ff', letterSpacing: '-1px', marginBottom: 4 }}>
              ~$0.83
            </div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
              vs. $2.40 with all-Opus · 60% saved via semantic cache
            </div>
          </div>

          <button className="btn btn-primary" id="save-routing">Save Routing</button>
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
