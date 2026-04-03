import { useParams, Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProject, useProjectBuilds } from '@/hooks/queries/useProjects'
import Skeleton from '@/components/shared/Skeleton'

interface BuildData {
  id: string
  status: string
  build_number?: number
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  error_summary?: string | null
}

const statusColor: Record<string, string> = {
  live: '#3dffa0',
  building: '#63d9ff',
  draft: 'rgba(232,232,240,0.40)',
  error: '#ff6b35',
  succeeded: '#3dffa0',
  failed: '#ff6b35',
  pending: 'rgba(232,232,240,0.40)',
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: projectData, isLoading: loadingProject } = useProject(id ?? '')
  const { data: buildsData, isLoading: loadingBuilds } = useProjectBuilds(id ?? '')

  const project = projectData ?? null
  const builds: BuildData[] = buildsData?.builds?.slice(0, 4) ?? []

  const stats = [
    { label: 'Builds', value: String(buildsData?.builds?.length ?? 0), color: '#63d9ff' },
    { label: 'Deploys', value: '0', color: '#3dffa0' },
    { label: 'Uptime', value: '—', color: '#b06bff' },
    { label: 'Files', value: '—', color: '#f5c842' },
  ]

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, fontSize: 12 }}>
          <Link to="/projects" style={{ color: 'rgba(232,232,240,0.45)', textDecoration: 'none' }}>Projects</Link>
          <span style={{ color: 'rgba(232,232,240,0.20)' }}>/</span>
          <span style={{ color: '#e8e8f0' }}>
            {loadingProject ? <Skeleton width={120} height={14} /> : (project?.name ?? 'Project')}
          </span>
        </div>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              {loadingProject ? (
                <Skeleton width={220} height={32} />
              ) : (
                <>
                  <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0' }}>
                    {project?.name ?? 'Project'}
                  </h1>
                  <span
                    className="tag"
                    style={{ color: statusColor[project?.status ?? 'draft'], borderColor: statusColor[project?.status ?? 'draft'] }}
                  >
                    ● {project?.status ?? 'draft'}
                  </span>
                </>
              )}
            </div>
            <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.45)', marginBottom: 4 }}>
              {project?.description ?? ''}
            </p>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)' }}>
              {project?.framework ?? ''} {project?.created_at ? `· Created ${new Date(project.created_at as string).toLocaleDateString()}` : ''}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 9 }}>
            <Link to={`/projects/${id}/editor`} className="btn btn-primary" style={{ textDecoration: 'none' }}>
              Open Editor →
            </Link>
            <Link to={`/projects/${id}/settings`} className="btn btn-ghost" style={{ textDecoration: 'none' }}>
              ⚙ Settings
            </Link>
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
          {stats.map((s) => (
            <div key={s.label} className="card" style={{ padding: '18px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: s.color, marginBottom: 4 }}>{s.value}</div>
              <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.40)', textTransform: 'uppercase', letterSpacing: 1.5 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Quick Links */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 28 }}>
          <Link to={`/projects/${id}/builds`} className="card" style={{ textDecoration: 'none', padding: '20px 16px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 4 }}>Build History</div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)' }}>View all builds and logs</div>
          </Link>
          <Link to={`/projects/${id}/deployments`} className="card" style={{ textDecoration: 'none', padding: '20px 16px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 4 }}>Deployments</div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)' }}>Manage live deployments</div>
          </Link>
          <Link to={`/projects/${id}/settings`} className="card" style={{ textDecoration: 'none', padding: '20px 16px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 4 }}>Settings</div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)' }}>Project configuration</div>
          </Link>
        </div>

        {/* Recent Builds */}
        <h2 style={{ fontSize: 16, fontWeight: 700, color: '#e8e8f0', marginBottom: 12 }}>Recent Builds</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {loadingBuilds ? (
            [0, 1, 2].map((i) => (
              <div key={i} className="card" style={{ padding: '14px 16px' }}>
                <Skeleton width="60%" height={14} style={{ marginBottom: 4 }} />
                <Skeleton width="40%" height={10} />
              </div>
            ))
          ) : builds.length > 0 ? (
            builds.map((b: BuildData) => (
              <div
                key={b.id}
                className="card"
                style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: statusColor[b.status] ?? 'rgba(232,232,240,0.40)',
                  }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#e8e8f0' }}>
                      Build #{b.build_number ?? '—'}
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                      {b.status}
                      {b.started_at && b.completed_at
                        ? ` · ${Math.round((new Date(b.completed_at).getTime() - new Date(b.started_at).getTime()) / 1000)}s`
                        : ''}
                    </div>
                  </div>
                </div>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)' }}>
                  {new Date(b.created_at).toLocaleDateString()}
                </span>
              </div>
            ))
          ) : (
            <div className="card" style={{ padding: '30px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 13, color: 'rgba(232,232,240,0.40)' }}>No builds yet</div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
