import { Link } from 'react-router-dom'
import HexLogo from '@/components/shared/HexLogo'

interface TopNavProps {
  variant?: 'landing' | 'authenticated' | 'minimal'
  rightContent?: React.ReactNode
}

export default function TopNav({ variant = 'authenticated', rightContent }: TopNavProps) {
  if (variant === 'landing') {
    return (
      <nav
        id="top-nav-landing"
        style={{
          height: 62,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 28px',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          background: 'rgba(4,4,10,0.88)',
          backdropFilter: 'blur(24px)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <HexLogo />
        <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          <Link to="/login" className="btn btn-ghost btn-sm" id="nav-login-btn">
            Log In
          </Link>
          <Link to="/projects/new" className="btn btn-primary btn-sm" id="nav-start-btn">
            Start Building →
          </Link>
        </div>
      </nav>
    )
  }

  if (variant === 'minimal') {
    return (
      <nav
        id="top-nav-minimal"
        style={{
          height: 62,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 28px',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          background: 'rgba(4,4,10,0.88)',
          backdropFilter: 'blur(24px)',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <HexLogo />
        {rightContent && <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>{rightContent}</div>}
      </nav>
    )
  }

  return (
    <nav
      id="top-nav-auth"
      style={{
        height: 62,
        display: 'flex',
        alignItems: 'center',
        padding: '0 28px',
        gap: 14,
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: 'rgba(4,4,10,0.88)',
        backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <HexLogo />
      <div style={{ flex: 1 }} />
      <span
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: '#3dffa0',
        }}
      >
        ● All systems normal
      </span>
      <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.08)' }} />
      <div
        id="user-avatar"
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 700,
          color: '#04040a',
          cursor: 'pointer',
        }}
      >
        JD
      </div>
    </nav>
  )
}
