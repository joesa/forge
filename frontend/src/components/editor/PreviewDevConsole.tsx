/* ------------------------------------------------------------------ */
/*  FORGE — PreviewDevConsole                                          */
/*  Developer console that streams real-time logs from the sandbox.    */
/*  Three tabs: Console, Network, Errors                               */
/*  WebSocket to /api/v1/sandbox/{sandboxId}/console                   */
/* ------------------------------------------------------------------ */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useEditorStore } from '@/stores/editorStore'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PreviewDevConsoleProps {
  sandboxId: string | null
  projectId: string | null
}

interface ConsoleEvent {
  type: 'log' | 'warn' | 'error' | 'network_request' | 'network_response'
  data: ConsoleEventData
  timestamp: string
}

interface ConsoleLogData {
  message: string
  source?: string
  line?: number
  stack?: string
}

interface NetworkRequestData {
  id: string
  method: string
  url: string
  headers?: Record<string, string>
  body?: string
}

interface NetworkResponseData {
  id: string
  status: number
  duration: number
  headers?: Record<string, string>
  body?: string
}

type ConsoleEventData = ConsoleLogData | NetworkRequestData | NetworkResponseData

interface ConsoleLineEntry {
  id: number
  type: 'log' | 'warn' | 'error'
  message: string
  timestamp: string
  source?: string
  line?: number
  stack?: string
  isHmr: boolean
}

interface NetworkEntry {
  id: string
  method: string
  url: string
  status: number | null
  duration: number | null
  requestHeaders?: Record<string, string>
  requestBody?: string
  responseHeaders?: Record<string, string>
  responseBody?: string
  timestamp: string
}

type TabId = 'console' | 'network' | 'errors'

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const MAX_CONSOLE_LINES = 200
const MAX_NETWORK_ENTRIES = 100
const MAX_RESPONSE_BODY_CHARS = 1000
const WS_INITIAL_BACKOFF_MS = 1000
const WS_MAX_BACKOFF_MS = 16000

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const monoFont = "'JetBrains Mono', monospace"

/**
 * Parse file path + line number from a message string.
 * Matches patterns like: "at components/Card.tsx:47" or "Card.tsx:47:12"
 */
function parseSourceLink(text: string): { file: string; line: number; match: string } | null {
  const re = /(?:at\s+)?([a-zA-Z0-9_/.-]+\.[a-zA-Z]+):(\d+)(?::\d+)?/
  const m = re.exec(text)
  if (!m) return null
  return { file: m[1], line: Number(m[2]), match: m[0] }
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-GB', { hour12: false })
  } catch {
    return ts
  }
}

function isConsoleLogData(data: ConsoleEventData): data is ConsoleLogData {
  return 'message' in data
}

function isNetworkRequestData(data: ConsoleEventData): data is NetworkRequestData {
  return 'method' in data && 'url' in data && !('status' in data)
}

function isNetworkResponseData(data: ConsoleEventData): data is NetworkResponseData {
  return 'status' in data && 'duration' in data
}

function methodColor(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET': return '#63d9ff'
    case 'POST': return '#3dffa0'
    case 'PUT': return '#f5c842'
    case 'PATCH': return '#b06bff'
    case 'DELETE': return '#ff6b35'
    default: return 'rgba(232,232,240,0.45)'
  }
}

