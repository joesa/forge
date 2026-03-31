import { useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

interface IdeaData {
  id: string
  title: string
  tagline: string
  problem: string
  solution: string
  uniqueness: number
  complexity: number
  market: string
  revenue: string
  techStack: string[]
  saved: boolean
}

const mockIdeas: IdeaData[] = [
  {
    id: 'i1', title: 'CodeReview AI', tagline: 'AI-powered code review that learns your team patterns',
    problem: 'Code reviews are slow and inconsistent across teams. Senior developers spend 30% of their time reviewing PRs.',
    solution: 'An AI agent that learns team coding patterns and provides instant, contextual code reviews with actionable suggestions.',
    uniqueness: 8.5, complexity: 7, market: '$4.2B', revenue: 'Subscription', techStack: ['Next.js', 'Python', 'OpenAI', 'PostgreSQL'], saved: false,
  },
  {
    id: 'i2', title: 'SupplySync', tagline: 'Real-time supply chain visibility for SMBs',
    problem: 'Small businesses lack visibility into their supply chain, leading to stockouts and overordering.',
    solution: 'A lightweight platform that connects suppliers, warehouses, and retailers with real-time tracking and predictive analytics.',
    uniqueness: 7.2, complexity: 6, market: '$8.7B', revenue: 'Freemium', techStack: ['React', 'Node.js', 'MongoDB', 'Stripe'], saved: false,
  },
  {
    id: 'i3', title: 'MeetingMind', tagline: 'Turn meetings into structured action items automatically',
    problem: 'Teams lose 31 hours monthly in unproductive meetings with no clear outcomes.',
    solution: 'Transcribe, summarize, and extract action items from meetings with auto-assignment and deadline tracking.',
    uniqueness: 6.8, complexity: 5, market: '$2.1B', revenue: 'Subscription', techStack: ['Next.js', 'Whisper', 'Supabase', 'Resend'], saved: false,
  },
  {
    id: 'i4', title: 'GreenCompute', tagline: 'Carbon-aware cloud computing scheduler',
    problem: 'Cloud workloads generate significant carbon emissions by running in high-carbon-intensity regions.',
    solution: 'Intelligent scheduler that routes non-urgent compute to regions and times with lowest carbon intensity.',
    uniqueness: 9.1, complexity: 8, market: '$1.8B', revenue: 'Usage-based', techStack: ['FastAPI', 'React', 'Redis', 'Docker'], saved: false,
  },
  {
    id: 'i5', title: 'LearnPath', tagline: 'Personalized learning roadmaps powered by skill assessment',
    problem: 'Online learners waste time on content too easy or advanced for them, leading to high dropout rates.',
    solution: 'Adaptive assessment engine that maps current skills and generates optimized learning paths from curated resources.',
    uniqueness: 7.5, complexity: 6, market: '$5.3B', revenue: 'Freemium', techStack: ['Next.js', 'OpenAI', 'PostgreSQL', 'Stripe'], saved: false,
  },
]

function IdeaCard({ idea, index, onToggleSave }: { idea: IdeaData; index: number; onToggleSave: () => void }) {
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
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f5c842' }}>
            ★ {idea.uniqueness}/10 uniqueness
          </span>
          <span className="tag tag-v" style={{ fontSize: 8 }}>◆ {idea.complexity}/10 complexity</span>
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.5px', color: '#e8e8f0', marginBottom: 3 }}>
          {idea.title}
        </div>
        <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', fontStyle: 'italic' }}>
          {idea.tagline}
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '13px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 3 }}>
            PROBLEM
          </div>
          <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5 }}>{idea.problem}</div>
        </div>
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 3 }}>
            SOLUTION
          </div>
          <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5 }}>{idea.solution}</div>
        </div>
        <div style={{ display: 'flex', gap: 14 }}>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 2 }}>
              MARKET
            </div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#63d9ff' }}>{idea.market}</div>
          </div>
          <div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.30)', marginBottom: 2 }}>
              REVENUE
            </div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#63d9ff' }}>{idea.revenue}</div>
          </div>
        </div>
      </div>

      {/* Tech Stack */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {idea.techStack.map((t) => (
          <span key={t} className="tag tag-f">{t}</span>
        ))}
      </div>

      {/* Actions */}
      <div style={{ padding: '10px 16px', display: 'flex', gap: 7 }}>
        <button
          className="btn btn-ghost btn-sm"
          onClick={onToggleSave}
          style={idea.saved ? { color: '#3dffa0', borderColor: 'rgba(61,255,160,0.22)' } : {}}
        >
          {idea.saved ? '💾 Saved' : '💾 Save'}
        </button>
        <button className="btn btn-ghost btn-sm">↻</button>
        <Link to="/pipeline/new" className="btn btn-primary btn-sm" style={{ flex: 1, textDecoration: 'none' }}>
          🚀 Build This
        </Link>
      </div>
    </div>
  )
}

export default function IdeasPage() {
  const [ideas, setIdeas] = useState(mockIdeas)

  const toggleSave = (id: string) => {
    setIdeas((prev) => prev.map((idea) => idea.id === id ? { ...idea, saved: !idea.saved } : idea))
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
              5 AI-generated ideas · Private for 7 days · Based on your answers
            </p>
          </div>
          <button className="btn btn-ghost btn-sm">↻ Regenerate All</button>
        </div>

        {/* Ideas grid — 3 top, 2 bottom */}
        <div id="ideas-top-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
          {ideas.slice(0, 3).map((idea, i) => (
            <IdeaCard key={idea.id} idea={idea} index={i} onToggleSave={() => toggleSave(idea.id)} />
          ))}
        </div>
        <div id="ideas-bottom-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {ideas.slice(3, 5).map((idea, i) => (
            <IdeaCard key={idea.id} idea={idea} index={i + 3} onToggleSave={() => toggleSave(idea.id)} />
          ))}
        </div>

        {/* Footer */}
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.20)', textAlign: 'center', marginTop: 22 }}>
          Ideas private for 7 days · Similar ideas may surface to other users after expiry
        </div>
      </div>
    </AppShell>
  )
}
