import { useState } from 'react'
import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'
import { useProfile, useUpdateProfile } from '@/hooks/queries/useSettings'
import { useToast } from '@/components/shared/Toast'
import Skeleton from '@/components/shared/Skeleton'

export default function ProfilePage() {
  const { data: profile, isLoading } = useProfile()
  const updateMutation = useUpdateProfile()
  const toast = useToast()

  const [displayName, setDisplayName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [initialized, setInitialized] = useState(false)

  if (profile && !initialized) {
    setDisplayName(profile.display_name ?? '')
    setTimezone(profile.timezone ?? 'UTC')
    setInitialized(true)
  }

  const handleSave = () => {
    updateMutation.mutate(
      { display_name: displayName, timezone },
      {
        onSuccess: () => toast.success('Profile updated'),
        onError: () => toast.error('Failed to update profile'),
      },
    )
  }

  return (
    <AppShell>
      <SettingsLayout>
        <div style={{ maxWidth: 480 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Profile</h1>
          <span className="tag tag-m" style={{ fontSize: 8, marginBottom: 24, display: 'inline-block' }}>/settings/profile</span>

          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 20 }}>
              <Skeleton height={68} borderRadius={34} style={{ width: 68 }} />
              <Skeleton height={44} />
              <Skeleton height={44} />
            </div>
          ) : (
            <>
              {/* Avatar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 26, marginTop: 20 }}>
                <div style={{
                  width: 68,
                  height: 68,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  fontWeight: 800,
                  color: '#04040a',
                  flexShrink: 0,
                }}>
                  {displayName.charAt(0).toUpperCase() || '?'}
                </div>
                <div>
                  <button className="btn btn-ghost btn-sm" style={{ marginBottom: 4 }}>Upload Photo</button>
                  <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.40)' }}>JPG, PNG or GIF · Max 2MB</div>
                </div>
              </div>

              {/* Form */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label className="lbl">Display Name</label>
                  <input className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </div>
                <div>
                  <label className="lbl">Email</label>
                  <input className="input" value={profile?.email ?? ''} disabled style={{ opacity: 0.6 }} />
                </div>
                <div>
                  <label className="lbl">Timezone</label>
                  <select className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)} style={{ cursor: 'pointer' }}>
                    <option value="UTC">UTC</option>
                    <option value="America/New_York">Eastern (US)</option>
                    <option value="America/Chicago">Central (US)</option>
                    <option value="America/Denver">Mountain (US)</option>
                    <option value="America/Los_Angeles">Pacific (US)</option>
                    <option value="Europe/London">London</option>
                    <option value="Europe/Berlin">Berlin</option>
                    <option value="Asia/Tokyo">Tokyo</option>
                  </select>
                </div>
                <button
                  className="btn btn-primary"
                  style={{ width: 'fit-content' }}
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>

              {/* Danger Zone */}
              <div style={{
                marginTop: 28,
                background: 'rgba(255,107,53,0.08)',
                border: '1px solid rgba(255,107,53,0.20)',
                borderRadius: 10,
                padding: 18,
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#ff6b35', marginBottom: 4 }}>Danger Zone</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', marginBottom: 10 }}>
                  Permanently delete your account and all associated data.
                </div>
                <button className="btn btn-danger btn-sm">Delete Account</button>
              </div>
            </>
          )}
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
