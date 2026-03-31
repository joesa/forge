import { useState, useMemo } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

function getStrength(pw: string): number {
  if (pw.length >= 16) return 4
  if (pw.length >= 12) return 3
  if (pw.length >= 8) return 2
  if (pw.length > 0) return 1
  return 0
}

const sessions = [
  { device: 'Chrome on macOS', location: 'Austin, TX', current: true },
  { device: 'Safari on iPhone', location: 'Austin, TX', current: false },
  { device: 'Firefox on Linux', location: 'New York, NY', current: false },
]

export default function SecurityPage() {
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const strength = useMemo(() => getStrength(newPw), [newPw])

  return (
    <AppShell>
      <SettingsLayout>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Security</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/security</span>
          </div>

          {/* Change Password */}
          <div className="card" id="change-password-card">
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 14 }}>Change Password</h3>
            <form onSubmit={(e) => e.preventDefault()} style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 400 }}>
              <div>
                <label className="lbl" htmlFor="current-pw">CURRENT PASSWORD</label>
                <input id="current-pw" type="password" className="input" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} />
              </div>
              <div>
                <label className="lbl" htmlFor="new-pw">NEW PASSWORD</label>
                <input id="new-pw" type="password" className="input" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
                <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                  {[1, 2, 3, 4].map((seg) => (
                    <div key={seg} style={{ flex: 1, height: 3, borderRadius: 2, background: strength >= seg ? '#63d9ff' : 'rgba(255,255,255,0.08)', transition: 'background 200ms' }} />
                  ))}
                </div>
              </div>
              <div>
                <label className="lbl" htmlFor="confirm-pw">CONFIRM PASSWORD</label>
                <input id="confirm-pw" type="password" className="input" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} />
              </div>
              <button className="btn btn-primary" style={{ width: 'fit-content' }} type="submit">Update Password</button>
            </form>
          </div>

          {/* 2FA */}
          <div className="card" id="twofa-card">
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 10 }}>Two-Factor Authentication</h3>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: '#e8e8f0', marginBottom: 2 }}>Authenticator App</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>Add an extra layer of security to your account</div>
              </div>
              <span className="tag tag-m" style={{ marginRight: 8 }}>Disabled</span>
              <button className="btn btn-secondary btn-sm">Enable 2FA</button>
            </div>
          </div>

          {/* Active Sessions */}
          <div className="card" id="sessions-card">
            <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 10 }}>Active Sessions</h3>
            {sessions.map((s, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '9px 0',
                  borderBottom: i < sessions.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: '#e8e8f0', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {s.device}
                    {s.current && <span className="tag tag-j" style={{ fontSize: 7 }}>Current</span>}
                  </div>
                  <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>{s.location}</div>
                </div>
                {!s.current && (
                  <button className="btn btn-danger btn-sm" style={{ height: 26, fontSize: 9 }}>Sign Out</button>
                )}
              </div>
            ))}
            <button className="btn btn-danger" style={{ marginTop: 13 }}>
              Sign Out All Other Sessions
            </button>
          </div>
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
