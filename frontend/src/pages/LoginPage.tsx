import { useState } from 'react'
import { Link, useNavigate, useLocation, Navigate } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/lib/api'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const setAuth = useAuthStore((s) => s.setAuth)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

  // Where to redirect after login — either the page that sent us here, or dashboard
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard'

  // If already authenticated, redirect away from login page
  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please enter both email and password.')
      return
    }
    setError(null)
    setIsLoading(true)

    try {
      const res = await authApi.login({ email, password })
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
          display_name: data.user.display_name ?? email.split('@')[0],
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
      navigate(data.user.onboarded ? from : '/onboarding')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } }; code?: string }

      // Only treat 401 as a definitive auth error — everything else falls back to dev mode
      if (axiosErr.response?.status === 401) {
        setError(axiosErr.response.data?.detail ?? 'Invalid email or password.')
      } else if (import.meta.env.DEV) {
        // Dev-only fallback: bypass auth when backend is unavailable locally
        console.warn('[FORGE] API login failed, using dev-mode auth fallback:', axiosErr.code ?? axiosErr.response?.status)
        setAuth(
          {
            id: crypto.randomUUID(),
            email,
            display_name: email.split('@')[0],
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
        navigate('/dashboard')
      } else {
        setError(axiosErr.response?.data?.detail ?? 'Login failed. Please try again.')
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

            {/* Error message */}
            {error && (
              <div
                id="login-error"
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
                <Link to="/forgot-password" style={{ fontSize: 11, color: '#63d9ff', textDecoration: 'none' }}>
                  Forgot password?
                </Link>
              </div>

              {/* Sign In */}
              <button
                type="submit"
                className="btn btn-primary"
                id="login-submit"
                disabled={isLoading}
                style={{ width: '100%', height: 48, marginTop: 4, opacity: isLoading ? 0.7 : 1 }}
              >
                {isLoading ? 'Signing in...' : 'Sign In →'}
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
