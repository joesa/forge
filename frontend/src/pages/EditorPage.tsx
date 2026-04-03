/* ------------------------------------------------------------------ */
/*  FORGE — Editor Page                                                */
/*  Full viewport layout: activity bar + file tree + Monaco editor     */
/*  + preview pane + chat panel + status bar                           */
/* ------------------------------------------------------------------ */

import { useState, lazy, Suspense } from 'react'
import { useParams } from 'react-router-dom'
import HexLogo from '@/components/shared/HexLogo'
import FileTree from '@/components/editor/FileTree'
import EditorTabs from '@/components/editor/EditorTabs'
import PreviewPane from '@/components/editor/PreviewPane'
import Terminal from '@/components/editor/Terminal'
import { useEditor } from '@/hooks/useEditor'
import { useEditorStore } from '@/stores/editorStore'

/* Lazy load Monaco so it doesn't block initial paint */
const MonacoEditor = lazy(
  () => import('@/components/editor/MonacoEditor'),
)

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const activityIcons = ['📁', '🔍', '⚡', '🔀', '🐛', '🧪']

const chatMessages = [
  {
    from: 'user' as const,
    text: 'Add a chart component to the dashboard that shows weekly active users',
  },
  {
    from: 'ai' as const,
    text: "I'll add a WAU chart using Recharts. Here's the implementation:",
    codeBlock: {
      filename: 'components/Chart.tsx',
      code: "import { LineChart } from 'recharts'\n\nexport function WAUChart({ data }) {\n  return <LineChart data={data} />\n}",
    },
  },
  { from: 'user' as const, text: 'Can you also add a date range picker?' },
]

