import { useState } from 'react'
import HexLogo from '@/components/shared/HexLogo'

const activityIcons = ['📁', '🔍', '⚡', '🔀', '🐛', '🧪']

interface FileItem {
  name: string
  depth: number
  type: 'file' | 'dir'
  status?: 'active' | 'modified' | 'new'
}

const files: FileItem[] = [
  { name: 'src', depth: 0, type: 'dir' },
  { name: 'app', depth: 1, type: 'dir' },
  { name: 'layout.tsx', depth: 2, type: 'file' },
  { name: 'page.tsx', depth: 2, type: 'file', status: 'active' },
  { name: 'globals.css', depth: 2, type: 'file' },
  { name: 'dashboard', depth: 2, type: 'dir' },
  { name: 'page.tsx', depth: 3, type: 'file', status: 'modified' },
  { name: 'components', depth: 1, type: 'dir' },
  { name: 'Header.tsx', depth: 2, type: 'file' },
  { name: 'Sidebar.tsx', depth: 2, type: 'file', status: 'new' },
  { name: 'Chart.tsx', depth: 2, type: 'file' },
  { name: 'lib', depth: 1, type: 'dir' },
  { name: 'utils.ts', depth: 2, type: 'file' },
  { name: 'api.ts', depth: 2, type: 'file' },
  { name: 'package.json', depth: 0, type: 'file' },
  { name: 'tsconfig.json', depth: 0, type: 'file' },
]

const openTabs = [
  { name: 'page.tsx', modified: false, active: true },
  { name: 'layout.tsx', modified: false, active: false },
  { name: 'page.tsx', modified: true, active: false },
]

const codeLines = [
  "import { Metadata } from 'next'",
  "import { DashboardShell } from '@/components/shell'",
  "import { StatsCards } from '@/components/stats'",
  "",
  "export const metadata: Metadata = {",
  "  title: 'Dashboard | SaaS App',",
  "  description: 'Analytics dashboard',",
  "}",
  "",
  "export default async function DashboardPage() {",
  "  const stats = await getStats()",
  "  const projects = await getProjects()",
  "",
  "  return (",
  "    <DashboardShell>",
  "      <div className=\"grid gap-4 md:grid-cols-4\">",
  "        <StatsCards data={stats} />",
  "      </div>",
  "      <div className=\"mt-8\">",
  "        <h2 className=\"text-xl font-bold\">",
  "          Recent Projects",
  "        </h2>",
  "        {projects.map((p) => (",
  "          <ProjectCard key={p.id} project={p} />",
  "        ))}",
  "      </div>",
  "    </DashboardShell>",
  "  )",
  "}",
]

const chatMessages = [
  { from: 'user', text: 'Add a chart component to the dashboard that shows weekly active users' },
  { from: 'ai', text: "I'll add a WAU chart using Recharts. Here's the implementation:", codeBlock: { filename: 'components/Chart.tsx', code: "import { LineChart } from 'recharts'\n\nexport function WAUChart({ data }) {\n  return <LineChart data={data} />\n}" } },
  { from: 'user', text: 'Can you also add a date range picker?' },
]

const consoleLines: { time: string; type: 'log' | 'warn' | 'error'; msg: string }[] = [
  { time: '14:32:01', type: 'log', msg: '[HMR] Updated modules: dashboard/page.tsx' },
  { time: '14:31:58', type: 'log', msg: 'GET /api/stats 200 OK (12ms)' },
  { time: '14:31:55', type: 'warn', msg: 'React: Missing key prop in ProjectCard list' },
  { time: '14:31:42', type: 'log', msg: '[build] Compiled successfully (340ms)' },
]

