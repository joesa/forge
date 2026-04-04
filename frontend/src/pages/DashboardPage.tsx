import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProjects } from '@/hooks/queries/useProjects'
import { SkeletonCard } from '@/components/shared/Skeleton'

/* ── Fallback mock data (used when API is not connected) ───────── */

const fallbackStats = [
  { icon: '📁', value: '0', label: 'Total Projects' },
  { icon: '⚙️', value: '0', label: 'Active Builds' },
  { icon: '▲', value: '0', label: 'Deployments' },
  { icon: '⚡', value: '0 / 2M', label: 'Tokens', hasProgress: true },
]

const statusBadge = (status: string) => {
  const map: Record<string, { cls: string; text: string }> = {
    live: { cls: 'status-live', text: '● Live' },
    building: { cls: 'status-building', text: '◎ Building' },
    draft: { cls: 'status-draft', text: '✦ Draft' },
    error: { cls: 'status-error', text: '⚠ Error' },
  }
  const s = map[status] ?? map['draft']
  return <span className={`tag ${s.cls}`}>{s.text}</span>
}

interface ProjectData {
  id: string
  name: string
  description?: string
  framework?: string
  status?: string
}

export default function DashboardPage() {
  const { data: projectsData, isLoading } = useProjects()

  const projects: ProjectData[] = projectsData?.items ?? []
  const recentProjects = projects.slice(0, 3)

  const stats = [
    { icon: '📁', value: String(projects.length || fallbackStats[0].value), label: 'Total Projects' },
    { icon: '⚙️', value: String(projects.filter((p: ProjectData) => p.status === 'building').length), label: 'Active Builds' },
    { icon: '▲', value: '0', label: 'Deployments' },
    { icon: '⚡', value: '0 / 2M', label: 'Tokens', hasProgress: true },
  ]

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
          {stats.map((stat) => (
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
              {'hasProgress' in stat && stat.hasProgress && (
                <div style={{ height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2, marginTop: 8, overflow: 'hidden' }}>
                  <div style={{ width: '0%', height: '100%', background: '#63d9ff', borderRadius: 2 }} />
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
            {isLoading ? (
              <>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </>
            ) : recentProjects.length > 0 ? (
              recentProjects.map((p: ProjectData) => (
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
                    {statusBadge(p.status ?? 'draft')}
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.42)' }}>
                      {p.framework ?? 'React'}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 13, lineHeight: 1.5 }}>{p.description}</div>
                  <Link to={`/projects/${p.id}/editor`} className="btn btn-secondary btn-sm" style={{ width: '100%', textDecoration: 'none' }}>
                    Open Editor →
                  </Link>
                </div>
              ))
            ) : (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px 0' }}>
                <div style={{ fontSize: 44, marginBottom: 12 }}>⬡</div>
                <div style={{ fontSize: 17, fontWeight: 700, color: '#e8e8f0', marginBottom: 6 }}>No projects yet</div>
                <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 16 }}>Start building your first application</div>
                <Link to="/projects/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>Start Building →</Link>
              </div>
            )}
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

        {/* Recent Activity — placeholder until activity endpoint exists */}
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#e8e8f0', marginBottom: 13 }}>Recent Activity</h2>
          <div id="activity-feed" style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{
              padding: '20px 0',
              textAlign: 'center',
              fontSize: 12,
              color: 'rgba(232,232,240,0.30)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Activity will appear here as you build
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
