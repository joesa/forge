import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'
import { useApiKeys, useCreateApiKey, useDeleteApiKey } from '@/hooks/queries/useSettings'
import { useToast } from '@/components/shared/Toast'
import { SkeletonRow } from '@/components/shared/Skeleton'

interface ApiKeyData {
  id: string
  name: string
  prefix?: string
  last_used?: string | null
  expires_at?: string | null
  created_at: string
}

export default function ApiKeysPage() {
  const { data, isLoading } = useApiKeys()
  const createMutation = useCreateApiKey()
  const deleteMutation = useDeleteApiKey()
  const toast = useToast()

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showSuccessModal, setShowSuccessModal] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [expiry, setExpiry] = useState('never')
  const [createdKeyValue, setCreatedKeyValue] = useState('')
  const [copied, setCopied] = useState(false)

  const keys: ApiKeyData[] = data?.keys ?? []

  const handleCreate = () => {
    const expiresInDays = expiry === 'never' ? undefined : parseInt(expiry, 10)
    createMutation.mutate(
      { name: keyName, expires_in_days: expiresInDays },
      {
        onSuccess: (result: Record<string, unknown>) => {
          setShowCreateModal(false)
          setCreatedKeyValue((result as { key?: string }).key ?? 'forge_key_' + Math.random().toString(36).slice(2))
          setShowSuccessModal(true)
          toast.success('API key created')
        },
        onError: () => toast.error('Failed to create API key'),
      },
    )
  }

  const handleDelete = (id: string) => {
    if (!window.confirm('Delete this API key? This cannot be undone.')) return
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success('API key deleted'),
      onError: () => toast.error('Failed to delete API key'),
    })
  }

  const copyKey = async () => {
    await navigator.clipboard.writeText(createdKeyValue)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <AppShell>
      <SettingsLayout>
        <div>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0' }}>API Keys</h1>
            <button className="btn btn-primary" onClick={() => { setKeyName(''); setExpiry('never'); setShowCreateModal(true) }}>
              + Create API Key
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/api-keys</span>
          </div>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 26 }}>
            Manage your API keys for programmatic access
          </p>

          {/* Keys Table */}
          <div style={{
            background: '#0d0d1f',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12,
            overflow: 'hidden',
          }}>
            {/* TH */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 120px 120px 80px',
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              textTransform: 'uppercase' as const,
              letterSpacing: '1px',
              color: 'rgba(232,232,240,0.40)',
            }}>
              <span>Name</span>
              <span>Prefix</span>
              <span>Last Used</span>
              <span>Expires</span>
              <span>Actions</span>
            </div>

            {isLoading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : keys.length > 0 ? (
              keys.map((k: ApiKeyData) => (
                <div key={k.id} style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 120px 120px 120px 80px',
                  padding: '12px 16px',
                  alignItems: 'center',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>{k.name}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#63d9ff' }}>
                    {k.prefix ?? '••••'}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                    {k.last_used ? new Date(k.last_used).toLocaleDateString() : 'Never'}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                    {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never'}
                  </span>
                  <button
                    className="btn btn-danger btn-sm"
                    style={{ height: 26, fontSize: 10 }}
                    onClick={() => handleDelete(k.id)}
                    disabled={deleteMutation.isPending}
                  >
                    Delete
                  </button>
                </div>
              ))
            ) : (
              <div style={{ padding: 40, textAlign: 'center' }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>🔑</div>
                <div style={{ fontSize: 13, color: '#e8e8f0', fontWeight: 600, marginBottom: 4 }}>No API keys</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)' }}>Create one to get started</div>
              </div>
            )}
          </div>
        </div>

        {/* Create Key Modal */}
        {showCreateModal && (
          <div
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
              zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onClick={() => setShowCreateModal(false)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: '#0d0d1f',
                border: '1px solid rgba(99,217,255,0.22)',
                borderRadius: 16, padding: 34, maxWidth: 420, width: '100%',
                animation: 'fade-in 200ms ease',
              }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 800, color: '#e8e8f0', marginBottom: 18 }}>Create API Key</h2>
              <div style={{ marginBottom: 14 }}>
                <label className="lbl">Key Name</label>
                <input className="input" placeholder="e.g. production-server" value={keyName} onChange={(e) => setKeyName(e.target.value)} />
              </div>
              <div style={{ marginBottom: 18 }}>
                <label className="lbl">Expires</label>
                <select
                  className="input"
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                  style={{ cursor: 'pointer' }}
                >
                  <option value="never">Never</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                </select>
              </div>
              <div style={{ display: 'flex', gap: 9 }}>
                <button className="btn btn-ghost" onClick={() => setShowCreateModal(false)} style={{ flex: 1 }}>Cancel</button>
                <button
                  className="btn btn-primary"
                  onClick={handleCreate}
                  disabled={!keyName || createMutation.isPending}
                  style={{ flex: 1 }}
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Modal — one-time key display */}
        {showSuccessModal && (
          <div
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.80)', backdropFilter: 'blur(10px)',
              zIndex: 501, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <div
              style={{
                background: '#0d0d1f',
                border: '1px solid rgba(245,200,66,0.25)',
                borderRadius: 16, padding: 34, maxWidth: 460, width: '100%',
                animation: 'fade-in 200ms ease',
              }}
            >
              <div style={{ fontSize: 11, color: '#f5c842', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                ⚠️ This key will only be shown once
              </div>
              <div style={{
                background: '#04040a',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '12px 14px',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                color: '#63d9ff',
                wordBreak: 'break-all',
                marginBottom: 18,
              }}>
                {createdKeyValue}
              </div>
              <button
                className="btn btn-primary"
                style={{ width: '100%', marginBottom: 9 }}
                onClick={copyKey}
              >
                {copied ? '✓ Copied!' : '⎘ Copy to Clipboard'}
              </button>
              <button
                className="btn btn-ghost"
                style={{ width: '100%' }}
                onClick={() => { setShowSuccessModal(false); setCreatedKeyValue('') }}
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
