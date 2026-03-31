import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

const statCards = [
  { icon: '📁', value: '7', label: 'Total Projects' },
  { icon: '⚙️', value: '2', label: 'Active Builds' },
  { icon: '▲', value: '14', label: 'Deployments' },
  { icon: '⚡', value: '847k / 2M', label: 'Tokens', hasProgress: true },
]

const projects = [
  { id: 'p1', name: 'SaaS Dashboard', desc: 'Customer analytics platform with real-time metrics and team management', framework: 'Next.js', status: 'live' as const },
  { id: 'p2', name: 'E-Commerce API', desc: 'Headless commerce API with Stripe payments and inventory system', framework: 'FastAPI + React', status: 'building' as const },
  { id: 'p3', name: 'DevOps Monitor', desc: 'Infrastructure monitoring tool with alerting and incident management', framework: 'React + Vite', status: 'draft' as const },
]

const activities = [
  { color: '#3dffa0', text: 'Deployed SaaS Dashboard to production', project: 'SaaS Dashboard', time: '2m ago' },
  { color: '#63d9ff', text: 'Build completed for E-Commerce API', project: 'E-Commerce API', time: '18m ago' },
  { color: '#b06bff', text: 'AI generated 5 new ideas', project: 'Ideation', time: '1h ago' },
  { color: '#ff6b35', text: 'Error in DevOps Monitor build pipeline', project: 'DevOps Monitor', time: '3h ago' },
  { color: '#3dffa0', text: 'Connected OpenAI API key', project: 'Settings', time: '5h ago' },
]

const statusBadge = (status: 'live' | 'building' | 'draft' | 'error') => {
  const map = {
    live: { cls: 'status-live', text: '● Live' },
    building: { cls: 'status-building', text: '◎ Building' },
    draft: { cls: 'status-draft', text: '✦ Draft' },
    error: { cls: 'status-error', text: '⚠ Error' },
  }
  const s = map[status]
  return <span className={`tag ${s.cls}`}>{s.text}</span>
}

export default function DashboardPage() {
  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Header */}
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0', marginBottom: 4 }}>
          Good morning 👋
        </h1>
        <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.40)', marginBottom: 24 }}>
          Here&apos;s what&apos;s happening in your workspace
        </p>

        {/* Stat cards */}
        <div id="dashboard-stats" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 36 }}>
          {statCards.map((stat) => (
            <div
              key={stat.label}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 10,
                padding: 18,
              }}
            >
              <div style={{ fontSize: 18, marginBottom: 7 }}>{stat.icon}</div>
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 800,
                  letterSpacing: '-1px',
                  background: 'linear-gradient(135deg, #63d9ff, #3dffa0)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                {stat.value}
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.40)', marginTop: 4 }}>
                {stat.label}
              </div>
              {stat.hasProgress && (
                <div style={{ height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2, marginTop: 8, overflow: 'hidden' }}>
                  <div style={{ width: '42%', height: '100%', background: '#63d9ff', borderRadius: 2 }} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Continue Building */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#e8e8f0' }}>Continue Building</h2>
            <Link to="/projects" className="btn btn-ghost btn-sm">View all</Link>
          </div>
          <div id="dashboard-projects" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {projects.map((p) => (
              <div key={p.id} className="card" id={`project-card-${p.id}`}>
                <div
                  style={{
                    height: 80,
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 12,
                  }}
                >
                  <span style={{ fontSize: 28 }}>⬡</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  {statusBadge(p.status)}
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.42)' }}>
                    {p.framework}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>{p.name}</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 13, lineHeight: 1.5 }}>{p.desc}</div>
                <Link to={`/projects/${p.id}/editor`} className="btn btn-secondary btn-sm" style={{ width: '100%', textDecoration: 'none' }}>
                  Open Editor →
                </Link>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#e8e8f0', marginBottom: 13 }}>Quick Actions</h2>
          <div id="quick-actions" style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
            <Link to="/projects/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>+ New Project</Link>
            <Link to="/ideate" className="btn btn-secondary" style={{ textDecoration: 'none' }}>💡 Generate Idea</Link>
            <Link to="/projects" className="btn btn-ghost" style={{ textDecoration: 'none' }}>📁 All Projects</Link>
            <Link to="/settings/profile" className="btn btn-ghost" style={{ textDecoration: 'none' }}>⚙ Settings</Link>
          </div>
        </div>

        {/* Recent Activity */}
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#e8e8f0', marginBottom: 13 }}>Recent Activity</h2>
          <div id="activity-feed" style={{ display: 'flex', flexDirection: 'column' }}>
            {activities.map((a, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '9px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: a.color, flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: '#e8e8f0', flex: 1 }}>{a.text}</span>
                <span className="tag tag-f">{a.project}</span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.35)', flexShrink: 0 }}>
                  {a.time}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
