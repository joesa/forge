import { useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

type ProjectStatus = 'all' | 'live' | 'building' | 'draft' | 'error'

const projects = [
  { id: 'p1', name: 'SaaS Dashboard', desc: 'Customer analytics platform with real-time metrics', framework: 'Next.js', status: 'live' as const, updated: '2 hours ago' },
  { id: 'p2', name: 'E-Commerce API', desc: 'Headless commerce API with Stripe payments', framework: 'FastAPI + React', status: 'building' as const, updated: '30 min ago' },
  { id: 'p3', name: 'DevOps Monitor', desc: 'Infrastructure monitoring with alerting system', framework: 'React + Vite', status: 'draft' as const, updated: '1 day ago' },
  { id: 'p4', name: 'Social Platform', desc: 'Real-time social app with messaging and feeds', framework: 'Next.js', status: 'live' as const, updated: '3 days ago' },
  { id: 'p5', name: 'AI Chatbot Builder', desc: 'No-code chatbot builder with LLM integrations', framework: 'React + Vite', status: 'error' as const, updated: '5 hours ago' },
  { id: 'p6', name: 'Portfolio Generator', desc: 'Auto-generate developer portfolios from GitHub', framework: 'Remix', status: 'draft' as const, updated: '1 week ago' },
  { id: 'p7', name: 'Invoice Tool', desc: 'Automated invoicing with PDF generation', framework: 'Next.js', status: 'live' as const, updated: '4 days ago' },
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

  const filtered = projects.filter((p) => {
    if (filter !== 'all' && p.status !== filter) return false
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
            <span className="tag tag-m" style={{ fontSize: 8 }}>/projects</span>
          </div>
          <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
            <input
              className="input"
              placeholder="Search..."
              style={{ width: 200, height: 36 }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              id="projects-search"
            />
            <Link to="/projects/new" className="btn btn-primary" style={{ textDecoration: 'none' }} id="projects-new-btn">
              + New Project
            </Link>
          </div>
        </div>

        {/* Filter tabs */}
        <div id="project-filters" style={{ display: 'flex', gap: 5, marginBottom: 22 }}>
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`btn btn-sm ${filter === tab.key ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Project grid */}
        {filtered.length > 0 ? (
          <div id="projects-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {filtered.map((p) => (
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
                  {statusBadge(p.status)}
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.42)' }}>{p.framework}</span>
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 3 }}>{p.name}</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 14, lineHeight: 1.5 }}>{p.desc}</div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>{p.updated}</span>
                  <Link to={`/projects/${p.id}/editor`} className="btn btn-secondary btn-sm" style={{ textDecoration: 'none' }}>
                    Open Editor →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Empty state */
          <div
            id="projects-empty"
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px 0',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 120,
                height: 120,
                borderRadius: '50%',
                background: 'rgba(99,217,255,0.05)',
                border: '1px solid rgba(99,217,255,0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 48,
                marginBottom: 24,
              }}
            >
              ⬡
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#e8e8f0', marginBottom: 8 }}>No projects yet</div>
            <div style={{ fontSize: 13, color: 'rgba(232,232,240,0.42)', marginBottom: 20 }}>Start building your first application</div>
            <div style={{ display: 'flex', gap: 9 }}>
              <Link to="/ideate" className="btn btn-primary" style={{ textDecoration: 'none' }}>Start with an idea →</Link>
              <Link to="/projects/new" className="btn btn-ghost" style={{ textDecoration: 'none' }}>Build from prompt →</Link>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
