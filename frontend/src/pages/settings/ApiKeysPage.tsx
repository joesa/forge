import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

interface ApiKey {
  id: string
  name: string
  prefix: string
  lastUsed: string
  expires: string
}

const mockKeys: ApiKey[] = [
  { id: 'k1', name: 'Production App', prefix: 'forge_pk_...x3k1', lastUsed: '2 hours ago', expires: 'Never' },
  { id: 'k2', name: 'CI/CD Pipeline', prefix: 'forge_pk_...m7n2', lastUsed: '1 day ago', expires: '30 days' },
  { id: 'k3', name: 'Development', prefix: 'forge_pk_...q9p4', lastUsed: '5 min ago', expires: '90 days' },
]

export default function ApiKeysPage() {
  const [keys] = useState(mockKeys)
  const [showCreate, setShowCreate] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [keyExpiry, setKeyExpiry] = useState('never')
  const generatedKey = 'forge_pk_live_2xK9mN4vR7bQ3pL8wJ6cF1dH5aE0gT4yU9iO2kS7zX3'

  const handleCreate = () => {
    setShowCreate(false)
    setShowSuccess(true)
  }

  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div>
              <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>API Keys</h1>
              <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/api-keys</span>
            </div>
            <button className="btn btn-primary" onClick={() => { setShowCreate(true); setKeyName(''); setKeyExpiry('never') }} id="create-key-btn">
              + Create API Key
            </button>
          </div>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 26 }}>
            Manage your API keys for programmatic access
          </p>

          {/* Keys table */}
          <div
            id="keys-table"
            style={{
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Name', 'Prefix', 'Last Used', 'Expires', 'Actions'].map((h) => (
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
                {keys.map((k, i) => (
                  <tr key={k.id} style={{ borderBottom: i < keys.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>{k.name}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.42)' }}>{k.prefix}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>{k.lastUsed}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>{k.expires}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <button className="btn btn-danger btn-sm" style={{ height: 26, fontSize: 9 }}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create Key Modal */}
        {showCreate && (
          <div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            onClick={() => setShowCreate(false)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{ background: '#0d0d1f', border: '1px solid rgba(99,217,255,0.22)', borderRadius: 16, padding: 34, maxWidth: 420, width: '100%', animation: 'fade-in 200ms ease' }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 800, color: '#e8e8f0', marginBottom: 16 }}>Create API Key</h2>
              <div style={{ marginBottom: 12 }}>
                <label className="lbl" htmlFor="key-name">KEY NAME</label>
                <input id="key-name" className="input" placeholder="My API Key" value={keyName} onChange={(e) => setKeyName(e.target.value)} />
              </div>
              <div style={{ marginBottom: 18 }}>
                <label className="lbl" htmlFor="key-expiry">EXPIRES</label>
                <select id="key-expiry" className="input" value={keyExpiry} onChange={(e) => setKeyExpiry(e.target.value)} style={{ cursor: 'pointer' }}>
                  <option value="never">Never</option>
                  <option value="30d">30 days</option>
                  <option value="90d">90 days</option>
                </select>
              </div>
              <div style={{ display: 'flex', gap: 9 }}>
                <button className="btn btn-ghost" onClick={() => setShowCreate(false)} style={{ flex: 1 }}>Cancel</button>
                <button className="btn btn-primary" onClick={handleCreate} style={{ flex: 1 }}>Create</button>
              </div>
            </div>
          </div>
        )}

        {/* Success Modal */}
        {showSuccess && (
          <div
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            onClick={() => setShowSuccess(false)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{ background: '#0d0d1f', border: '1px solid rgba(245,200,66,0.30)', borderRadius: 16, padding: 34, maxWidth: 460, width: '100%', animation: 'fade-in 200ms ease' }}
            >
              <div style={{ fontSize: 11, color: '#f5c842', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                ⚠️ This key will only be shown once
              </div>
              <div
                style={{
                  background: '#04040a',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8,
                  padding: '12px 14px',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  color: '#63d9ff',
                  wordBreak: 'break-all',
                  marginBottom: 14,
                }}
              >
                {generatedKey}
              </div>
              <button
                className="btn btn-primary"
                style={{ width: '100%', marginBottom: 8 }}
                onClick={() => navigator.clipboard.writeText(generatedKey)}
              >
                ⎘ Copy to Clipboard
              </button>
              <button
                className="btn btn-ghost"
                style={{ width: '100%' }}
                onClick={() => setShowSuccess(false)}
              >
                I&apos;ve saved this key safely
              </button>
            </div>
          </div>
        )}
      </SettingsLayout>
    </AppShell>
  )
}
