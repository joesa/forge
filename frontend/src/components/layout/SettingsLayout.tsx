import { Link, useLocation } from 'react-router-dom'

interface SettingsLayoutProps {
  children: React.ReactNode
}

const settingsItems = [
  { icon: '👤', label: 'Profile', path: '/settings/profile' },
  { icon: '🤖', label: 'AI Providers', path: '/settings/ai-providers' },
  { icon: '⚡', label: 'Model Routing', path: '/settings/model-routing' },
  { icon: '🔗', label: 'Integrations', path: '/settings/integrations' },
  { icon: '🔑', label: 'API Keys', path: '/settings/api-keys' },
  { icon: '🔒', label: 'Security', path: '/settings/security' },
  { icon: '💳', label: 'Billing', path: '/settings/billing' },
]

export default function SettingsLayout({ children }: SettingsLayoutProps) {
  const location = useLocation()

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 62px)' }}>
      {/* Settings sub-sidebar */}
      <div
        id="settings-sub-sidebar"
        style={{
          width: 200,
          borderRight: '1px solid rgba(255,255,255,0.06)',
          padding: '20px 0',
          flexShrink: 0,
        }}
      >
        {settingsItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              id={`settings-nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                height: 34,
                padding: '0 16px',
                marginBottom: 2,
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                color: isActive ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                background: isActive ? 'rgba(99,217,255,0.08)' : 'transparent',
                borderLeft: isActive ? '2px solid #63d9ff' : '2px solid transparent',
                borderRadius: isActive ? '0 6px 6px 0' : 6,
                textDecoration: 'none',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = '#e8e8f0'
                  e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = 'rgba(232,232,240,0.45)'
                  e.currentTarget.style.background = 'transparent'
                }
              }}
            >
              <span style={{ fontSize: 13 }}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          )
        })}
      </div>

      {/* Settings content */}
      <div style={{ flex: 1, maxWidth: 900, padding: '32px 36px' }}>
        {children}
      </div>
    </div>
  )
}
