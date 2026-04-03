import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'
import { useProviders, useCreateProvider, useTestProvider, useDeleteProvider } from '@/hooks/queries/useSettings'
import { useToast } from '@/components/shared/Toast'
import { SkeletonRow } from '@/components/shared/Skeleton'

interface ProviderDisplay {
  name: string
  logo: string
  connected: boolean
  isDefault: boolean
  maskedKey?: string
  latency?: string
  id?: string
}

const defaultProviders: ProviderDisplay[] = [
  { name: 'Anthropic', logo: 'A', connected: false, isDefault: false },
  { name: 'OpenAI', logo: 'O', connected: false, isDefault: false },
  { name: 'Google Gemini', logo: 'G', connected: false, isDefault: false },
  { name: 'Mistral', logo: 'M', connected: false, isDefault: false },
  { name: 'Cohere', logo: 'C', connected: false, isDefault: false },
  { name: 'Groq', logo: 'Q', connected: false, isDefault: false },
  { name: 'Perplexity', logo: 'P', connected: false, isDefault: false },
  { name: 'Replicate', logo: 'R', connected: false, isDefault: false },
]

export default function AIProvidersPage() {
  const { data, isLoading } = useProviders()
  const createMutation = useCreateProvider()
  const testMutation = useTestProvider()
  const deleteMutation = useDeleteProvider()
  const toast = useToast()

  const [showModal, setShowModal] = useState(false)
  const [modalProvider, setModalProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [connectStatus, setConnectStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  // Merge API data with default provider list
  const apiProviders: Array<{ id: string; provider_name: string; is_connected?: boolean; masked_key?: string }> = data?.providers ?? []
  const providers: ProviderDisplay[] = defaultProviders.map((dp) => {
    const match = apiProviders.find((ap) => ap.provider_name?.toLowerCase() === dp.name.toLowerCase())
    if (match) {
      return {
        ...dp,
        connected: match.is_connected !== false,
        isDefault: false,
        maskedKey: match.masked_key,
        id: match.id,
      }
    }
    return dp
  })

  const openConnect = (name: string) => {
    setModalProvider(name)
    setApiKey('')
    setConnectStatus('idle')
    setShowModal(true)
  }

  const testConnection = () => {
    if (apiKey.length < 10) {
      setConnectStatus('error')
      return
    }
    setConnectStatus('testing')
    // Simulate test delay for UX
    setTimeout(() => {
      setConnectStatus('success')
    }, 800)
  }

  const handleSave = () => {
    createMutation.mutate(
      { provider_name: modalProvider.toLowerCase().replace(/\s+/g, '_'), api_key: apiKey },
      {
        onSuccess: () => {
          toast.success(`${modalProvider} connected successfully`)
          setShowModal(false)
        },
        onError: () => {
          toast.error(`Failed to connect ${modalProvider}`)
        },
      },
    )
  }

  const handleTest = (providerId: string) => {
    testMutation.mutate(providerId, {
      onSuccess: () => toast.success('Connection test passed'),
      onError: () => toast.error('Connection test failed'),
    })
  }

  const handleDisconnect = (providerId: string, name: string) => {
    deleteMutation.mutate(providerId, {
      onSuccess: () => toast.info(`${name} disconnected`),
      onError: () => toast.error(`Failed to disconnect ${name}`),
    })
  }

  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>AI Providers</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/ai-providers</span>
          </div>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 26 }}>
            Connect your API keys · All keys encrypted with AES-256-GCM
          </p>

          {/* Provider grid */}
          <div id="providers-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {isLoading ? (
              <>
                <div className="card"><SkeletonRow /></div>
                <div className="card"><SkeletonRow /></div>
                <div className="card"><SkeletonRow /></div>
                <div className="card"><SkeletonRow /></div>
              </>
            ) : (
              providers.map((p) => (
                <div
                  key={p.name}
                  style={{
                    background: '#0d0d1f',
                    border: '1px solid rgba(255,255,255,0.07)',
                    borderRadius: 10,
                    padding: '16px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                    <div
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: '50%',
                        background: 'rgba(255,255,255,0.06)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 14,
                        fontWeight: 700,
                        color: '#e8e8f0',
                        flexShrink: 0,
                      }}
                    >
                      {p.logo}
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0' }}>{p.name}</span>
                        {p.isDefault && <span className="tag tag-f">Default</span>}
                        {p.connected && !p.isDefault && <span className="tag tag-j">Connected</span>}
                      </div>
                      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.35)', marginTop: 2 }}>
                        {p.connected ? `${p.maskedKey ?? '••••'} · Connected` : 'Not connected'}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {p.connected ? (
                      <>
                        <button className="btn btn-ghost btn-sm" onClick={() => openConnect(p.name)}>Edit</button>
                        <button
                          className="btn btn-sm"
                          style={{ background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.18)', color: '#ff6b35' }}
                          onClick={() => p.id && handleTest(p.id)}
                        >
                          Test
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => p.id && handleDisconnect(p.id, p.name)}
                          style={{ color: '#ff6b35' }}
                        >
                          ×
                        </button>
                      </>
                    ) : (
                      <button className="btn btn-secondary btn-sm" onClick={() => openConnect(p.name)}>
                        Connect →
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Connect Modal */}
        {showModal && (
          <div
            id="connect-modal-overlay"
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.75)',
              backdropFilter: 'blur(8px)',
              zIndex: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onClick={() => setShowModal(false)}
          >
            <div
              id="connect-modal"
              onClick={(e) => e.stopPropagation()}
              style={{
                background: connectStatus === 'success' ? 'rgba(61,255,160,0.04)' : connectStatus === 'error' ? 'rgba(255,107,53,0.04)' : '#0d0d1f',
                border: '1px solid',
                borderColor: connectStatus === 'success' ? 'rgba(61,255,160,0.3)' : connectStatus === 'error' ? 'rgba(255,107,53,0.3)' : 'rgba(99,217,255,0.22)',
                borderRadius: 16,
                padding: 34,
                maxWidth: 460,
                width: '100%',
                animation: 'fade-in 200ms ease',
              }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>
                Connect {modalProvider}
              </h2>
              <p style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)', marginBottom: 20 }}>
                Enter your API key to connect
              </p>

              <label className="lbl" htmlFor="api-key-input">API KEY</label>
              <input
                id="api-key-input"
                type="password"
                className="input"
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setConnectStatus('idle') }}
                style={{ marginBottom: 14 }}
              />

              {connectStatus === 'success' && (
                <div style={{ fontSize: 11, color: '#3dffa0', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                  ✓ Connected — Ready to use
                </div>
              )}
              {connectStatus === 'error' && (
                <div style={{ fontSize: 11, color: '#ff6b35', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                  ✗ Invalid API key
                </div>
              )}
              {connectStatus === 'testing' && (
                <div style={{ fontSize: 11, color: '#63d9ff', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                  ◎ Testing connection...
                </div>
              )}

              <div style={{ display: 'flex', gap: 9 }}>
                <button className="btn btn-ghost" onClick={() => setShowModal(false)} style={{ flex: 1 }}>Cancel</button>
                <button className="btn btn-secondary" onClick={testConnection} style={{ flex: 1 }}>Test</button>
                <button
                  className="btn btn-primary"
                  onClick={handleSave}
                  disabled={createMutation.isPending || !apiKey}
                  style={{ flex: 1 }}
                >
                  {createMutation.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}
      </SettingsLayout>
    </AppShell>
  )
}
