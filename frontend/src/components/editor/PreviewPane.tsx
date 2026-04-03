/* ------------------------------------------------------------------ */
/*  FORGE — PreviewPane                                                */
/*  Container component for the live preview pane in the editor.       */
/*  Renders: toolbar, iframe/snapshot body, dev console, timeline.     */
/* ------------------------------------------------------------------ */

import { useState, useCallback, useMemo, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { useAuthStore } from '@/stores/authStore'
import { usePreview } from '@/hooks/usePreview'
import PreviewToolbar from './PreviewToolbar'
import AnnotationLayer from './AnnotationLayer'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ConsoleEntry {
  time: string
  type: 'log' | 'warn' | 'error'
  msg: string
}

/* ------------------------------------------------------------------ */
/*  Demo data                                                          */
/* ------------------------------------------------------------------ */

const demoConsoleLines: ConsoleEntry[] = [
  { time: '14:32:01', type: 'log', msg: '[HMR] Updated modules: dashboard/page.tsx' },
  { time: '14:31:58', type: 'log', msg: 'GET /api/stats 200 OK (12ms)' },
  { time: '14:31:55', type: 'warn', msg: 'React: Missing key prop in ProjectCard list' },
  { time: '14:31:42', type: 'log', msg: '[build] Compiled successfully (340ms)' },
]

/* ------------------------------------------------------------------ */
/*  Shimmer skeleton                                                   */
/* ------------------------------------------------------------------ */

function PreviewSkeleton() {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: 'rgba(255,255,255,0.04)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '-100%',
          width: '200%',
          height: '100%',
          background:
            'linear-gradient(90deg, transparent 0%, rgba(99,217,255,0.04) 50%, transparent 100%)',
          animation: 'shimmer 1.5s ease-in-out infinite',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 8, opacity: 0.15 }}>⬡</div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(232,232,240,0.25)',
            letterSpacing: 2,
            textTransform: 'uppercase',
          }}
        >
          LOADING PREVIEW...
        </div>
      </div>
    </div>
  )
}

/* AnnotationDot moved to AnnotationLayer component */

/* ------------------------------------------------------------------ */
/*  Main PreviewPane Component                                         */
/* ------------------------------------------------------------------ */

