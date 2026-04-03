import { Link, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProjectBuilds } from '@/hooks/queries/useProjects'
import { SkeletonRow } from '@/components/shared/Skeleton'

interface BuildData {
  id: string
  status: string
  build_number?: number
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  error_summary?: string | null
}

const statusBadge = (status: string) => {
  const map: Record<string, { cls: string; text: string }> = {
    succeeded: { cls: 'status-live', text: '✓ Succeeded' },
    building: { cls: 'status-building', text: '◎ Building' },
    pending: { cls: 'status-draft', text: '◌ Pending' },
    failed: { cls: 'status-error', text: '✗ Failed' },
  }
  const s = map[status] ?? map['pending']
  return <span className={`tag ${s.cls}`}>{s.text}</span>
}

export default function BuildHistoryPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useProjectBuilds(id ?? '')
  const builds: BuildData[] = data?.builds ?? []

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <Link to={`/projects/${id}`} className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Project</Link>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0' }}>Build History</h1>
          <span className="tag tag-f" style={{ fontSize: 8 }}>/builds</span>
        </div>
        <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 24 }}>
          All builds for this project
        </p>

        {/* Build list */}
        <div style={{
          background: '#0d0d1f',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '80px 1fr 120px 120px 140px',
            padding: '10px 16px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            textTransform: 'uppercase' as const,
            letterSpacing: '1px',
            color: 'rgba(232,232,240,0.40)',
          }}>
            <span>#</span>
            <span>Status</span>
            <span>Started</span>
            <span>Duration</span>
            <span>Actions</span>
          </div>

          {isLoading ? (
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : builds.length > 0 ? (
            builds.map((b: BuildData) => (
              <div key={b.id} style={{
                display: 'grid',
                gridTemplateColumns: '80px 1fr 120px 120px 140px',
                padding: '12px 16px',
                alignItems: 'center',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                transition: 'background 150ms',
              }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: '#63d9ff' }}>
                  #{b.build_number ?? '—'}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {statusBadge(b.status)}
                  {b.error_summary && (
                    <span style={{ fontSize: 10, color: '#ff6b35', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {b.error_summary}
                    </span>
                  )}
                </div>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                  {b.started_at ? new Date(b.started_at).toLocaleTimeString() : '—'}
                </span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                  {b.started_at && b.completed_at
                    ? `${Math.round((new Date(b.completed_at).getTime() - new Date(b.started_at).getTime()) / 1000)}s`
                    : '—'}
                </span>
                <div style={{ display: 'flex', gap: 5 }}>
                  <button className="btn btn-ghost btn-sm">Logs</button>
                  {b.status === 'failed' && (
                    <button className="btn btn-secondary btn-sm">Retry</button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🔨</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 4 }}>No builds yet</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)' }}>Builds will appear here when you start the pipeline</div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
