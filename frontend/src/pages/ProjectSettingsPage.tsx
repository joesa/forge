import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useProject, useUpdateProject, useDeleteProject } from '@/hooks/queries/useProjects'
import { useToast } from '@/components/shared/Toast'
import Skeleton from '@/components/shared/Skeleton'

export default function ProjectSettingsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { data: project, isLoading } = useProject(id ?? '')
  const updateMutation = useUpdateProject(id ?? '')
  const deleteMutation = useDeleteProject()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [initialized, setInitialized] = useState(false)

  // Sync form state once project loads
  if (project && !initialized) {
    setName(project.name ?? '')
    setDescription(project.description ?? '')
    setInitialized(true)
  }

  const handleSave = () => {
    updateMutation.mutate({ name, description }, {
      onSuccess: () => toast.success('Project updated'),
      onError: () => toast.error('Failed to update project'),
    })
  }

  const handleDelete = () => {
    if (!id) return
    if (!window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) return
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success('Project deleted')
        navigate('/projects')
      },
      onError: () => toast.error('Failed to delete project'),
    })
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 700 }}>
        {/* Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, fontSize: 12 }}>
          <Link to="/projects" style={{ color: 'rgba(232,232,240,0.45)', textDecoration: 'none' }}>Projects</Link>
          <span style={{ color: 'rgba(232,232,240,0.20)' }}>/</span>
          <Link to={`/projects/${id}`} style={{ color: 'rgba(232,232,240,0.45)', textDecoration: 'none' }}>
            {project?.name ?? 'Project'}
          </Link>
          <span style={{ color: 'rgba(232,232,240,0.20)' }}>/</span>
          <span style={{ color: '#e8e8f0' }}>Settings</span>
        </div>

        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-1px', color: '#e8e8f0', marginBottom: 4 }}>
          Project Settings
        </h1>
        <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 28 }}>
          Configuration for this project
        </p>

        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Skeleton height={44} />
            <Skeleton height={44} />
            <Skeleton height={100} />
          </div>
        ) : (
          <>
            {/* General Settings */}
            <div className="card" style={{ padding: '22px 20px', marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 16 }}>General</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label className="lbl">Project Name</label>
                  <input
                    className="input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Project name"
                  />
                </div>
                <div>
                  <label className="lbl">Description</label>
                  <textarea
                    className="input"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description"
                    style={{ height: 80, padding: '10px 14px', resize: 'none' }}
                  />
                </div>
                <div>
                  <label className="lbl">Framework</label>
                  <input className="input" value={project?.framework ?? ''} disabled style={{ opacity: 0.6 }} />
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
            </div>

            {/* Environment Variables */}
            <div className="card" style={{ padding: '22px 20px', marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e8e8f0', marginBottom: 8 }}>Environment Variables</h3>
              <p style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', marginBottom: 14 }}>
                Securely store environment variables for your project
              </p>
              <div style={{
                padding: 20,
                textAlign: 'center',
                border: '1px dashed rgba(255,255,255,0.08)',
                borderRadius: 8,
                color: 'rgba(232,232,240,0.30)',
                fontSize: 12,
              }}>
                No environment variables configured
              </div>
            </div>

            {/* Danger Zone */}
            <div style={{
              background: 'rgba(255,107,53,0.08)',
              border: '1px solid rgba(255,107,53,0.20)',
              borderRadius: 10,
              padding: 18,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#ff6b35', marginBottom: 6 }}>Danger Zone</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', marginBottom: 12 }}>
                Permanently delete this project and all associated data. This action cannot be undone.
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete Project'}
              </button>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
