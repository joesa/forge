import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AppShell from '@/components/layout/AppShell'
import { isUuid, usePipelineStatus, useRetryPipeline } from '@/hooks/queries/usePipeline'
import { useProject } from '@/hooks/queries/useProjects'

// Backend stage key → display name
const STAGE_NAMES: Record<string, string> = {
  input_layer: 'Input Layer',
  csuite_analysis: 'C-Suite Analysis',
  synthesis: 'Synthesis',
  spec_layer: 'Spec Layer',
  bootstrap: 'Bootstrap',
  build: 'Build',
}
const STAGE_KEYS = ['input_layer', 'csuite_analysis', 'synthesis', 'spec_layer', 'bootstrap', 'build']

// C-Suite analyst agents (maps to backend ceo/cpo/cto/cso/cfo/cdo/cmo/cco)
const CSUITE_AGENTS = [
  { emoji: '📊', role: 'Market Analyst', key: 'ceo' },
  { emoji: '🎯', role: 'Product Strategist', key: 'cpo' },
  { emoji: '🏗️', role: 'Tech Architect', key: 'cto' },
  { emoji: '🔒', role: 'Security Advisor', key: 'cso' },
  { emoji: '💰', role: 'Revenue Modeler', key: 'cfo' },
  { emoji: '🎨', role: 'UX Director', key: 'cdo' },
  { emoji: '🚀', role: 'GTM Strategist', key: 'cmo' },
  { emoji: '📋', role: 'Compliance Officer', key: 'cco' },
]

interface LogEntry {
  time: string
  level: 'info' | 'success' | 'error'
  message: string
}

