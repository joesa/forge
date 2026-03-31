import { useState } from 'react'
import { Link } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)

  return (
    <>
      <div className="grid-bg" aria-hidden="true" />
      <div className="orb" style={{ width: 600, height: 600, top: '-15%', right: '-5%', background: 'rgba(176,107,255,0.04)' }} aria-hidden="true" />
      <div className="orb" style={{ width: 500, height: 500, bottom: '-10%', left: '-8%', background: 'rgba(99,217,255,0.04)' }} aria-hidden="true" />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <TopNav variant="minimal" />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 'calc(100vh - 62px)',
            padding: '40px 20px',
          }}
        >
          <div
            id="login-card"
            style={{
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 16,
              padding: 42,
              maxWidth: 440,
              width: '100%',
              animation: 'fade-in 280ms ease',
            }}
          >
            {/* Header */}
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
                <HexLogo showWordmark={false} size={36} />
              </div>
              <div
                style={{
                  fontFamily: "'Syne', sans-serif",
                  fontSize: 22,
                  fontWeight: 800,
                  background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  marginBottom: 16,
                }}
              >
                FORGE
              </div>
              <h1 style={{ fontSize: 22, fontWeight: 800, color: '#e8e8f0', marginBottom: 5 }}>
                Welcome back
              </h1>
              <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
                Sign in to your workspace
              </p>
            </div>

            {/* Form */}
            <form
              onSubmit={(e) => e.preventDefault()}
              style={{ display: 'flex', flexDirection: 'column', gap: 13 }}
            >
              {/* Email */}
              <div>
                <label className="lbl" htmlFor="login-email">EMAIL ADDRESS</label>
                <input
                  id="login-email"
                  type="email"
                  className="input"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              {/* Password */}
              <div>
                <label className="lbl" htmlFor="login-password">PASSWORD</label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    className="input"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: 12,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      color: 'rgba(232,232,240,0.40)',
                      cursor: 'pointer',
                      fontSize: 13,
                    }}
                  >
                    {showPassword ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              {/* Remember / Forgot */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'rgba(232,232,240,0.45)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    style={{ accentColor: '#63d9ff' }}
                  />
                  Remember me
                </label>
                <Link to="#" style={{ fontSize: 11, color: '#63d9ff', textDecoration: 'none' }}>
                  Forgot password?
                </Link>
              </div>

              {/* Sign In */}
              <button
                type="submit"
                className="btn btn-primary"
                id="login-submit"
                style={{ width: '100%', height: 48, marginTop: 4 }}
              >
                Sign In →
              </button>
            </form>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '18px 0' }}>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
              <span style={{ fontSize: 11, color: 'rgba(232,232,240,0.25)' }}>or continue with</span>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
            </div>

            {/* OAuth */}
            <div style={{ display: 'flex', gap: 9 }}>
              <button className="btn btn-ghost" id="login-github" style={{ flex: 1 }}>
                🐙 GitHub
              </button>
              <button className="btn btn-ghost" id="login-google" style={{ flex: 1 }}>
                G Google
              </button>
            </div>

            {/* Footer */}
            <div style={{ textAlign: 'center', marginTop: 22, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
              Don&apos;t have an account?{' '}
              <Link to="/register" style={{ color: '#63d9ff', textDecoration: 'none', fontWeight: 600 }}>
                Create account →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
