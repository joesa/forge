import { Link, useLocation } from 'react-router-dom'

interface NavItem {
  icon: string
  label: string
  path: string
  indent?: boolean
}

const mainNav: NavItem[] = [
  { icon: '🏠', label: 'Dashboard', path: '/dashboard' },
  { icon: '📁', label: 'Projects', path: '/projects' },
  { icon: '💡', label: 'Ideate', path: '/ideate' },
]

const settingsNav: NavItem[] = [
  { icon: '👤', label: 'Profile', path: '/settings/profile', indent: true },
  { icon: '🤖', label: 'AI Providers', path: '/settings/ai-providers', indent: true },
  { icon: '⚡', label: 'Model Routing', path: '/settings/model-routing', indent: true },
  { icon: '🔗', label: 'Integrations', path: '/settings/integrations', indent: true },
  { icon: '🔑', label: 'API Keys', path: '/settings/api-keys', indent: true },
  { icon: '🔒', label: 'Security', path: '/settings/security', indent: true },
  { icon: '💳', label: 'Billing', path: '/settings/billing', indent: true },
]

function SidebarItem({ item, isActive }: { item: NavItem; isActive: boolean }) {
  return (
    <Link
      to={item.path}
      id={`sidebar-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        height: 38,
        padding: isActive ? '0 11px 0 12px' : `0 11px 0 ${item.indent ? 32 : 11}px`,
        borderRadius: isActive ? '0 6px 6px 0' : 6,
        marginBottom: 2,
        color: isActive ? '#63d9ff' : 'rgba(232,232,240,0.45)',
        background: isActive ? 'rgba(99,217,255,0.10)' : 'transparent',
        borderLeft: isActive ? '2px solid #63d9ff' : '2px solid transparent',
        marginLeft: isActive ? -1 : 0,
        fontSize: 13,
        fontWeight: 500,
        textDecoration: 'none',
        transition: 'all 0.15s',
        cursor: 'pointer',
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
      <span style={{ fontSize: 15, width: 20, textAlign: 'center' }}>{item.icon}</span>
      <span>{item.label}</span>
    </Link>
  )
}

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside
      id="main-sidebar"
      style={{
        position: 'fixed',
        left: 0,
        top: 62,
        bottom: 0,
        width: 220,
        background: 'rgba(4,4,10,0.70)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        padding: '14px 10px',
        overflowY: 'auto',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* User profile */}
      <div
        style={{
          padding: '8px 10px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
            fontWeight: 700,
            color: '#04040a',
            flexShrink: 0,
          }}
        >
          JD
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e8e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Joe Developer
          </div>
        </div>
        <span className="tag tag-f" style={{ marginLeft: 'auto', flexShrink: 0 }}>PRO</span>
      </div>

      {/* Main nav */}
      <div style={{ marginBottom: 6 }}>
        {mainNav.map((item) => (
          <SidebarItem key={item.path} item={item} isActive={location.pathname === item.path || location.pathname.startsWith(item.path + '/')} />
        ))}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '6px 0 10px' }} />

      {/* Settings label */}
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          textTransform: 'uppercase',
          color: 'rgba(232,232,240,0.20)',
          padding: '4px 11px 6px',
          letterSpacing: 1,
        }}
      >
        SETTINGS
      </div>

      {/* Settings nav */}
      <div style={{ marginBottom: 6 }}>
        {settingsNav.map((item) => (
          <SidebarItem key={item.path} item={item} isActive={location.pathname === item.path} />
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Token usage */}
      <div
        style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          paddingTop: 12,
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(232,232,240,0.30)',
            marginBottom: 6,
          }}
        >
          TOKEN USAGE
        </div>
        <div
          style={{
            height: 3,
            background: 'rgba(255,255,255,0.07)',
            borderRadius: 2,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: '42%',
              height: '100%',
              background: '#63d9ff',
              borderRadius: 2,
            }}
          />
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(232,232,240,0.30)',
            marginTop: 4,
          }}
        >
          847k / 2M tokens
        </div>
      </div>
    </aside>
  )
}
