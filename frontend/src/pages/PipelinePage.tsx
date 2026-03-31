import { useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'

interface Stage {
  name: string
  status: 'done' | 'running' | 'pending' | 'failed'
  duration?: string
}

const stages: Stage[] = [
  { name: 'Input Layer', status: 'done', duration: '0:12' },
  { name: 'C-Suite Analysis', status: 'done', duration: '1:48' },
  { name: 'Synthesis', status: 'running', duration: '0:32' },
  { name: 'Spec Layer', status: 'pending' },
  { name: 'Bootstrap', status: 'pending' },
  { name: 'Build', status: 'pending' },
]

const agents = [
  { emoji: '📊', role: 'Market Analyst', status: 'done', output: 'B2B SaaS, $4.2B TAM' },
  { emoji: '🎯', role: 'Product Strategist', status: 'done', output: 'Freemium → Pro conversion' },
  { emoji: '🏗️', role: 'Tech Architect', status: 'done', output: 'Next.js + Supabase stack' },
  { emoji: '🔒', role: 'Security Advisor', status: 'running', output: '' },
  { emoji: '💰', role: 'Revenue Modeler', status: 'done', output: '$49/mo avg plan' },
  { emoji: '🎨', role: 'UX Director', status: 'done', output: 'Dashboard-first layout' },
  { emoji: '⚡', role: 'Performance Lead', status: 'pending', output: '' },
  { emoji: '📋', role: 'Compliance Officer', status: 'pending', output: '' },
]

const logEntries = [
  { time: '04:32', level: 'info', message: 'Synthesis agent started — merging C-Suite outputs' },
  { time: '04:28', level: 'info', message: 'Security Advisor analyzing auth requirements' },
  { time: '04:15', level: 'success', message: 'Revenue Modeler completed — $49/mo pricing validated' },
  { time: '04:02', level: 'info', message: 'UX Director completed — dashboard-first recommendation' },
  { time: '03:48', level: 'success', message: 'Tech Architect selected Next.js + Supabase stack' },
  { time: '03:21', level: 'info', message: 'Market Analyst completed — $4.2B TAM identified' },
  { time: '02:55', level: 'info', message: 'Product Strategist completed — freemium model recommended' },
  { time: '00:12', level: 'success', message: 'Input Layer completed — prompt analyzed and enriched' },
]

export default function PipelinePage() {
  const [selectedStage] = useState(2)
  const completedAgents = agents.filter((a) => a.status === 'done').length

  const stageCircle = (s: Stage, idx: number) => {
    const styles: Record<string, React.CSSProperties> = {
      done: { background: '#3dffa0', color: '#04040a' },
      running: { background: '#63d9ff', color: '#04040a' },
      pending: { background: 'rgba(255,255,255,0.07)', color: 'rgba(232,232,240,0.35)' },
      failed: { background: '#ff6b35', color: '#fff' },
    }
    const icons: Record<string, string> = { done: '✓', running: '◎', pending: String(idx + 1), failed: '✕' }
    return (
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
          ...styles[s.status],
          ...(s.status === 'running' ? { boxShadow: '0 0 0 3px rgba(99,217,255,0.20)' } : {}),
        }}
      >
        {icons[s.status]}
      </div>
    )
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1100 }}>
        {/* Header */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Link to="/projects" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Projects</Link>
            <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.8px', color: '#e8e8f0' }}>
              Building: SaaS Dashboard
            </h1>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/pipeline</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="tag status-building" style={{ animation: 'pulse-f 1.8s ease-in-out infinite' }}>
              ◎ Running — Stage 3 of 6
            </span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.42)' }}>
              Elapsed: 4:32
            </span>
          </div>
        </div>

        {/* 2-column layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: 18, marginBottom: 18 }}>
          {/* Stage list */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', color: 'rgba(232,232,240,0.30)', marginBottom: 13, letterSpacing: 1 }}>
              PIPELINE STAGES
            </div>
            {stages.map((s, i) => (
              <div
                key={s.name}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 7px',
                  borderBottom: i < stages.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                  cursor: 'pointer',
                  background: selectedStage === i ? 'rgba(99,217,255,0.04)' : 'transparent',
                  borderRadius: 6,
                }}
              >
                {stageCircle(s, i)}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>{s.name}</div>
                  <div style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(232,232,240,0.30)' }}>
                    {s.status === 'done' ? 'Completed' : s.status === 'running' ? 'In progress...' : 'Pending'}
                  </div>
                </div>
                {s.duration && (
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>
                    {s.duration}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* C-Suite detail */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#e8e8f0' }}>C-Suite Analysis</h2>
              <span className="tag tag-j">{completedAgents}/8 Complete</span>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)', marginBottom: 14 }}>
              8 executive agents analyzing in parallel
            </div>
            <div id="csuite-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
              {agents.map((a) => (
                <div
                  key={a.role}
                  style={{
                    background: '#111125',
                    border: `1px solid ${a.status === 'done' ? 'rgba(61,255,160,0.2)' : a.status === 'running' ? 'rgba(99,217,255,0.22)' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: 8,
                    padding: '12px 13px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: a.output ? 6 : 0 }}>
                    <span style={{ fontSize: 18 }}>{a.emoji}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#e8e8f0', flex: 1 }}>{a.role}</span>
                    {a.status === 'done' && <span style={{ color: '#3dffa0', fontSize: 12 }}>✓</span>}
                    {a.status === 'running' && (
                      <div style={{ width: 14, height: 14, border: '2px solid #63d9ff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                    )}
                    {a.status === 'pending' && <span style={{ color: 'rgba(232,232,240,0.30)', fontSize: 11 }}>○</span>}
                  </div>
                  {a.output && (
                    <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.42)', marginLeft: 26 }}>{a.output}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Live event log */}
        <div className="card" style={{ padding: 16, maxHeight: 180, overflow: 'hidden' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', color: 'rgba(232,232,240,0.30)', marginBottom: 10, letterSpacing: 1 }}>
            LIVE EVENT LOG
          </div>
          <div id="event-log" style={{ display: 'flex', flexDirection: 'column', fontFamily: "'JetBrains Mono', monospace", fontSize: 9 }}>
            {logEntries.map((e, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
                <span style={{ color: 'rgba(232,232,240,0.18)', flexShrink: 0 }}>{e.time}</span>
                <span style={{ color: e.level === 'success' ? '#3dffa0' : e.level === 'error' ? '#ff6b35' : '#63d9ff', flexShrink: 0 }}>
                  {e.level === 'success' ? '✓' : e.level === 'error' ? '✕' : 'ℹ'}
                </span>
                <span style={{ color: 'rgba(232,232,240,0.42)' }}>{e.message}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Skip button */}
        <div style={{ textAlign: 'center', marginTop: 18 }}>
          <Link to="/projects/test/editor" className="btn btn-primary btn-lg" style={{ textDecoration: 'none' }} id="skip-to-editor">
            Skip to Editor Preview →
          </Link>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)', marginTop: 7 }}>
            In production this auto-redirects when build completes
          </div>
        </div>
      </div>
    </AppShell>
  )
}
