import { useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProjects } from '@/hooks/queries/useProjects'
import { SkeletonCard } from '@/components/shared/Skeleton'

type ProjectStatus = 'all' | 'live' | 'building' | 'draft' | 'error'

interface ProjectData {
  id: string
  name: string
  description?: string
  framework?: string
  status?: string
  updated_at?: string
}

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

const tabs: { key: ProjectStatus; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'live', label: 'Live' },
  { key: 'building', label: 'Building' },
  { key: 'draft', label: 'Draft' },
  { key: 'error', label: 'Error' },
]

export default function ProjectsPage() {
  const [filter, setFilter] = useState<ProjectStatus>('all')
  const [search, setSearch] = useState('')
  const { data: projectsData, isLoading } = useProjects()

  const allProjects: ProjectData[] = projectsData?.projects ?? []
  const filtered = allProjects.filter((p: ProjectData) => {
    if (filter !== 'all' && (p.status ?? 'draft') !== filter) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0' }}>Projects</h1>
            <span className="tag tag-f" style={{ fontSize: 8 }}>/projects</span>
          </div>
          <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
            <input
              className="input"
              placeholder="Search projects..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 200, height: 36, fontSize: 12 }}
            />
            <Link to="/projects/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>+ New Project</Link>
          </div>
        </div>

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 5, marginBottom: 22 }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`btn btn-sm ${filter === t.key ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setFilter(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Project grid */}
        <div id="projects-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {isLoading ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : filtered.length > 0 ? (
            filtered.map((p: ProjectData) => (
              <div key={p.id} className="card" id={`project-${p.id}`}>
                <div
                  style={{
                    height: 90,
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
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0' }}>{p.name}</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 14, lineHeight: 1.5 }}>
                  {p.description}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>
                    {p.updated_at ?? ''}
                  </span>
                  <Link to={`/projects/${p.id}/editor`} className="btn btn-secondary btn-sm" style={{ textDecoration: 'none' }}>
                    Open Editor →
                  </Link>
                </div>
              </div>
            ))
          ) : (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '60px 0' }}>
              <div style={{ fontSize: 60, marginBottom: 14, opacity: 0.6 }}>⬡</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#e8e8f0', marginBottom: 8 }}>No projects yet</div>
              <div style={{ fontSize: 13, color: 'rgba(232,232,240,0.42)', marginBottom: 20 }}>
                Start building your first application
              </div>
              <div style={{ display: 'flex', gap: 9, justifyContent: 'center' }}>
                <Link to="/ideate" className="btn btn-primary" style={{ textDecoration: 'none' }}>Start with an idea →</Link>
                <Link to="/projects/new" className="btn btn-ghost" style={{ textDecoration: 'none' }}>Build from prompt →</Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
