import { useState } from 'react'
import { Link } from 'react-router-dom'
import TopNav from '@/components/layout/TopNav'
import HexLogo from '@/components/shared/HexLogo'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

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
            id="forgot-password-card"
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
              <h1 style={{ fontSize: 22, fontWeight: 800, color: '#e8e8f0', marginBottom: 5 }}>
                Reset your password
              </h1>
              <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
                {submitted
                  ? 'Check your email for a reset link'
                  : "Enter your email and we'll send you a reset link"}
              </p>
            </div>

            {submitted ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '32px 0',
                }}
              >
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
                <div style={{ fontSize: 14, color: 'rgba(232,232,240,0.60)', marginBottom: 24, lineHeight: 1.6 }}>
                  If an account exists for <strong style={{ color: '#e8e8f0' }}>{email}</strong>,
                  you&apos;ll receive a password reset link shortly.
                </div>
                <Link
                  to="/login"
                  className="btn btn-ghost"
                  style={{ textDecoration: 'none' }}
                >
                  ← Back to login
                </Link>
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  if (email) setSubmitted(true)
                }}
                style={{ display: 'flex', flexDirection: 'column', gap: 13 }}
              >
                <div>
                  <label className="lbl" htmlFor="forgot-email">EMAIL ADDRESS</label>
                  <input
                    id="forgot-email"
                    type="email"
                    className="input"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  id="forgot-submit"
                  style={{ width: '100%', height: 48, marginTop: 4 }}
                >
                  Send Reset Link →
                </button>
              </form>
            )}

            <div style={{ textAlign: 'center', marginTop: 22, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
              Remember your password?{' '}
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
