import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const passwordsMatch = password === confirm && password.length >= 8

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
            id="reset-password-card"
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
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
                <HexLogo showWordmark={false} size={36} />
              </div>
              <h1 style={{ fontSize: 22, fontWeight: 800, color: '#e8e8f0', marginBottom: 5 }}>
                {submitted ? 'Password reset!' : 'Create new password'}
              </h1>
              <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
                {submitted
                  ? 'Your password has been updated successfully'
                  : 'Enter your new password below'}
              </p>
            </div>

            {!token && !submitted && (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <div style={{ fontSize: 13, color: 'rgba(255,107,53,0.80)', marginBottom: 16 }}>
                  Invalid or missing reset token.
                </div>
                <Link to="/forgot-password" className="btn btn-ghost" style={{ textDecoration: 'none' }}>
                  Request a new reset link →
                </Link>
              </div>
            )}

            {submitted ? (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: '50%',
                    background: 'rgba(61,255,160,0.08)',
                    border: '1px solid rgba(61,255,160,0.20)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 28,
                    margin: '0 auto 20px',
                  }}
                >
                  ✓
                </div>
                <Link
                  to="/login"
                  className="btn btn-primary"
                  style={{ textDecoration: 'none', width: '100%', display: 'inline-block', textAlign: 'center' }}
                >
                  Sign in with new password →
                </Link>
              </div>
            ) : token ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  if (passwordsMatch) setSubmitted(true)
                }}
                style={{ display: 'flex', flexDirection: 'column', gap: 13 }}
              >
                <div>
                  <label className="lbl" htmlFor="reset-password">NEW PASSWORD</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="reset-password"
                      type={showPassword ? 'text' : 'password'}
                      className="input"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={8}
                      required
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

                <div>
                  <label className="lbl" htmlFor="reset-confirm">CONFIRM PASSWORD</label>
                  <input
                    id="reset-confirm"
                    type={showPassword ? 'text' : 'password'}
                    className="input"
                    placeholder="••••••••"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    minLength={8}
                    required
                  />
                </div>

                {password && confirm && !passwordsMatch && (
                  <div style={{ fontSize: 11, color: 'rgba(255,107,53,0.80)' }}>
                    Passwords must match and be at least 8 characters
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn-primary"
                  id="reset-submit"
                  style={{ width: '100%', height: 48, marginTop: 4 }}
                  disabled={!passwordsMatch}
                >
                  Reset Password →
                </button>
              </form>
            ) : null}
          </div>
        </div>
      </div>
    </>
  )
}