export default function PreviewPane() {
  const projectId = useEditorStore((s) => s.projectId)
  const sandboxId = useEditorStore((s) => s.sandboxId)
  const previewRoute = useEditorStore((s) => s.previewRoute)
  const previewDevice = useEditorStore((s) => s.previewDevice)
  const annotationMode = useEditorStore((s) => s.annotationMode)
  const annotations = useEditorStore((s) => s.annotations)
  const snapshots = useEditorStore((s) => s.snapshots)
  const storeSelectedSnapshot = useEditorStore((s) => s.selectedSnapshot)
  const storeSelectSnapshot = useEditorStore((s) => s.selectSnapshot)

  const tokens = useAuthStore((s) => s.tokens)

  const {
    previewUrl,
    isLoading,
    hmrFlash,
    refreshPreview,
    iframeRef,
    selectedSnapshot: hookSnapshot,
    selectSnapshot: hookSelectSnapshot,
  } = usePreview(sandboxId)

  /* Sync snapshot from editorStore to hook — editorStore is source of truth */
  const currentSnapshot = storeSelectedSnapshot ?? hookSnapshot
  const handleSelectSnapshot = useCallback(
    (snapshot: typeof currentSnapshot) => {
      storeSelectSnapshot(snapshot)
      hookSelectSnapshot(snapshot)
    },
    [storeSelectSnapshot, hookSelectSnapshot],
  )

  /* ---- Console state ---- */
  const [consoleTab, setConsoleTab] = useState<'console' | 'network' | 'errors'>('console')
  const [consoleExpanded, setConsoleExpanded] = useState(true)

  /* ---- Set auth cookie for iframe domain ---- */
  useEffect(() => {
    if (!tokens?.accessToken || !previewUrl) return

    // Only set cookie when preview URL is on the .preview.forge.dev domain
    try {
      const url = new URL(previewUrl)
      if (url.hostname.endsWith('.preview.forge.dev')) {
        document.cookie = `forge_access_token=${tokens.accessToken}; domain=.preview.forge.dev; path=/; SameSite=None; Secure`
      }
    } catch {
      // Invalid URL or cookie setting failed — skip silently
    }
  }, [tokens, previewUrl])

  /* ---- Annotation click handling is now delegated to AnnotationLayer ---- */

  /* ---- Iframe src ---- */
  const iframeSrc = useMemo(() => {
    if (!previewUrl) return undefined
    return `${previewUrl}${previewRoute}`
  }, [previewUrl, previewRoute])

  /* ---- Iframe width based on device ---- */
  const iframeWidth = useMemo(() => {
    switch (previewDevice) {
      case 'mobile':
        return 375
      case 'tablet':
        return 768
      case 'desktop':
      default:
        return '100%'
    }
  }, [previewDevice])

  /* ---- Route annotations (filter by current route) ---- */
  const routeAnnotations = useMemo(
    () => annotations.filter((a) => !a.route || a.route === previewRoute),
    [annotations, previewRoute],
  )

  /* Suppress unused variable warning — routeAnnotations used by AnnotationLayer */
  void routeAnnotations

  return (
    <div
      id="preview-pane"
      style={{
        borderLeft: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        height: '100%',
        minHeight: 0,
      }}
    >
      {/* ---- Toolbar (38px) ---- */}
      <PreviewToolbar
        previewUrl={previewUrl}
        onRefresh={refreshPreview}
      />

      {/* ---- Preview Body (flex: 1) ---- */}
      <div
        id="preview-body"
        style={{
          flex: 1,
          background: '#04040a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
          opacity: hmrFlash ? 0.6 : 1,
          transition: 'opacity 100ms ease',
        }}
      >
        {/* Loading skeleton */}
        {isLoading && <PreviewSkeleton />}

        {/* Snapshot view */}
        {!isLoading && currentSnapshot && (
          <img
            src={currentSnapshot.image_url}
            alt={`Build snapshot at agent ${currentSnapshot.agent_index}`}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
          />
        )}

        {/* Live iframe */}
        {!isLoading && !currentSnapshot && iframeSrc && (
          <iframe
            ref={iframeRef}
            id="preview-iframe"
            src={iframeSrc}
            title="App Preview"
            style={{
              width: iframeWidth,
              height: '100%',
              border: 'none',
              background: '#fff',
              margin: '0 auto',
              display: 'block',
              transition: 'width 200ms ease',
            }}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
          />
        )}

        {/* No preview URL fallback */}
        {!isLoading && !currentSnapshot && !iframeSrc && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 36, marginBottom: 8, opacity: 0.15 }}>⬡</div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: 'rgba(232,232,240,0.25)',
                letterSpacing: 2,
                textTransform: 'uppercase',
              }}
            >
              NO PREVIEW AVAILABLE
            </div>
          </div>
        )}

        {/* Annotation Layer — handles dots, click-to-annotate, popovers */}
        {!currentSnapshot && projectId && sandboxId && (
          <AnnotationLayer
            projectId={projectId}
            sandboxId={sandboxId}
            annotations={annotations.filter((a) => !a.route || a.route === previewRoute)}
            annotationMode={annotationMode}
          />
        )}
      </div>

      {/* ---- Dev Console (collapsible) ---- */}
      {consoleExpanded && (
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
          {/* Console tab bar */}
          <div
            style={{
              display: 'flex',
              gap: 2,
              padding: '6px 10px 0',
              alignItems: 'center',
            }}
          >
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
                  border:
                    consoleTab === tab
                      ? '1px solid rgba(99,217,255,0.25)'
                      : '1px solid transparent',
                  color: consoleTab === tab ? '#63d9ff' : 'rgba(232,232,240,0.35)',
                  background:
                    consoleTab === tab ? 'rgba(99,217,255,0.08)' : 'transparent',
                  textTransform: 'capitalize',
                }}
              >
                {tab}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            <button
              onClick={() => setConsoleExpanded(false)}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(232,232,240,0.25)',
                cursor: 'pointer',
                fontSize: 9,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              ✕
            </button>
          </div>

          {/* Console lines */}
          <div
            style={{
              padding: '4px 10px',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              overflowY: 'auto',
              maxHeight: 70,
            }}
          >
            {demoConsoleLines.map((l, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, padding: '1px 0' }}>
                <span style={{ color: 'rgba(232,232,240,0.16)', flexShrink: 0 }}>
                  {l.time}
                </span>
                <span
                  style={{
                    color:
                      l.type === 'warn'
                        ? '#f5c842'
                        : l.type === 'error'
                          ? '#ff6b35'
                          : 'rgba(232,232,240,0.45)',
                  }}
                >
                  {l.msg}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Console re-open button when collapsed */}
      {!consoleExpanded && (
        <div
          style={{
            borderTop: '1px solid rgba(255,255,255,0.06)',
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => setConsoleExpanded(true)}
            style={{
              width: '100%',
              background: 'rgba(4,4,10,0.97)',
              border: 'none',
              padding: '3px 10px',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color: 'rgba(232,232,240,0.30)',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            ▸ Console
          </button>
        </div>
      )}

      {/* ---- Snapshot Timeline (38px) ---- */}
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
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 7,
            color: 'rgba(232,232,240,0.30)',
            flexShrink: 0,
          }}
        >
          BUILD
        </span>

        {/* Track */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
          {Array.from({ length: 10 }, (_, i) => {
            const snapshot = snapshots[i] ?? null
            const isDone = snapshot !== null
            const isSelected = currentSnapshot?.id === snapshot?.id

            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < 9 ? 1 : undefined }}>
                <div
                  onClick={() => {
                    if (snapshot) handleSelectSnapshot(snapshot)
                  }}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: isDone
                      ? isSelected
                        ? '#63d9ff'
                        : '#3dffa0'
                      : 'rgba(232,232,240,0.15)',
                    flexShrink: 0,
                    cursor: isDone ? 'pointer' : 'default',
                    boxShadow: isSelected
                      ? '0 0 6px rgba(99,217,255,0.5)'
                      : 'none',
                    transition: 'all 0.15s',
                  }}
                />
                {i < 9 && (
                  <div
                    style={{
                      flex: 1,
                      height: 1,
                      background: 'rgba(255,255,255,0.07)',
                      minWidth: 4,
                    }}
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* LIVE dot */}
        <div
          onClick={() => handleSelectSnapshot(null)}
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#3dffa0',
            animation: 'jade-pulse 2s ease-in-out infinite',
            cursor: 'pointer',
            marginLeft: 4,
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 7,
            color: currentSnapshot ? 'rgba(232,232,240,0.30)' : '#3dffa0',
            flexShrink: 0,
            cursor: 'pointer',
          }}
          onClick={() => handleSelectSnapshot(null)}
        >
          {currentSnapshot
            ? `After Agent ${currentSnapshot.agent_index}`
            : '● LIVE'}
        </span>
      </div>
    </div>
  )
}
