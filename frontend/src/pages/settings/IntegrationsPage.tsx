import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

interface Integration {
  name: string
  icon: string
  desc: string
  connected: boolean
  details?: string
}

const integrations: Integration[] = [
  { name: 'GitHub', icon: '🐙', desc: 'Push generated code to your repositories', connected: true, details: 'joe-dev · 12 repos synced' },
  { name: 'Vercel', icon: '▲', desc: 'Deploy directly to Vercel hosting', connected: true, details: 'team-forge · 3 active deployments' },
  { name: 'Cloudflare', icon: '☁', desc: 'Deploy to Cloudflare Pages and Workers', connected: false },
  { name: 'Netlify', icon: '◇', desc: 'Deploy to Netlify hosting', connected: false },
  { name: 'Slack', icon: '💬', desc: 'Get build and deploy notifications', connected: false },
  { name: 'Discord', icon: '🎮', desc: 'Build status notifications in Discord', connected: false },
]

export default function IntegrationsPage() {
  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Integrations</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/integrations</span>
          </div>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 26 }}>
            Connect FORGE to your development tools and services
          </p>

          <div id="integrations-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {integrations.map((intg) => (
              <div
                key={intg.name}
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
                      fontSize: 16,
                      flexShrink: 0,
                    }}
                  >
                    {intg.icon}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0' }}>{intg.name}</span>
                      {intg.connected && <span className="tag tag-j">Connected</span>}
                    </div>
                    <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.35)', marginTop: 2 }}>
                      {intg.connected ? intg.details : intg.desc}
                    </div>
                  </div>
                </div>
                {intg.connected ? (
                  <div style={{ display: 'flex', gap: 5 }}>
                    <button className="btn btn-ghost btn-sm">Configure</button>
                    <button className="btn btn-danger btn-sm">Disconnect</button>
                  </div>
                ) : (
                  <button className="btn btn-secondary btn-sm">Connect →</button>
                )}
              </div>
            ))}
          </div>
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
