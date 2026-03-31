import AppShell from '@/components/layout/AppShell'
import SettingsLayout from '@/components/layout/SettingsLayout'

const usageStats = [
  { label: 'Tokens Used', value: '847k', max: '2M', pct: 42 },
  { label: 'Builds', value: '38', max: '∞', pct: 0 },
  { label: 'Deployments', value: '14', max: '∞', pct: 0 },
  { label: 'Storage', value: '2.1', max: '10GB', pct: 21 },
]

const invoices = [
  { date: 'Mar 1, 2026', amount: '$49.00', status: 'Paid' },
  { date: 'Feb 1, 2026', amount: '$49.00', status: 'Paid' },
  { date: 'Jan 1, 2026', amount: '$49.00', status: 'Paid' },
  { date: 'Dec 1, 2025', amount: '$49.00', status: 'Paid' },
]

export default function BillingPage() {
  return (
    <AppShell>
      <SettingsLayout>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0', marginBottom: 4 }}>Billing</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 26 }}>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/settings/billing</span>
          </div>

          {/* Current Plan */}
          <div
            id="current-plan"
            style={{
              background: 'linear-gradient(135deg, rgba(99,217,255,0.06), rgba(176,107,255,0.04))',
              border: '1px solid rgba(99,217,255,0.20)',
              borderRadius: 14,
              padding: 26,
              marginBottom: 18,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 4 }}>
                CURRENT PLAN
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#e8e8f0', marginBottom: 2 }}>Pro Plan</div>
              <div style={{ fontSize: 14, color: '#63d9ff', fontWeight: 700 }}>$49/month</div>
            </div>
            <button className="btn btn-primary">Manage Subscription →</button>
          </div>

          {/* Usage grid */}
          <div id="usage-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 }}>
            {usageStats.map((s) => (
              <div
                key={s.label}
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 10,
                  padding: 16,
                }}
              >
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#e8e8f0', marginBottom: 2 }}>
                  {s.value}<span style={{ fontSize: 12, color: 'rgba(232,232,240,0.30)', fontWeight: 400 }}>/{s.max}</span>
                </div>
                {s.pct > 0 && (
                  <div style={{ height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                    <div style={{ width: `${s.pct}%`, height: '100%', background: '#63d9ff', borderRadius: 2 }} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Invoice table */}
          <div
            id="invoices-table"
            style={{
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Amount', 'Status', 'Download'].map((h) => (
                    <th
                      key={h}
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 9,
                        textTransform: 'uppercase',
                        letterSpacing: 1,
                        color: 'rgba(232,232,240,0.30)',
                        padding: '10px 14px',
                        textAlign: 'left',
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        fontWeight: 500,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, i) => (
                  <tr key={i} style={{ borderBottom: i < invoices.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: '#e8e8f0' }}>{inv.date}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: 700, color: '#e8e8f0' }}>{inv.amount}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <span className="tag tag-j">Paid</span>
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: '#63d9ff', cursor: 'pointer' }}>
                      Download PDF
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </SettingsLayout>
    </AppShell>
  )
}
