import { Link, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProjectDeployments, useDeployProject } from '@/hooks/queries/useProjects'
import { SkeletonRow } from '@/components/shared/Skeleton'
import { useToast } from '@/components/shared/Toast'

interface DeploymentData {
  id: string
  status: string
  url?: string | null
  created_at: string
}

const statusBadge = (status: string) => {
  const map: Record<string, { cls: string; text: string }> = {
    active: { cls: 'status-live', text: '● Active' },
    deploying: { cls: 'status-building', text: '◎ Deploying' },
    pending: { cls: 'status-draft', text: '◌ Pending' },
    failed: { cls: 'status-error', text: '✗ Failed' },
    rolled_back: { cls: 'status-error', text: '↩ Rolled Back' },
  }
  const s = map[status] ?? map['pending']
  return <span className={`tag ${s.cls}`}>{s.text}</span>
}

export default function DeploymentsPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading } = useProjectDeployments(id ?? '')
  const deployMutation = useDeployProject(id ?? '')
  const toast = useToast()

  const deployments: DeploymentData[] = data?.deployments ?? []

  const handleDeploy = () => {
    deployMutation.mutate(undefined, {
      onSuccess: () => toast.success('Deployment initiated'),
      onError: () => toast.error('Failed to deploy'),
    })
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Link to={`/projects/${id}`} className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Project</Link>
            <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0' }}>Deployments</h1>
            <span className="tag tag-f" style={{ fontSize: 8 }}>/deployments</span>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleDeploy}
            disabled={deployMutation.isPending}
          >
            {deployMutation.isPending ? '◎ Deploying...' : '▲ Deploy Now'}
          </button>
        </div>
        <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 24 }}>
          Deployment history and active environments
        </p>

        {/* Deployments list */}
        <div style={{
          background: '#0d0d1f',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 120px 200px 140px',
            padding: '10px 16px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            textTransform: 'uppercase' as const,
            letterSpacing: '1px',
            color: 'rgba(232,232,240,0.40)',
          }}>
            <span>Status</span>
            <span>Created</span>
            <span>URL</span>
            <span>Actions</span>
          </div>

          {isLoading ? (
            <>
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : deployments.length > 0 ? (
            deployments.map((d: DeploymentData) => (
              <div key={d.id} style={{
                display: 'grid',
                gridTemplateColumns: '1fr 120px 200px 140px',
                padding: '12px 16px',
                alignItems: 'center',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}>
                {statusBadge(d.status)}
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>
                  {new Date(d.created_at).toLocaleDateString()}
                </span>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#63d9ff' }}>
                  {d.url ? (
                    <a href={d.url} target="_blank" rel="noopener noreferrer" style={{ color: '#63d9ff', textDecoration: 'none' }}>
                      {d.url.replace(/^https?:\/\//, '').slice(0, 30)}
                    </a>
                  ) : '—'}
                </span>
                <button className="btn btn-ghost btn-sm">View logs</button>
              </div>
            ))
          ) : (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🚀</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 4 }}>No deployments yet</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 14 }}>
                Deploy your app to make it live
              </div>
              <button className="btn btn-primary" onClick={handleDeploy}>
                ▲ Deploy Now
              </button>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
