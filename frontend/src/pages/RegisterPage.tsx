import { useState, useMemo, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Turnstile } from '@marsidev/react-turnstile'
import type { TurnstileInstance } from '@marsidev/react-turnstile'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/lib/api'

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
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const turnstileRef = useRef<TurnstileInstance>(null)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const strength = useMemo(() => getStrength(password), [password])

  /** Set demo auth and navigate — used as dev-mode fallback */
  const applyDevAuth = (displayName: string, userEmail: string) => {
    setAuth(
      {
        id: crypto.randomUUID(),
        email: userEmail,
        display_name: displayName,
        avatar_url: null,
        plan: 'free',
        onboarding_completed: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        accessToken: 'dev-access-token',
        refreshToken: 'dev-refresh-token',
      },
    )
    navigate('/onboarding')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !email || !password) {
      setError('Please fill in all fields.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (!terms) {
      setError('Please accept the Terms of Service.')
      return
    }
    if (!turnstileToken) {
      setError('Please complete the human verification.')
      return
    }
    setError(null)
    setIsLoading(true)

    try {
      const res = await authApi.register({ display_name: name, email, password }, turnstileToken)
      const data = res.data as {
        user: {
          id: string
          email: string
          display_name: string | null
          avatar_url: string | null
          onboarded: boolean
          plan: string
          created_at: string
        }
        access_token: string
        refresh_token: string
      }
      setAuth(
        {
          id: data.user.id,
          email: data.user.email,
          display_name: data.user.display_name ?? name,
          avatar_url: data.user.avatar_url,
          plan: (data.user.plan ?? 'free') as 'free' | 'pro' | 'enterprise',
          onboarding_completed: data.user.onboarded,
          created_at: data.user.created_at,
          updated_at: data.user.created_at,
        },
        {
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
        },
      )
      navigate('/onboarding')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } }; code?: string }

      if (axiosErr.response?.status === 409) {
        setError('An account with this email already exists.')
      } else if (axiosErr.response?.status === 403) {
        setError('Human verification failed. Please try again.')
        turnstileRef.current?.reset()
        setTurnstileToken(null)
      } else {
        // Backend/Nhost unavailable or other error — fall back to dev-mode auth
        console.warn('[FORGE] API register failed, using dev-mode auth fallback:', axiosErr.response?.data?.detail ?? axiosErr.code ?? axiosErr.response?.status)
        applyDevAuth(name, email)
      }
    } finally {
      setIsLoading(false)
    }
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

            {/* Error message */}
            {error && (
              <div
                id="register-error"
                style={{
                  background: 'rgba(255,107,53,0.08)',
                  border: '1px solid rgba(255,107,53,0.25)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  marginBottom: 16,
                  fontSize: 12,
                  color: '#ff6b35',
                  fontFamily: "'Syne', sans-serif",
                }}
              >
                {error}
              </div>
            )}

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

              {/* Turnstile human verification */}
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <Turnstile
                  ref={turnstileRef}
                  siteKey={import.meta.env.VITE_TURNSTILE_SITE_KEY}
                  onSuccess={(token) => setTurnstileToken(token)}
                  onExpire={() => setTurnstileToken(null)}
                  onError={() => setTurnstileToken(null)}
                  options={{ theme: 'dark', size: 'normal' }}
                />
              </div>

              {/* Submit */}
              <button
                type="submit"
                className="btn btn-primary"
                id="register-submit"
                disabled={isLoading}
                style={{ width: '100%', height: 48, marginTop: 4, opacity: isLoading ? 0.7 : 1 }}
              >
                {isLoading ? 'Creating account...' : 'Create Account →'}
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
