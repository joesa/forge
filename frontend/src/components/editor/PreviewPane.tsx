/* ------------------------------------------------------------------ */
/*  FORGE — PreviewPane                                                */
/*  Container component for the live preview pane in the editor.       */
/*  Renders: toolbar, iframe/snapshot body, dev console, timeline.     */
/* ------------------------------------------------------------------ */

import { useCallback, useMemo, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { useAuthStore } from '@/stores/authStore'
import { usePreview } from '@/hooks/usePreview'
import PreviewToolbar from './PreviewToolbar'
import AnnotationLayer from './AnnotationLayer'
import SnapshotTimeline from './SnapshotTimeline'
import PreviewDevConsole from './PreviewDevConsole'

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

      {/* ---- Dev Console (collapsible, WebSocket-connected) ---- */}
      <PreviewDevConsole sandboxId={sandboxId} projectId={projectId} />

      {/* ---- Snapshot Timeline (38px) ---- */}
      <SnapshotTimeline
        snapshots={snapshots}
        selectedSnapshot={currentSnapshot}
        onSelectSnapshot={handleSelectSnapshot}
      />
    </div>
  )
}