/* ------------------------------------------------------------------ */
/*  Editor Page Component                                              */
/* ------------------------------------------------------------------ */
export default function EditorPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const { handleContentChange } = useEditor(projectId ?? 'test')

  /* Local UI state */
  const [activeActivity, setActiveActivity] = useState(0)
  const [chatInput, setChatInput] = useState('')
  const [terminalVisible, setTerminalVisible] = useState(false)

  /* Store selectors */
  const previewVisible = useEditorStore((s) => s.previewVisible)
  const togglePreview = useEditorStore((s) => s.togglePreview)
  const activeFile = useEditorStore((s) => s.activeFile)
  const fileContents = useEditorStore((s) => s.fileContents)
  const modifiedFiles = useEditorStore((s) => s.modifiedFiles)

  /* Count modified files for status bar */
  const modifiedCount = Object.keys(modifiedFiles).length

  /* Breadcrumb from active file */
  const breadcrumb = activeFile
    ? activeFile.split('/').map((part, i, arr) =>
        i === arr.length - 1 ? (
          <span key={i} style={{ color: '#63d9ff' }}>{part}</span>
        ) : (
          <span key={i}>
            {part}
            <span style={{ margin: '0 5px', color: 'rgba(232,232,240,0.18)' }}>›</span>
          </span>
        ),
      )
    : null

  return (
    <div
      id="editor-page"
      style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: '#04040a',
      }}
    >
      {/* ============================================================ */}
      {/*  TOP BAR — 46px                                               */}
      {/* ============================================================ */}
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
        <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.55)', cursor: 'pointer' }}>
          SaaS Dashboard ▼
        </span>
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

        {modifiedCount > 0 && (
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: '#ff6b35',
            }}
          >
            ● {modifiedCount} unsaved
          </span>
        )}
        <button
          className="btn btn-ghost btn-sm"
          onClick={togglePreview}
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

      {/* ============================================================ */}
      {/*  BODY GRID                                                    */}
      {/* ============================================================ */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: `46px 210px 1fr ${previewVisible ? '310px' : ''} 295px`,
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        {/* ---------------------------------------------------------- */}
        {/*  ACTIVITY BAR — 46px                                        */}
        {/* ---------------------------------------------------------- */}
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
            onClick={() => setTerminalVisible((v) => !v)}
            style={{
              width: 34,
              height: 34,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
              cursor: 'pointer',
              color: terminalVisible ? '#63d9ff' : 'rgba(232,232,240,0.40)',
              background: terminalVisible ? 'rgba(99,217,255,0.08)' : 'transparent',
              border: 'none',
            }}
            title="Toggle Terminal"
          >
            💻
          </button>
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

        {/* ---------------------------------------------------------- */}
        {/*  FILE TREE — 210px                                          */}
        {/* ---------------------------------------------------------- */}
        <FileTree />

        {/* ---------------------------------------------------------- */}
        {/*  MAIN EDITOR AREA                                           */}
        {/* ---------------------------------------------------------- */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Tab bar */}
          <EditorTabs />

          {/* Breadcrumb */}
          {activeFile && (
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
              {breadcrumb}
            </div>
          )}

          {/* Monaco Editor */}
          <div
            id="code-editor"
            style={{
              flex: 1,
              background: '#04040a',
              overflow: 'hidden',
              minHeight: 0,
            }}
          >
            {activeFile && activeFile in fileContents ? (
              <Suspense
                fallback={
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      background: '#04040a',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 10,
                        color: 'rgba(232,232,240,0.25)',
                        letterSpacing: 2,
                        textTransform: 'uppercase',
                      }}
                    >
                      Loading editor...
                    </span>
                  </div>
                }
              >
                <MonacoEditor
                  filePath={activeFile}
                  content={fileContents[activeFile] ?? ''}
                  onChange={handleContentChange}
                />
              </Suspense>
            ) : (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 36, marginBottom: 8, opacity: 0.15 }}>⬡</div>
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 10,
                      color: 'rgba(232,232,240,0.20)',
                      letterSpacing: 2,
                      textTransform: 'uppercase',
                    }}
                  >
                    Select a file to edit
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Terminal Panel (collapsible) */}
          {terminalVisible && (
            <div
              id="terminal-panel"
              style={{
                height: 180,
                borderTop: '1px solid rgba(255,255,255,0.06)',
                flexShrink: 0,
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  right: 8,
                  zIndex: 2,
                  padding: '4px 8px',
                }}
              >
                <button
                  onClick={() => setTerminalVisible(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'rgba(232,232,240,0.30)',
                    cursor: 'pointer',
                    fontSize: 14,
                  }}
                >
                  ×
                </button>
              </div>
              <Terminal sandboxId={projectId ?? null} visible={terminalVisible} />
            </div>
          )}
        </div>

        {/* ---------------------------------------------------------- */}
        {/*  PREVIEW PANE — 310px (conditional)                         */}
        {/* ---------------------------------------------------------- */}
        {previewVisible && <PreviewPane />}

        {/* ---------------------------------------------------------- */}
        {/*  CHAT PANEL — 295px                                         */}
        {/* ---------------------------------------------------------- */}
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
              <div style={{ fontSize: 12, fontWeight: 700, color: '#e8e8f0' }}>
                Forge AI
              </div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 8,
                  color: '#3dffa0',
                }}
              >
                ● active · claude-sonnet-4
              </div>
            </div>
            <span style={{ color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>⚙</span>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              padding: 12,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 9,
            }}
          >
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
                    background:
                      msg.from === 'user'
                        ? 'rgba(255,255,255,0.04)'
                        : 'rgba(99,217,255,0.08)',
                    border: `1px solid ${msg.from === 'user' ? 'rgba(255,255,255,0.06)' : 'rgba(99,217,255,0.14)'}`,
                    borderRadius: 8,
                    padding: '9px 11px',
                    fontSize: 11,
                    lineHeight: 1.6,
                    color:
                      msg.from === 'user' ? 'rgba(232,232,240,0.65)' : '#e8e8f0',
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
                        <span
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 9,
                            color: '#63d9ff',
                          }}
                        >
                          {msg.codeBlock.filename}
                        </span>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button
                            className="btn btn-ghost"
                            style={{ height: 22, padding: '0 6px', fontSize: 8 }}
                          >
                            Copy
                          </button>
                          <button
                            className="btn btn-primary"
                            style={{ height: 22, padding: '0 6px', fontSize: 8 }}
                          >
                            Apply
                          </button>
                        </div>
                      </div>
                      <div
                        style={{
                          padding: '9px 11px',
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 9,
                          lineHeight: 1.7,
                          color: 'rgba(232,232,240,0.65)',
                          whiteSpace: 'pre',
                        }}
                      >
                        {msg.codeBlock.code}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Input area */}
          <div
            style={{
              padding: '9px 10px',
              borderTop: '1px solid rgba(255,255,255,0.06)',
              flexShrink: 0,
            }}
          >
            {/* Command chips */}
            <div
              style={{
                display: 'flex',
                gap: 4,
                flexWrap: 'wrap',
                marginBottom: 6,
              }}
            >
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

      {/* ============================================================ */}
      {/*  STATUS BAR — 22px                                            */}
      {/* ============================================================ */}
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
        <span>Ln 1, Col 1</span>
        <span>{modifiedCount > 0 ? `${modifiedCount} unsaved` : 'No changes'}</span>
        <span>Sandbox: ● Running</span>
        <span>main</span>
      </div>
    </div>
  )
}
