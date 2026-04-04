import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import HexLogo from '@/components/shared/HexLogo'
import { useAuthStore } from '@/stores/authStore'

interface TopNavProps {
  variant?: 'landing' | 'authenticated' | 'minimal'
  rightContent?: React.ReactNode
}

export default function TopNav({ variant = 'authenticated', rightContent }: TopNavProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  useEffect(() => {
    if (!menuOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  function handleLogout() {
    setMenuOpen(false)
    logout()
    navigate('/login')
  }

  const initials = user?.display_name
    ? user.display_name.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2)
    : 'JD'
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
      <div ref={menuRef} style={{ position: 'relative' }}>
        <div
          id="user-avatar"
          onClick={() => setMenuOpen((o) => !o)}
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
            userSelect: 'none',
          }}
        >
          {initials}
        </div>
        {menuOpen && (
          <div
            style={{
              position: 'absolute',
              top: 40,
              right: 0,
              minWidth: 180,
              background: '#0e0e18',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8,
              padding: '4px 0',
              zIndex: 200,
              boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
            }}
          >
            {user?.email && (
              <div
                style={{
                  padding: '8px 14px 6px',
                  fontSize: 11,
                  color: 'rgba(255,255,255,0.4)',
                  borderBottom: '1px solid rgba(255,255,255,0.07)',
                  marginBottom: 4,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {user.email}
              </div>
            )}
            <Link
              to="/settings"
              onClick={() => setMenuOpen(false)}
              style={{
                display: 'block',
                padding: '7px 14px',
                fontSize: 13,
                color: 'rgba(255,255,255,0.8)',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Settings
            </Link>
            <button
              onClick={handleLogout}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '7px 14px',
                fontSize: 13,
                color: '#ff6b6b',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,107,107,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}