export default function EditorPage() {
  const [previewVisible, setPreviewVisible] = useState(true)
  const [activeActivity, setActiveActivity] = useState(0)
  const [chatInput, setChatInput] = useState('')
  const [consoleTab, setConsoleTab] = useState<'console' | 'network' | 'errors'>('console')

  return (
    <div id="editor-page" style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#04040a' }}>
      {/* Top bar — 46px */}
      <div
        id="editor-topbar"
        style={{
          height: 46,
          background: '#080812',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 14px',
          gap: 11,
          flexShrink: 0,
          zIndex: 50,
        }}
      >
        <HexLogo size={22} wordmarkSize={16} />
        <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.08)' }} />
        <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.55)', cursor: 'pointer' }}>SaaS Dashboard ▼</span>
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            padding: '2px 8px',
            borderRadius: 10,
            background: 'rgba(255,255,255,0.05)',
            color: 'rgba(232,232,240,0.40)',
          }}
        >
          ○ main
        </span>

        <div style={{ flex: 1 }} />

        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#ff6b35' }}>● 2 errors</span>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setPreviewVisible(!previewVisible)}
          style={{ fontSize: 10 }}
        >
          {previewVisible ? '⊟' : '⊞'} Preview
        </button>
        <button className="btn btn-primary btn-sm">▲ Deploy</button>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 9,
            fontWeight: 700,
            color: '#04040a',
            cursor: 'pointer',
          }}
        >
          JD
        </div>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: `46px 210px 1fr ${previewVisible ? '310px' : ''} 295px`,
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        {/* Activity bar — 46px */}
        <div
          id="activity-bar"
          style={{
            background: 'rgba(4,4,10,0.90)',
            borderRight: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '10px 0',
            gap: 5,
          }}
        >
          {activityIcons.map((icon, i) => (
            <button
              key={i}
              onClick={() => setActiveActivity(i)}
              style={{
                width: 34,
                height: 34,
                borderRadius: activeActivity === i ? '0 6px 6px 0' : 6,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 14,
                cursor: 'pointer',
                color: activeActivity === i ? '#63d9ff' : 'rgba(232,232,240,0.40)',
                background: activeActivity === i ? 'rgba(99,217,255,0.08)' : 'transparent',
                border: 'none',
                borderLeft: activeActivity === i ? '2px solid #63d9ff' : '2px solid transparent',
                marginLeft: activeActivity === i ? -1 : 0,
                transition: 'all 0.15s',
              }}
            >
              {icon}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <button
            style={{
              width: 34,
              height: 34,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              cursor: 'pointer',
              color: 'rgba(232,232,240,0.40)',
              background: 'transparent',
              border: 'none',
            }}
          >
            ⚙️
          </button>
        </div>

        {/* File tree — 210px */}
        <div
          id="file-tree"
          style={{
            borderRight: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              textTransform: 'uppercase',
              color: 'rgba(232,232,240,0.30)',
              padding: '9px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              justifyContent: 'space-between',
              letterSpacing: 1,
            }}
          >
            <span>Explorer</span>
            <span style={{ color: '#63d9ff', cursor: 'pointer' }}>+</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
            {files.map((f, i) => {
              const dotColor = f.status === 'active' ? '#63d9ff' : f.status === 'modified' ? '#ff6b35' : f.status === 'new' ? '#3dffa0' : f.type === 'dir' ? '#f5c842' : 'transparent'
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: `3px 8px 3px ${8 + f.depth * 11}px`,
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    color: f.status === 'active' ? '#63d9ff' : f.type === 'dir' ? '#e8e8f0' : 'rgba(232,232,240,0.42)',
                    background: f.status === 'active' ? 'rgba(99,217,255,0.08)' : 'transparent',
                    cursor: 'pointer',
                  }}
                >
                  {f.type === 'dir' ? (
                    <span style={{ color: '#f5c842', fontSize: 8 }}>▶</span>
                  ) : (
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
                  )}
                  {f.name}
                </div>
              )
            })}
          </div>
        </div>

        {/* Main editor area */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Tab bar */}
          <div
            style={{
              height: 34,
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              overflowX: 'auto',
              flexShrink: 0,
            }}
          >
            {openTabs.map((tab, i) => (
              <div
                key={i}
                style={{
                  minWidth: 90,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  padding: '0 13px',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  color: tab.active ? '#e8e8f0' : 'rgba(232,232,240,0.40)',
                  borderBottom: tab.active ? '2px solid #63d9ff' : '2px solid transparent',
                  background: tab.active ? 'rgba(255,255,255,0.02)' : 'transparent',
                  cursor: 'pointer',
                }}
              >
                {tab.modified && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff6b35' }} />}
                {tab.name}
                <span style={{ fontSize: 10, color: 'rgba(232,232,240,0.25)', marginLeft: 'auto' }}>×</span>
              </div>
            ))}
          </div>

          {/* Breadcrumb */}
          <div
            style={{
              padding: '5px 14px',
              background: 'rgba(255,255,255,0.015)',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: 'rgba(232,232,240,0.30)',
            }}
          >
            src › app › dashboard › <span style={{ color: '#63d9ff' }}>page.tsx</span>
          </div>

          {/* Code area */}
          <div
            id="code-editor"
            style={{
              flex: 1,
              padding: '16px 18px',
              background: '#04040a',
              overflowY: 'auto',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 12,
              lineHeight: 1.85,
            }}
          >
            {codeLines.map((line, i) => (
              <div key={i} style={{ display: 'flex' }}>
                <span
                  style={{
                    width: 26,
                    textAlign: 'right',
                    marginRight: 14,
                    color: 'rgba(232,232,240,0.15)',
                    userSelect: 'none',
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </span>
                <span>
                  {colorize(line)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Preview pane — 310px (conditional) */}
        {previewVisible && (
          <div
            id="preview-pane"
            style={{
              borderLeft: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Preview toolbar */}
            <div
              style={{
                height: 38,
                background: 'rgba(4,4,10,0.95)',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                display: 'flex',
                alignItems: 'center',
                padding: '0 10px',
                gap: 5,
                flexShrink: 0,
              }}
            >
              <button style={{ background: 'none', border: 'none', color: 'rgba(232,232,240,0.40)', cursor: 'pointer', fontSize: 11 }}>←</button>
              <button style={{ background: 'none', border: 'none', color: 'rgba(232,232,240,0.40)', cursor: 'pointer', fontSize: 11 }}>→</button>
              <div
                style={{
                  flex: 1,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  color: 'rgba(232,232,240,0.30)',
                  background: 'rgba(255,255,255,0.04)',
                  borderRadius: 4,
                  padding: '4px 8px',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                }}
              >
                localhost:3000/dashboard
              </div>
              <button style={{ background: 'none', border: 'none', color: 'rgba(232,232,240,0.40)', cursor: 'pointer', fontSize: 11 }}>📱</button>
              <button style={{ background: 'rgba(99,217,255,0.08)', border: '1px solid rgba(99,217,255,0.22)', color: '#63d9ff', cursor: 'pointer', fontSize: 11, padding: '2px 4px', borderRadius: 3 }}>💻</button>
            </div>

            {/* Preview body */}
            <div
              style={{
                flex: 1,
                background: '#04040a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>⬡</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.25)' }}>
                  PREVIEW LOADING...
                </div>
              </div>
            </div>

            {/* Dev console */}
            <div
              id="dev-console"
              style={{
                background: 'rgba(4,4,10,0.97)',
                borderTop: '1px solid rgba(255,255,255,0.06)',
                flexShrink: 0,
                maxHeight: 100,
                overflow: 'hidden',
              }}
            >
              <div style={{ display: 'flex', gap: 2, padding: '6px 10px 0' }}>
                {(['console', 'network', 'errors'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setConsoleTab(tab)}
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 9,
                      cursor: 'pointer',
                      padding: '2px 6px',
                      borderRadius: 4,
                      border: consoleTab === tab ? '1px solid rgba(99,217,255,0.25)' : '1px solid transparent',
                      color: consoleTab === tab ? '#63d9ff' : 'rgba(232,232,240,0.35)',
                      background: consoleTab === tab ? 'rgba(99,217,255,0.08)' : 'transparent',
                      textTransform: 'capitalize',
                    }}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <div style={{ padding: '4px 10px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9 }}>
                {consoleLines.map((l, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, padding: '1px 0' }}>
                    <span style={{ color: 'rgba(232,232,240,0.16)' }}>{l.time}</span>
                    <span style={{ color: l.type === 'warn' ? '#f5c842' : l.type === 'error' ? '#ff6b35' : 'rgba(232,232,240,0.45)' }}>
                      {l.msg}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Snapshot timeline */}
            <div
              id="snapshot-timeline"
              style={{
                height: 38,
                background: 'rgba(4,4,10,0.95)',
                borderTop: '1px solid rgba(255,255,255,0.06)',
                display: 'flex',
                alignItems: 'center',
                padding: '0 10px',
                gap: 5,
                flexShrink: 0,
              }}
            >
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 7, color: 'rgba(232,232,240,0.30)' }}>
                BUILD
              </span>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                {Array.from({ length: 10 }, (_, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: i < 7 ? '#3dffa0' : 'rgba(232,232,240,0.15)',
                        flexShrink: 0,
                      }}
                    />
                    {i < 9 && (
                      <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.07)', minWidth: 8 }} />
                    )}
                  </div>
                ))}
              </div>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#3dffa0',
                  animation: 'jade-pulse 2s ease-in-out infinite',
                  cursor: 'pointer',
                  marginLeft: 4,
                }}
              />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 7, color: '#3dffa0' }}>
                ● LIVE
              </span>
            </div>
          </div>
        )}

        {/* Chat panel — 295px */}
        <div
          id="chat-panel"
          style={{
            borderLeft: '1px solid rgba(255,255,255,0.06)',
            background: '#080812',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* Chat header */}
          <div
            style={{
              padding: '10px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              flexShrink: 0,
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
              }}
            >
              ⚡
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#e8e8f0' }}>Forge AI</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#3dffa0' }}>
                ● active · claude-sonnet-4
              </div>
            </div>
            <span style={{ color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>⚙</span>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, padding: 12, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 9 }}>
            {chatMessages.map((msg, i) => (
              <div key={i}>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 8,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    marginBottom: 3,
                    color: msg.from === 'user' ? 'rgba(232,232,240,0.35)' : '#63d9ff',
                  }}
                >
                  {msg.from === 'user' ? 'YOU' : 'FORGE AI'}
                </div>
                <div
                  style={{
                    background: msg.from === 'user' ? 'rgba(255,255,255,0.04)' : 'rgba(99,217,255,0.08)',
                    border: `1px solid ${msg.from === 'user' ? 'rgba(255,255,255,0.06)' : 'rgba(99,217,255,0.14)'}`,
                    borderRadius: 8,
                    padding: '9px 11px',
                    fontSize: 11,
                    lineHeight: 1.6,
                    color: msg.from === 'user' ? 'rgba(232,232,240,0.65)' : '#e8e8f0',
                  }}
                >
                  {msg.text}
                  {msg.from === 'ai' && 'codeBlock' in msg && msg.codeBlock && (
                    <div
                      style={{
                        background: '#04040a',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 7,
                        overflow: 'hidden',
                        marginTop: 6,
                      }}
                    >
                      <div
                        style={{
                          padding: '6px 10px',
                          borderBottom: '1px solid rgba(255,255,255,0.06)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#63d9ff' }}>
                          {msg.codeBlock.filename}
                        </span>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button className="btn btn-ghost" style={{ height: 22, padding: '0 6px', fontSize: 8 }}>Copy</button>
                          <button className="btn btn-primary" style={{ height: 22, padding: '0 6px', fontSize: 8 }}>Apply</button>
                        </div>
                      </div>
                      <div style={{ padding: '9px 11px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, lineHeight: 1.7, color: 'rgba(232,232,240,0.65)', whiteSpace: 'pre' }}>
                        {msg.codeBlock.code}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Input area */}
          <div style={{ padding: '9px 10px', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
            {/* Command chips */}
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
              {['/build', '/deploy', '/test', '/lint'].map((cmd) => (
                <button
                  key={cmd}
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 8,
                    padding: '2px 6px',
                    background: 'rgba(99,217,255,0.08)',
                    color: '#63d9ff',
                    border: '1px solid rgba(99,217,255,0.18)',
                    borderRadius: 3,
                    cursor: 'pointer',
                  }}
                >
                  {cmd}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              <textarea
                id="chat-input"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                rows={2}
                placeholder="Ask Forge AI..."
                style={{
                  flex: 1,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  resize: 'none',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: 5,
                  padding: '6px 9px',
                  color: '#e8e8f0',
                  outline: 'none',
                }}
              />
              <button
                style={{
                  width: 28,
                  height: 28,
                  background: '#63d9ff',
                  border: 'none',
                  borderRadius: 5,
                  color: '#04040a',
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: 'pointer',
                  flexShrink: 0,
                  alignSelf: 'flex-end',
                }}
              >
                ↑
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Status bar — 22px */}
      <div
        id="editor-statusbar"
        style={{
          height: 22,
          background: '#63d9ff',
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
          gap: 16,
          flexShrink: 0,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: '#04040a',
          fontWeight: 700,
        }}
      >
        <span>⚡ Forge</span>
        <span>TypeScript</span>
        <span>Ln 10, Col 24</span>
        <span>No errors</span>
        <span>Sandbox: ● Running</span>
        <span>main</span>
      </div>
    </div>
  )
}

/** Minimal syntax coloring for demo */
function colorize(line: string): React.ReactNode {
  if (!line) return '\u00A0'
  // Simple keyword highlighting
  const parts: React.ReactNode[] = []
  const remaining = line

  const patterns: [RegExp, string][] = [
    [/^(import|export|from|const|async|function|return|default)\b/, '#b06bff'],
    [/^(\/\/.*)$/, 'rgba(232,232,240,0.28)'],
    [/'[^']*'/, '#3dffa0'],
    [/"[^"]*"/, '#3dffa0'],
    [/`[^`]*`/, '#3dffa0'],
    [/\b(Metadata|DashboardShell|StatsCards|ProjectCard)\b/, '#f5c842'],
    [/\b(className|data|key|project|stats|projects|title|description|id|p)\b/, '#e8e8f0'],
  ]

  // Simple approach: just return the line with basic coloring
  if (remaining.includes('import') || remaining.includes('export') || remaining.includes('const') || remaining.includes('return') || remaining.includes('async') || remaining.includes('function') || remaining.includes('default')) {
    const words = remaining.split(/(\s+|[{}()=<>/,;.])/)
    return (
      <>
        {words.map((w, i) => {
          const keywords = ['import', 'export', 'from', 'const', 'async', 'function', 'return', 'default']
          const types = ['Metadata', 'DashboardShell', 'StatsCards', 'ProjectCard']
          if (keywords.includes(w)) return <span key={i} style={{ color: '#b06bff' }}>{w}</span>
          if (types.includes(w)) return <span key={i} style={{ color: '#f5c842' }}>{w}</span>
          if (w.startsWith("'") || w.startsWith('"')) return <span key={i} style={{ color: '#3dffa0' }}>{w}</span>
          if (['=', '<', '>', '/', '{', '}', '(', ')', '.'].includes(w)) return <span key={i} style={{ color: '#ff6b35' }}>{w}</span>
          return <span key={i}>{w}</span>
        })}
      </>
    )
  }

  // Just dump unmatched content
  void patterns
  parts.push(<span key="rest">{remaining || '\u00A0'}</span>)
  return <>{parts}</>
}