function formatElapsed(startedAt: string | null | undefined): string {
  if (!startedAt) return '0:00'
  const diff = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000))
  const mins = Math.floor(diff / 60)
  const secs = diff % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function getPipelineWsUrl(pipelineId: string): string {
  const apiUrl = import.meta.env.VITE_API_URL || ''
  if (apiUrl.startsWith('http')) {
    return `${apiUrl.replace(/^http/, 'ws')}/pipeline/${pipelineId}/stream`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/v1/pipeline/${pipelineId}/stream`
}

export default function PipelinePage() {
  const { id = '' } = useParams<{ id: string }>()
  const hasValidPipelineId = isUuid(id)
  const navigate = useNavigate()

  const { data: status, isLoading } = usePipelineStatus(id)
  const { data: project } = useProject(status?.project_id ? String(status.project_id) : '')
  const retryPipeline = useRetryPipeline()

  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [elapsed, setElapsed] = useState('0:00')
  const [wsStages, setWsStages] = useState<Record<string, 'pending' | 'running' | 'done' | 'failed'>>({})
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket — subscribe to live pipeline events
  useEffect(() => {
    if (!hasValidPipelineId) return
    let cancelled = false

    // Delay WS creation slightly so React StrictMode's
    // mount→unmount→remount cycle can cancel before we open a socket
    const timer = setTimeout(() => {
      if (cancelled) return
      const ws = new WebSocket(getPipelineWsUrl(id))
      wsRef.current = ws

      ws.onerror = () => {
        // Suppress console noise for expected failures (proxy, cleanup)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string)
          const stageNum = data.stage as number
          const stageKey = STAGE_KEYS[stageNum - 1]
          const stageName = stageKey ? STAGE_NAMES[stageKey] : `Stage ${stageNum}`
          const wsStatus = data.status as string

          // Update stage status map from WS events
          if (stageKey && wsStatus) {
            setWsStages((prev) => {
              const next = { ...prev }
              if (wsStatus === 'completed') {
                next[stageKey] = 'done'
                // Mark all prior stages done
                STAGE_KEYS.slice(0, stageNum - 1).forEach((k) => {
                  if (!next[k] || next[k] === 'running' || next[k] === 'pending') {
                    next[k] = 'done'
                  }
                })
              } else if (wsStatus === 'failed') {
                next[stageKey] = 'failed'
              } else if (wsStatus === 'running') {
                next[stageKey] = 'running'
                // Mark all prior stages done
                STAGE_KEYS.slice(0, stageNum - 1).forEach((k) => {
                  if (!next[k] || next[k] === 'pending') {
                    next[k] = 'done'
                  }
                })
              }
              return next
            })
          }

          // Build log entry
          const lvl: LogEntry['level'] =
            wsStatus === 'completed' ? 'success' : wsStatus === 'failed' ? 'error' : 'info'
          const msg = data.detail ? `${stageName}: ${data.detail}` : `${stageName} ${wsStatus}`
          const timeStr = new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })
          setLogEntries((prev) => [{ time: timeStr, level: lvl, message: msg }, ...prev].slice(0, 50))
        } catch {
          // ignore malformed messages
        }
      }
    }, 0)

    return () => {
      cancelled = true
      clearTimeout(timer)
      const ws = wsRef.current
      if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
        ws.close()
      }
      wsRef.current = null
    }
  }, [id, hasValidPipelineId])

  if (!hasValidPipelineId) {
    return (
      <AppShell>
        <div style={{ padding: '34px 32px', maxWidth: 900 }}>
          <div className="card" style={{ padding: 20 }}>
            <h1 style={{ fontSize: 18, fontWeight: 800, color: '#e8e8f0', marginBottom: 8 }}>
              Invalid Pipeline ID
            </h1>
            <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.55)', marginBottom: 14 }}>
              The URL uses an invalid pipeline id format. Open a pipeline using the full UUID.
            </div>
            <Link to="/projects" className="btn btn-primary btn-sm" style={{ textDecoration: 'none' }}>
              Back to Projects
            </Link>
          </div>
        </div>
      </AppShell>
    )
  }

  // Elapsed timer — ticks every second while pipeline is running
  useEffect(() => {
    if (!status?.started_at || status.status === 'completed' || status.status === 'failed') return
    const tick = () => setElapsed(formatElapsed(status.started_at))
    tick()
    const iv = setInterval(tick, 1000)
    return () => clearInterval(iv)
  }, [status?.started_at, status?.status])

  // Auto-redirect to editor when pipeline completes
  useEffect(() => {
    if (status?.status === 'completed' && status.project_id) {
      navigate(`/projects/${status.project_id}/editor`)
    }
  }, [status?.status, status?.project_id, navigate])

  // ── Derived state ────────────────────────────────────────────────
  const pipelineStatus = status?.status || 'queued'
  const currentStage = status?.current_stage || 0

  const stages = STAGE_KEYS.map((key, idx) => {
    const num = idx + 1
    // Prefer live WS-derived status; fall back to DB-polled status
    if (wsStages[key]) {
      return { name: STAGE_NAMES[key], key, status: wsStages[key] }
    }
    let s: 'done' | 'running' | 'pending' | 'failed'
    if (pipelineStatus === 'completed') {
      s = 'done'
    } else if (pipelineStatus === 'failed' || pipelineStatus === 'error') {
      s = num < currentStage ? 'done' : num === currentStage ? 'failed' : 'pending'
    } else if (pipelineStatus === 'running') {
      s = num <= currentStage ? 'done' : num === currentStage + 1 ? 'running' : 'pending'
    } else {
      s = 'pending'
    }
    return { name: STAGE_NAMES[key], key, status: s }
  })

  const runningIdx = stages.findIndex((s) => s.status === 'running')
  const lastDoneIdx = stages.reduce((acc, s, i) => (s.status === 'done' ? i : acc), -1)
  const activeIdx = runningIdx >= 0 ? runningIdx : lastDoneIdx >= 0 ? lastDoneIdx : 0
  const activeStage = stages[activeIdx]

  const csuiteStage = stages[1]
  const agentStatus = csuiteStage?.status ?? 'pending'
  const completedAgents = agentStatus === 'done' ? 8 : agentStatus === 'running' ? 4 : 0

  const runningStageNum = runningIdx >= 0 ? runningIdx + 1 : 0

  // ── Stage circle ─────────────────────────────────────────────────
  const stageCircle = (s: (typeof stages)[0], idx: number) => {
    const bg: Record<string, React.CSSProperties> = {
      done: { background: '#3dffa0', color: '#04040a' },
      running: { background: '#63d9ff', color: '#04040a', boxShadow: '0 0 0 3px rgba(99,217,255,0.20)' },
      pending: { background: 'rgba(255,255,255,0.07)', color: 'rgba(232,232,240,0.35)' },
      failed: { background: '#ff6b35', color: '#fff' },
    }
    const icon: Record<string, string> = { done: '✓', running: '◎', pending: String(idx + 1), failed: '✕' }
    return (
      <div
        style={{
          width: 26, height: 26, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, flexShrink: 0,
          ...bg[s.status],
        }}
      >
        {icon[s.status]}
      </div>
    )
  }

  return (
    <AppShell>
      <div style={{ padding: '34px 32px', maxWidth: 1100 }}>
        {isLoading && (
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(232,232,240,0.42)', paddingBottom: 18 }}>
            Loading pipeline...
          </div>
        )}
        {/* Header */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Link to="/projects" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>← Projects</Link>
            <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.8px', color: '#e8e8f0' }}>
              {project?.name ? `Building: ${project.name}` : 'Building...'}
            </h1>
            <span className="tag tag-m" style={{ fontSize: 8 }}>/pipeline</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {pipelineStatus === 'running' && (
              <span className="tag status-building" style={{ animation: 'pulse-f 1.8s ease-in-out infinite' }}>
                ◎ Running{runningStageNum > 0 ? ` — Stage ${runningStageNum} of 6` : ''}
              </span>
            )}
            {pipelineStatus === 'completed' && (
              <span className="tag" style={{ background: 'rgba(61,255,160,0.12)', color: '#3dffa0' }}>✓ Complete</span>
            )}
            {(pipelineStatus === 'failed' || pipelineStatus === 'error') && (
              <span className="tag" style={{ background: 'rgba(255,107,53,0.12)', color: '#ff6b35' }}>✕ Failed</span>
            )}
            {pipelineStatus === 'queued' && (
              <span className="tag">◎ Queued</span>
            )}
            {status?.started_at && (
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.42)' }}>
                Elapsed: {elapsed}
              </span>
            )}
          </div>
        </div>

        {/* 2-col layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: 18, marginBottom: 18 }}>
          {/* Stage list */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', color: 'rgba(232,232,240,0.30)', marginBottom: 13, letterSpacing: 1 }}>
              PIPELINE STAGES
            </div>
            {stages.map((s, i) => (
              <div
                key={s.key}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 7px',
                  borderBottom: i < stages.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                  background: activeIdx === i ? 'rgba(99,217,255,0.04)' : 'transparent',
                  borderRadius: 6,
                }}
              >
                {stageCircle(s, i)}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#e8e8f0' }}>{s.name}</div>
                  <div style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(232,232,240,0.30)' }}>
                    {s.status === 'done' ? 'Completed' : s.status === 'running' ? 'In progress...' : s.status === 'failed' ? 'Failed' : 'Pending'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Stage detail panel */}
          <div className="card" style={{ padding: 16 }}>
            {activeStage?.key === 'csuite_analysis' ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h2 style={{ fontSize: 16, fontWeight: 700, color: '#e8e8f0' }}>C-Suite Analysis</h2>
                  <span className="tag tag-j">{completedAgents}/8 Complete</span>
                </div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)', marginBottom: 14 }}>
                  8 executive agents analyzing in parallel
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
                  {CSUITE_AGENTS.map((a) => (
                    <div
                      key={a.key}
                      style={{
                        background: '#111125',
                        border: `1px solid ${agentStatus === 'done' ? 'rgba(61,255,160,0.2)' : agentStatus === 'running' ? 'rgba(99,217,255,0.22)' : 'rgba(255,255,255,0.06)'}`,
                        borderRadius: 8,
                        padding: '12px 13px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 18 }}>{a.emoji}</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#e8e8f0', flex: 1 }}>{a.role}</span>
                        {agentStatus === 'done' && <span style={{ color: '#3dffa0', fontSize: 12 }}>✓</span>}
                        {agentStatus === 'running' && (
                          <div style={{ width: 14, height: 14, border: '2px solid #63d9ff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                        )}
                        {agentStatus === 'pending' && <span style={{ color: 'rgba(232,232,240,0.30)', fontSize: 11 }}>○</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h2 style={{ fontSize: 16, fontWeight: 700, color: '#e8e8f0' }}>
                    {activeStage?.name || 'Pipeline'}
                  </h2>
                  <span className="tag tag-j" style={{ textTransform: 'capitalize' }}>
                    {activeStage?.status || 'pending'}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>
                  {activeStage?.status === 'running' ? 'Processing...'
                    : activeStage?.status === 'done' ? 'Completed successfully'
                    : activeStage?.status === 'failed' ? 'Stage failed — check errors below'
                    : 'Waiting to start'}
                </div>
                {status?.errors && status.errors.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    {status.errors.map((err: string, i: number) => (
                      <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#ff6b35', padding: '3px 0' }}>
                        ✕ {err}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Live event log */}
        <div className="card" style={{ padding: 16, maxHeight: 180, overflow: 'hidden' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', color: 'rgba(232,232,240,0.30)', marginBottom: 10, letterSpacing: 1 }}>
            LIVE EVENT LOG
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', fontFamily: "'JetBrains Mono', monospace", fontSize: 9 }}>
            {logEntries.length === 0 ? (
              <div style={{ color: 'rgba(232,232,240,0.20)' }}>
                {pipelineStatus === 'queued' ? 'Waiting for pipeline to start...' : 'Connecting to live stream...'}
              </div>
            ) : (
              logEntries.map((e, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
                  <span style={{ color: 'rgba(232,232,240,0.18)', flexShrink: 0 }}>{e.time}</span>
                  <span style={{
                    color: e.level === 'success' ? '#3dffa0' : e.level === 'error' ? '#ff6b35' : '#63d9ff',
                    flexShrink: 0,
                  }}>
                    {e.level === 'success' ? '✓' : e.level === 'error' ? '✕' : 'ℹ'}
                  </span>
                  <span style={{ color: 'rgba(232,232,240,0.42)' }}>{e.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Editor button */}
        {status?.project_id && (
          <div style={{ textAlign: 'center', marginTop: 18, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              {(pipelineStatus === 'failed' || pipelineStatus === 'error') && (
                <button
                  className="btn btn-ghost btn-lg"
                  disabled={retryPipeline.isPending}
                  onClick={() => {
                    retryPipeline.mutate(id, {
                      onSuccess: (data: { pipeline_id: string }) => {
                        navigate(`/pipeline/${data.pipeline_id}`)
                      },
                    })
                  }}
                >
                  {retryPipeline.isPending ? 'Starting...' : '↺ Retry Build'}
                </button>
              )}
              <Link
                to={`/projects/${status.project_id}/editor`}
                className="btn btn-primary btn-lg"
                style={{ textDecoration: 'none' }}
              >
                {pipelineStatus === 'completed' ? 'Open Editor →' : 'Skip to Editor →'}
              </Link>
            </div>
            {pipelineStatus !== 'completed' && (
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>
                Auto-redirects when build completes
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
