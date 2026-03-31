import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

export default function ProfilePage() {
  const [name, setName] = useState('Joe Developer')
  const [timezone, setTimezone] = useState('America/Chicago')

  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Profile</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 26 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/profile</span>
          </div>

          {/* Avatar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 26 }}>
            <div
              style={{
                width: 68,
                height: 68,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                fontWeight: 700,
                color: '#04040a',
                flexShrink: 0,
              }}
            >
              JD
            </div>
            <div>
              <button className="btn btn-ghost btn-sm">Upload Photo</button>
              <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.42)', marginTop: 5 }}>
                JPG, PNG or GIF · Max 2MB
              </div>
            </div>
          </div>

          {/* Form */}
          <form
            onSubmit={(e) => e.preventDefault()}
            style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 480 }}
          >
            <div>
              <label className="lbl" htmlFor="profile-name">DISPLAY NAME</label>
              <input
                id="profile-name"
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="lbl" htmlFor="profile-email">EMAIL</label>
              <input
                id="profile-email"
                className="input"
                value="joe@company.com"
                disabled
                style={{ opacity: 0.6 }}
              />
            </div>
            <div>
              <label className="lbl" htmlFor="profile-timezone">TIMEZONE</label>
              <select
                id="profile-timezone"
                className="input"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                style={{ cursor: 'pointer' }}
              >
                <option value="America/Chicago">America/Chicago (CST)</option>
                <option value="America/New_York">America/New_York (EST)</option>
                <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                <option value="Europe/London">Europe/London (GMT)</option>
                <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
              </select>
            </div>
            <button className="btn btn-primary" style={{ width: 'fit-content' }} type="submit">
              Save Changes
            </button>
          </form>

          {/* Danger Zone */}
          <div
            id="danger-zone"
            style={{
              marginTop: 28,
              background: 'rgba(255,107,53,0.08)',
              border: '1px solid rgba(255,107,53,0.20)',
              borderRadius: 10,
              padding: 18,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ff6b35', marginBottom: 6 }}>Danger Zone</div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)', marginBottom: 12 }}>
              Permanently delete your account and all associated data. This action cannot be undone.
            </div>
            <button className="btn btn-danger btn-sm">Delete Account</button>
          </div>
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
