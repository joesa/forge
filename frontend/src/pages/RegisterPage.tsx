import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'
import { useAuthStore } from '@/stores/authStore'

function getStrength(pw: string): number {
  if (pw.length >= 16) return 4
  if (pw.length >= 12) return 3
  if (pw.length >= 8) return 2
  if (pw.length > 0) return 1
  return 0
}

export default function RegisterPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [terms, setTerms] = useState(false)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const strength = useMemo(() => getStrength(password), [password])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !email || !password) return
    /* Set fake auth state for demo / E2E flow */
    setAuth(
      {
        id: crypto.randomUUID(),
        email,
        display_name: name,
        avatar_url: null,
        plan: 'free',
        onboarding_completed: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        accessToken: 'demo-access-token',
        refreshToken: 'demo-refresh-token',
      },
    )
    navigate('/onboarding')
  }

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
            id="register-card"
            style={{
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 16,
              padding: 42,
              maxWidth: 480,
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
                Create your account
              </h1>
              <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
                Start building production apps with AI
              </p>
            </div>

            {/* Form */}
            <form
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: 13 }}
            >
              {/* Display Name */}
              <div>
                <label className="lbl" htmlFor="register-name">DISPLAY NAME</label>
                <input
                  id="register-name"
                  type="text"
                  className="input"
                  placeholder="Joe Developer"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              {/* Email */}
              <div>
                <label className="lbl" htmlFor="register-email">EMAIL ADDRESS</label>
                <input
                  id="register-email"
                  type="email"
                  className="input"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              {/* Password */}
              <div>
                <label className="lbl" htmlFor="register-password">PASSWORD</label>
                <div style={{ position: 'relative' }}>
                  <input
                    id="register-password"
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
                {/* Strength meter */}
                <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                  {[1, 2, 3, 4].map((seg) => (
                    <div
                      key={seg}
                      style={{
                        flex: 1,
                        height: 3,
                        borderRadius: 2,
                        background: strength >= seg ? '#63d9ff' : 'rgba(255,255,255,0.08)',
                        transition: 'background 200ms',
                      }}
                    />
                  ))}
                </div>
              </div>

              {/* Terms */}
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11, color: 'rgba(232,232,240,0.45)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={terms}
                  onChange={(e) => setTerms(e.target.checked)}
                  style={{ accentColor: '#63d9ff', marginTop: 2 }}
                />
                I agree to the Terms of Service and Privacy Policy
              </label>

              {/* Submit */}
              <button
                type="submit"
                className="btn btn-primary"
                id="register-submit"
                style={{ width: '100%', height: 48, marginTop: 4 }}
              >
                Create Account →
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
              <button className="btn btn-ghost" id="register-github" style={{ flex: 1 }}>🐙 GitHub</button>
              <button className="btn btn-ghost" id="register-google" style={{ flex: 1 }}>G Google</button>
            </div>

            {/* Footer */}
            <div style={{ textAlign: 'center', marginTop: 22, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
              Already have an account?{' '}
              <Link to="/login" style={{ color: '#63d9ff', textDecoration: 'none', fontWeight: 600 }}>
                Sign in →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