function statusColor(status: number): string {
  if (status >= 200 && status < 300) return '#3dffa0'
  if (status >= 300 && status < 400) return '#f5c842'
  return '#ff6b35'
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function PreviewDevConsole({ sandboxId, projectId }: PreviewDevConsoleProps) {
  /* ---- Tab + expand state ---- */
  const [activeTab, setActiveTab] = useState<TabId>('console')
  const [expanded, setExpanded] = useState(true)

  /* ---- Data arrays ---- */
  const [consoleLines, setConsoleLines] = useState<ConsoleLineEntry[]>([])
  const [networkEntries, setNetworkEntries] = useState<NetworkEntry[]>([])
  const [expandedNetworkId, setExpandedNetworkId] = useState<string | null>(null)

  /* ---- WebSocket state ---- */
  const [wsStatus, setWsStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(WS_INITIAL_BACKOFF_MS)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lineIdRef = useRef(0)

  /* ---- Auto-scroll ---- */
  const consoleScrollRef = useRef<HTMLDivElement>(null)
  const userScrolledUpRef = useRef(false)

  /* ---- Store integration ---- */
  const setDevConsoleErrors = useEditorStore((s) => s.setDevConsoleErrors)
  const openFile = useEditorStore((s) => s.openFile)
  const appendChatMessage = useEditorStore((s) => s.appendChatMessage)

  /* ---- Derived: error entries ---- */
  const errorEntries = useMemo(
    () => consoleLines.filter((l) => l.type === 'error'),
    [consoleLines],
  )

  /* ---- Sync error count to editorStore ---- */
  useEffect(() => {
    setDevConsoleErrors(errorEntries.length)
  }, [errorEntries.length, setDevConsoleErrors])

  /* ---- Process incoming event ---- */
  const handleEvent = useCallback((event: ConsoleEvent) => {
    const { type, data, timestamp } = event

    if (type === 'log' || type === 'warn' || type === 'error') {
      if (!isConsoleLogData(data)) return
      const entry: ConsoleLineEntry = {
        id: ++lineIdRef.current,
        type,
        message: data.message,
        timestamp,
        source: data.source,
        line: data.line,
        stack: data.stack,
        isHmr: data.message.startsWith('[HMR]'),
      }
      setConsoleLines((prev) => {
        const next = [...prev, entry]
        return next.length > MAX_CONSOLE_LINES ? next.slice(next.length - MAX_CONSOLE_LINES) : next
      })
    } else if (type === 'network_request') {
      if (!isNetworkRequestData(data)) return
      const entry: NetworkEntry = {
        id: data.id,
        method: data.method,
        url: data.url,
        status: null,
        duration: null,
        requestHeaders: data.headers,
        requestBody: data.body,
        timestamp,
      }
      setNetworkEntries((prev) => {
        const next = [...prev, entry]
        return next.length > MAX_NETWORK_ENTRIES ? next.slice(next.length - MAX_NETWORK_ENTRIES) : next
      })
    } else if (type === 'network_response') {
      if (!isNetworkResponseData(data)) return
      setNetworkEntries((prev) =>
        prev.map((e) =>
          e.id === data.id
            ? {
                ...e,
                status: data.status,
                duration: data.duration,
                responseHeaders: data.headers,
                responseBody: data.body
                  ? data.body.substring(0, MAX_RESPONSE_BODY_CHARS)
                  : undefined,
              }
            : e,
        ),
      )
    }
  }, [])

  /* ---- Auto-scroll logic ---- */
  useEffect(() => {
    const el = consoleScrollRef.current
    if (!el || userScrolledUpRef.current) return
    el.scrollTop = el.scrollHeight
  }, [consoleLines])

  const handleConsoleScroll = useCallback(() => {
    const el = consoleScrollRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20
    userScrolledUpRef.current = !isAtBottom
  }, [])

  /* ---- WebSocket connection ---- */
  useEffect(() => {
    if (!sandboxId) return

    let cancelled = false

    function connect() {
      if (cancelled) return

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/api/v1/sandbox/${sandboxId}/console`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) {
          ws.close()
          return
        }
        setWsStatus('connected')
        backoffRef.current = WS_INITIAL_BACKOFF_MS
      }

      ws.onmessage = (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data as string) as ConsoleEvent
          handleEvent(event)
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (cancelled) return
        setWsStatus('reconnecting')
        const delay = Math.min(backoffRef.current, WS_MAX_BACKOFF_MS)
        backoffRef.current = delay * 2
        reconnectTimerRef.current = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        // onclose will fire after onerror, triggering reconnect
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setWsStatus('disconnected')
    }
  }, [sandboxId, handleEvent])

  /* ---- Clear handler ---- */
  const handleClear = useCallback(() => {
    if (activeTab === 'console' || activeTab === 'errors') {
      setConsoleLines([])
      userScrolledUpRef.current = false
    } else if (activeTab === 'network') {
      setNetworkEntries([])
      setExpandedNetworkId(null)
    }
  }, [activeTab])

  /* ---- Source link click handler ---- */
  const handleSourceClick = useCallback(
    (file: string, line: number) => {
      void openFile(file).then(() => {
        // Monaco editor integration — openFile sets activeFile,
        // line number navigation is handled by the editor component
        // via editorStore cursor position
      })
      void line // Line info is available for Monaco cursor positioning
    },
    [openFile],
  )

  /* ---- Send to AI handler ---- */
  const handleSendToAi = useCallback(
    (message: string, stack?: string) => {
      const content = `Fix this error:\n${message}${stack ? `\n${stack}` : ''}`
      appendChatMessage(content)
    },
    [appendChatMessage],
  )

  /* ---- Suppress unused warning for projectId — used for context ---- */
  void projectId

  /* ---- Header (always visible, 30px) ---- */
  const renderHeader = () => (
    <div
      id="dev-console-header"
      onClick={() => setExpanded((v) => !v)}
      style={{
        height: 30,
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px',
        gap: 4,
        cursor: 'pointer',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {/* Collapse arrow */}
      <span
        style={{
          fontFamily: monoFont,
          fontSize: 8,
          color: 'rgba(232,232,240,0.30)',
          marginRight: 2,
          display: 'inline-block',
          transition: 'transform 150ms ease',
          transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
        }}
      >
        ▶
      </span>

      {/* Tab buttons */}
      {(['console', 'network', 'errors'] as const).map((tab) => (
        <button
          key={tab}
          id={`dev-console-tab-${tab}`}
          onClick={(e) => {
            e.stopPropagation()
            setActiveTab(tab)
            if (!expanded) setExpanded(true)
          }}
          style={{
            fontFamily: monoFont,
            fontSize: 9,
            cursor: 'pointer',
            padding: '2px 7px',
            borderRadius: 4,
            border:
              activeTab === tab
                ? '1px solid rgba(99,217,255,0.25)'
                : '1px solid transparent',
            color: activeTab === tab ? '#63d9ff' : 'rgba(232,232,240,0.35)',
            background:
              activeTab === tab ? 'rgba(99,217,255,0.08)' : 'transparent',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          {tab}
          {tab === 'errors' && errorEntries.length > 0 && (
            <span
              style={{
                fontFamily: monoFont,
                fontSize: 8,
                color: '#04040a',
                background: '#ff6b35',
                borderRadius: 6,
                padding: '0 4px',
                minWidth: 14,
                textAlign: 'center',
                fontWeight: 700,
                lineHeight: '14px',
              }}
            >
              {errorEntries.length}
            </span>
          )}
        </button>
      ))}

      {/* Reconnecting indicator */}
      {wsStatus === 'reconnecting' && (
        <span
          style={{
            fontFamily: monoFont,
            fontSize: 8,
            color: 'rgba(232,232,240,0.25)',
            fontStyle: 'italic',
            marginLeft: 4,
          }}
        >
          Reconnecting...
        </span>
      )}

      <div style={{ flex: 1 }} />

      {/* Expand button */}
      <button
        id="dev-console-expand"
        onClick={(e) => {
          e.stopPropagation()
          setExpanded((v) => !v)
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'rgba(232,232,240,0.25)',
          cursor: 'pointer',
          fontSize: 10,
          fontFamily: monoFont,
          padding: '0 2px',
        }}
        title={expanded ? 'Collapse' : 'Expand'}
      >
        ⊡
      </button>

      {/* Clear button */}
      <button
        id="dev-console-clear"
        onClick={(e) => {
          e.stopPropagation()
          handleClear()
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'rgba(232,232,240,0.25)',
          cursor: 'pointer',
          fontSize: 10,
          fontFamily: monoFont,
          padding: '0 2px',
        }}
        title="Clear"
      >
        ✕
      </button>
    </div>
  )

  /* ---- Console Tab ---- */
  const renderConsoleTab = () => (
    <div
      ref={consoleScrollRef}
      onScroll={handleConsoleScroll}
      style={{
        overflowY: 'auto',
        padding: '4px 10px',
        flex: 1,
        minHeight: 0,
      }}
    >
      {consoleLines.length === 0 && (
        <div
          style={{
            fontFamily: monoFont,
            fontSize: 9,
            color: 'rgba(232,232,240,0.18)',
            padding: '8px 0',
          }}
        >
          No console output yet
        </div>
      )}
      {consoleLines.map((line) => {
        const sourceLink = parseSourceLink(line.message)
        const lineColor =
          line.type === 'warn'
            ? '#f5c842'
            : line.type === 'error'
              ? '#ff6b35'
              : 'rgba(232,232,240,0.45)'

        return (
          <div
            key={line.id}
            style={{
              display: 'flex',
              gap: 8,
              marginBottom: 2,
              fontFamily: monoFont,
              fontSize: 9,
              lineHeight: 1.5,
            }}
          >
            <span
              style={{
                color: 'rgba(238,240,246,0.18)',
                flexShrink: 0,
              }}
            >
              {formatTimestamp(line.timestamp)}
            </span>
            <span
              style={{
                color: lineColor,
                fontStyle: line.isHmr ? 'italic' : 'normal',
                opacity: line.isHmr ? 0.6 : 1,
                wordBreak: 'break-word',
              }}
            >
              {sourceLink ? (
                <>
                  {line.message.substring(0, line.message.indexOf(sourceLink.match))}
                  <span
                    onClick={() => handleSourceClick(sourceLink.file, sourceLink.line)}
                    style={{
                      color: '#63d9ff',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      textDecorationColor: 'rgba(99,217,255,0.3)',
                    }}
                  >
                    {sourceLink.match}
                  </span>
                  {line.message.substring(
                    line.message.indexOf(sourceLink.match) + sourceLink.match.length,
                  )}
                </>
              ) : (
                line.message
              )}
            </span>
          </div>
        )
      })}
    </div>
  )

  /* ---- Network Tab ---- */
  const renderNetworkTab = () => (
    <div
      style={{
        overflowY: 'auto',
        padding: '2px 0',
        flex: 1,
        minHeight: 0,
      }}
    >
      {networkEntries.length === 0 && (
        <div
          style={{
            fontFamily: monoFont,
            fontSize: 9,
            color: 'rgba(232,232,240,0.18)',
            padding: '8px 10px',
          }}
        >
          No network activity yet
        </div>
      )}
      {/* Table header */}
      {networkEntries.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '50px 1fr 48px 60px',
            gap: 4,
            padding: '2px 10px',
            fontFamily: monoFont,
            fontSize: 8,
            color: 'rgba(232,232,240,0.20)',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}
        >
          <span>METHOD</span>
          <span>URL</span>
          <span>STATUS</span>
          <span>TIME</span>
        </div>
      )}
      {networkEntries.map((entry) => {
        const isExpanded = expandedNetworkId === entry.id
        return (
          <div key={entry.id}>
            <div
              onClick={() => setExpandedNetworkId(isExpanded ? null : entry.id)}
              style={{
                display: 'grid',
                gridTemplateColumns: '50px 1fr 48px 60px',
                gap: 4,
                padding: '3px 10px',
                fontFamily: monoFont,
                fontSize: 11,
                cursor: 'pointer',
                background: isExpanded ? 'rgba(255,255,255,0.02)' : 'transparent',
                borderBottom: '1px solid rgba(255,255,255,0.02)',
              }}
            >
              <span style={{ color: methodColor(entry.method), fontWeight: 600 }}>
                {entry.method}
              </span>
              <span
                style={{
                  color: 'rgba(232,232,240,0.45)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {entry.url}
              </span>
              <span
                style={{
                  color: entry.status !== null ? statusColor(entry.status) : 'rgba(232,232,240,0.20)',
                  fontWeight: 600,
                }}
              >
                {entry.status ?? '...'}
              </span>
              <span style={{ color: 'rgba(232,232,240,0.30)' }}>
                {entry.duration !== null ? `${entry.duration}ms` : '—'}
              </span>
            </div>

            {/* Expanded detail view */}
            {isExpanded && (
              <div
                style={{
                  padding: '6px 10px 8px 18px',
                  fontFamily: monoFont,
                  fontSize: 9,
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  background: 'rgba(255,255,255,0.015)',
                }}
              >
                {entry.requestHeaders && (
                  <div style={{ marginBottom: 4 }}>
                    <span style={{ color: 'rgba(232,232,240,0.25)', textTransform: 'uppercase', fontSize: 8, letterSpacing: 0.5 }}>
                      Request Headers
                    </span>
                    <pre
                      style={{
                        color: 'rgba(232,232,240,0.35)',
                        margin: '2px 0',
                        whiteSpace: 'pre-wrap',
                        fontSize: 9,
                        fontFamily: monoFont,
                      }}
                    >
                      {Object.entries(entry.requestHeaders)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join('\n')}
                    </pre>
                  </div>
                )}
                {entry.requestBody && (
                  <div style={{ marginBottom: 4 }}>
                    <span style={{ color: 'rgba(232,232,240,0.25)', textTransform: 'uppercase', fontSize: 8, letterSpacing: 0.5 }}>
                      Request Body
                    </span>
                    <pre
                      style={{
                        color: 'rgba(232,232,240,0.35)',
                        margin: '2px 0',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        fontSize: 9,
                        fontFamily: monoFont,
                      }}
                    >
                      {entry.requestBody}
                    </pre>
                  </div>
                )}
                {entry.responseHeaders && (
                  <div style={{ marginBottom: 4 }}>
                    <span style={{ color: 'rgba(232,232,240,0.25)', textTransform: 'uppercase', fontSize: 8, letterSpacing: 0.5 }}>
                      Response Headers
                    </span>
                    <pre
                      style={{
                        color: 'rgba(232,232,240,0.35)',
                        margin: '2px 0',
                        whiteSpace: 'pre-wrap',
                        fontSize: 9,
                        fontFamily: monoFont,
                      }}
                    >
                      {Object.entries(entry.responseHeaders)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join('\n')}
                    </pre>
                  </div>
                )}
                {entry.responseBody && (
                  <div>
                    <span style={{ color: 'rgba(232,232,240,0.25)', textTransform: 'uppercase', fontSize: 8, letterSpacing: 0.5 }}>
                      Response Body
                    </span>
                    <pre
                      style={{
                        color: 'rgba(232,232,240,0.35)',
                        margin: '2px 0',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        fontSize: 9,
                        fontFamily: monoFont,
                      }}
                    >
                      {entry.responseBody}
                    </pre>
                  </div>
                )}
                {!entry.requestHeaders && !entry.requestBody && !entry.responseHeaders && !entry.responseBody && (
                  <span style={{ color: 'rgba(232,232,240,0.18)' }}>
                    No detail data available
                  </span>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )

  /* ---- Errors Tab ---- */
  const renderErrorsTab = () => (
    <div
      style={{
        overflowY: 'auto',
        padding: '4px 10px',
        flex: 1,
        minHeight: 0,
      }}
    >
      {errorEntries.length === 0 && (
        <div
          style={{
            fontFamily: monoFont,
            fontSize: 9,
            color: 'rgba(232,232,240,0.18)',
            padding: '8px 0',
          }}
        >
          No errors 🎉
        </div>
      )}
      {errorEntries.map((err) => {
        const sourceLink = parseSourceLink(err.message)
        return (
          <div
            key={err.id}
            style={{
              background: 'rgba(255,107,53,0.04)',
              border: '1px solid rgba(255,107,53,0.12)',
              borderRadius: 6,
              padding: '6px 8px',
              marginBottom: 4,
            }}
          >
            {/* Error message */}
            <div
              style={{
                fontFamily: monoFont,
                fontSize: 9,
                color: '#ff6b35',
                lineHeight: 1.5,
                marginBottom: err.stack ? 3 : 0,
                wordBreak: 'break-word',
              }}
            >
              {sourceLink ? (
                <>
                  {err.message.substring(0, err.message.indexOf(sourceLink.match))}
                  <span
                    onClick={() => handleSourceClick(sourceLink.file, sourceLink.line)}
                    style={{
                      color: '#63d9ff',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      textDecorationColor: 'rgba(99,217,255,0.3)',
                    }}
                  >
                    {sourceLink.match}
                  </span>
                  {err.message.substring(
                    err.message.indexOf(sourceLink.match) + sourceLink.match.length,
                  )}
                </>
              ) : (
                err.message
              )}
            </div>

            {/* Stack trace */}
            {err.stack && (
              <pre
                style={{
                  fontFamily: monoFont,
                  fontSize: 9,
                  color: 'rgba(232,232,240,0.25)',
                  lineHeight: 1.5,
                  margin: '2px 0 4px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {err.stack}
              </pre>
            )}

            {/* Send to AI button */}
            <button
              id={`error-send-ai-${err.id}`}
              onClick={() => handleSendToAi(err.message, err.stack)}
              style={{
                fontFamily: monoFont,
                fontSize: 8,
                color: '#b06bff',
                background: 'rgba(176,107,255,0.08)',
                border: '1px solid rgba(176,107,255,0.18)',
                borderRadius: 4,
                padding: '2px 6px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                letterSpacing: 0.3,
              }}
            >
              Send to AI ↑
            </button>
          </div>
        )
      })}
    </div>
  )

  /* ---- Main render ---- */
  return (
    <div
      id="dev-console"
      style={{
        background: 'rgba(4,4,10,0.97)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        maxHeight: expanded ? 160 : 30,
        transition: 'max-height 200ms ease',
        overflow: 'hidden',
      }}
    >
      {renderHeader()}

      {/* Tab content (only visible when expanded) */}
      {expanded && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {activeTab === 'console' && renderConsoleTab()}
          {activeTab === 'network' && renderNetworkTab()}
          {activeTab === 'errors' && renderErrorsTab()}
        </div>
      )}
    </div>
  )
}
