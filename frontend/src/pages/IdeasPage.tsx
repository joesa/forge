import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { useIdeas, useSaveIdea, useSelectIdea } from '@/hooks/queries/useIdeation'

interface IdeaData {
  id: string
  title: string
  tagline: string | null
  problem: string | null
  solution: string | null
  uniqueness?: number
  complexity?: number
  market: string | null
  revenue_model: string | null
  tech_stack: string[]
  features: string[]
  is_selected: boolean
}

function IdeaCard({
  idea,
  index,
  onSave,
  onBuild,
}: {
  idea: IdeaData
  index: number
  onSave: () => void
  onBuild: () => void
}) {
  return (
    <div
      id={`idea-card-${idea.id}`}
      style={{
        borderRadius: 13,
        border: '1px solid rgba(255,255,255,0.07)',
        overflow: 'hidden',
        animation: `fade-in 280ms ease ${index * 150}ms both`,
      }}
    >
      {/* Header */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))',
          padding: '16px 16px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          {idea.uniqueness != null && (
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f5c842' }}>
              ★ {idea.uniqueness}/10 uniqueness
            </span>
          )}
          {idea.complexity != null && (
            <span className="tag tag-v" style={{ fontSize: 8 }}>◆ {idea.complexity}/10 complexity</span>
          )}
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.5px', color: '#e8e8f0', marginBottom: 3 }}>
          {idea.title}
        </div>
        {idea.tagline && (
          <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', fontStyle: 'italic' }}>
            {idea.tagline}
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ padding: '13px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {idea.problem && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 3 }}>
              PROBLEM
            </div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5 }}>{idea.problem}</div>
          </div>
        )}
        {idea.solution && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 3 }}>
              SOLUTION
            </div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5 }}>{idea.solution}</div>
          </div>
        )}
        <div style={{ display: 'flex', gap: 14 }}>
          {idea.market && (
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 2 }}>MARKET</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#63d9ff' }}>{idea.market}</div>
            </div>
          )}
          {idea.revenue_model && (
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 2 }}>REVENUE</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#63d9ff' }}>{idea.revenue_model}</div>
            </div>
          )}
        </div>
      </div>

      {/* Tech Stack */}
      {idea.tech_stack.length > 0 && (
        <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {idea.tech_stack.map((t) => (
            <span key={t} className="tag tag-f">{t}</span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ padding: '10px 16px', display: 'flex', gap: 7 }}>
        <button
          className="btn btn-ghost btn-sm"
          onClick={onSave}
          style={idea.is_selected ? { color: '#3dffa0', borderColor: 'rgba(61,255,160,0.22)' } : {}}
        >
          {idea.is_selected ? '💾 Saved' : '💾 Save'}
        </button>
        <button className="btn btn-primary btn-sm" onClick={onBuild} style={{ flex: 1 }}>
          🚀 Build This
        </button>
      </div>
    </div>
  )
}

export default function IdeasPage() {
  const { id: sessionId = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useIdeas(sessionId)
  const saveIdea = useSaveIdea()
  const selectIdea = useSelectIdea()

  const ideas: IdeaData[] = (data?.ideas ?? []).map((i: Record<string, unknown>) => ({
    id: String(i.id),
    title: String(i.title || ''),
    tagline: i.tagline as string | null,
    problem: i.problem as string | null,
    solution: i.solution as string | null,
    uniqueness: (i as Record<string, unknown>).uniqueness as number | undefined,
    complexity: (i as Record<string, unknown>).complexity as number | undefined,
    market: i.market as string | null,
    revenue_model: i.revenue_model as string | null,
    tech_stack: (i.tech_stack as string[]) || [],
    features: (i.features as string[]) || [],
    is_selected: Boolean(i.is_selected),
  }))

  const handleBuild = (ideaId: string) => {
    selectIdea.mutate(ideaId, {
      onSuccess: (data: { project_id: string; pipeline_id: string }) => {
        navigate(`/pipeline/${data.pipeline_id}`)
      },
    })
  }

  const handleSave = (ideaId: string) => {
    saveIdea.mutate(ideaId)
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 26 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <Link to="/ideate" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Ideate</Link>
              <h1 style={{ fontSize: 26, fontWeight: 800, color: '#e8e8f0' }}>Your Ideas</h1>
              <span className="tag tag-m" style={{ fontSize: 8 }}>/ideate/ideas</span>
            </div>
            <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.42)' }}>
              {isLoading ? 'Generating ideas...' : `${ideas.length} AI-generated ideas · Private for 7 days`}
            </p>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div style={{ textAlign: 'center', padding: '80px 0', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
            <div style={{ marginBottom: 14, fontSize: 24 }}>💡</div>
            Generating ideas with AI...
          </div>
        )}

        {/* Error state */}
        {error && (
          <div style={{ textAlign: 'center', padding: '80px 0', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#ff6b35' }}>
            Failed to load ideas. Please try again.
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && ideas.length === 0 && (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <div style={{ fontSize: 32, marginBottom: 14 }}>💭</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: 'rgba(232,232,240,0.42)', marginBottom: 20 }}>
              No ideas generated yet
            </div>
            <Link to="/ideate" className="btn btn-primary">Start Ideation →</Link>
          </div>
        )}

        {/* Ideas grid — 3 top, 2 bottom */}
        {ideas.length > 0 && (
          <>
            <div
              id="ideas-top-row"
              style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}
            >
              {ideas.slice(0, 3).map((idea, i) => (
                <IdeaCard
                  key={idea.id}
                  idea={idea}
                  index={i}
                  onSave={() => handleSave(idea.id)}
                  onBuild={() => handleBuild(idea.id)}
                />
              ))}
            </div>
            <div
              id="ideas-bottom-row"
              style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}
            >
              {ideas.slice(3, 5).map((idea, i) => (
                <IdeaCard
                  key={idea.id}
                  idea={idea}
                  index={i + 3}
                  onSave={() => handleSave(idea.id)}
                  onBuild={() => handleBuild(idea.id)}
                />
              ))}
            </div>
          </>
        )}

        {/* Footer */}
        {ideas.length > 0 && (
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.20)', textAlign: 'center', marginTop: 22 }}>
            Ideas private for 7 days · Similar ideas may surface to other users after expiry
          </div>
        )}
      </div>
    </AppShell>
  )
}
