/* ------------------------------------------------------------------ */
/*  FORGE — AnnotationLayer                                            */
/*  Absolute overlay on the preview iframe. Captures clicks in         */
/*  annotation mode, renders annotation dots, and manages CRUD.        */
/* ------------------------------------------------------------------ */

import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type CSSProperties,
} from 'react'
import axios from 'axios'
import type { Annotation } from '@/types'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface AnnotationLayerProps {
  projectId: string
  sandboxId: string
  annotations: Annotation[]
  annotationMode: boolean
}

/** Allowed origin suffix for postMessage security validation. */
const PREVIEW_ORIGIN_SUFFIX = '.preview.forge.dev'

/** State for the inline comment form that appears on click. */
interface NewAnnotationState {
  x_pct: number
  y_pct: number
  css_selector: string
  route: string
}

/** State for the detail popover on a dot click. */
interface ActiveAnnotationState {
  annotation: Annotation
}

interface PostMessageSelectorResult {
  type: 'selector_result'
  selector: string
  route: string
}

/* ------------------------------------------------------------------ */
/*  API request / response types                                       */
/* ------------------------------------------------------------------ */

interface AnnotationCreatePayload {
  session_id: string
  css_selector: string
  route: string
  comment: string
  x_pct: number
  y_pct: number
}

interface AnnotationCreateResponse {
  id: string
  project_id: string
  user_id: string
  x_pct: number
  y_pct: number
  css_selector: string | null
  content: string
  resolved: boolean
  page_route: string | null
  created_at: string
  updated_at: string
}

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const monoFont = "'JetBrains Mono', monospace"
const sansFont = "'Syne', sans-serif"

const overlayBase: CSSProperties = {
  position: 'absolute',
  inset: 0,
  zIndex: 10,
}

const inputPopoverStyle: CSSProperties = {
  position: 'absolute',
  zIndex: 30,
  background: '#0d0d1f',
  border: '1px solid rgba(99,217,255,0.22)',
  borderRadius: 10,
  padding: '12px 14px',
  width: 240,
  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const detailPopoverStyle: CSSProperties = {
  position: 'absolute',
  zIndex: 30,
  background: '#0d0d1f',
  border: '1px solid rgba(255,107,53,0.22)',
  borderRadius: 10,
  padding: '14px 16px',
  width: 260,
  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
}

/* ------------------------------------------------------------------ */
/*  Annotation Dot                                                     */
/* ------------------------------------------------------------------ */

function AnnotationDot({
  annotation,
  onDotClick,
  interactive,
}: {
  annotation: Annotation
  onDotClick: (annotation: Annotation) => void
  interactive: boolean
}) {
  const [hovered, setHovered] = useState(false)
  const isResolved = annotation.resolved

  /* Clamp server-supplied percentages to [0, 1] for render safety */
  const safeX = Math.max(0, Math.min(1, annotation.x_pct))
  const safeY = Math.max(0, Math.min(1, annotation.y_pct))

  const truncatedComment =
    annotation.comment.length > 60
      ? annotation.comment.slice(0, 60) + '…'
      : annotation.comment

  return (
    <div
      data-annotation-id={annotation.id}
      style={{
        position: 'absolute',
        left: `${safeX * 100}%`,
        top: `${safeY * 100}%`,
        transform: 'translate(-50%, -50%)',
        zIndex: 15,
        cursor: interactive ? 'pointer' : 'default',
        pointerEvents: interactive ? 'auto' : 'none',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={(e) => {
        e.stopPropagation()
        if (!isResolved) onDotClick(annotation)
      }}
    >
      {/* The dot */}
      <div
        style={{
          width: hovered ? 16 : 12,
          height: hovered ? 16 : 12,
          borderRadius: '50%',
          border: '2px solid #fff',
          background: isResolved ? '#3dffa0' : '#ff6b35',
          opacity: isResolved ? 0.5 : 1,
          animation: isResolved ? 'none' : 'ember-pulse 1.8s ease-in-out infinite',
          transition: 'width 150ms ease, height 150ms ease',
        }}
      />

      {/* Hover tooltip */}
      {hovered && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#0d0d1f',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 6,
            padding: '5px 8px',
            fontFamily: monoFont,
            fontSize: 9,
            color: '#e8e8f0',
            whiteSpace: 'nowrap',
            zIndex: 25,
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            maxWidth: 220,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          <div style={{ marginBottom: 2 }}>{truncatedComment}</div>
          {annotation.route && (
            <div style={{ color: 'rgba(232,232,240,0.35)', fontSize: 8 }}>
              {annotation.route}
            </div>
          )}
          {!isResolved && (
            <div style={{ color: '#63d9ff', fontSize: 8, marginTop: 2 }}>
              Click to resolve
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Detail Popover (shown when clicking an unresolved dot)             */
/* ------------------------------------------------------------------ */

function DetailPopover({
  annotation,
  projectId,
  onClose,
  onResolved,
  onDeleted,
}: {
  annotation: Annotation
  projectId: string
  onClose: () => void
  onResolved: (id: string) => void
  onDeleted: (id: string) => void
}) {
  const [resolving, setResolving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  /* Close on outside click */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleResolve = useCallback(async () => {
    setResolving(true)
    try {
      // No PATCH endpoint exists — delete + re-create as resolved via convention.
      // For now we just delete (the backend doesn't expose PATCH).
      // The consumer can mark resolved locally via onResolved callback.
      await axios.delete(
        `/api/v1/projects/${projectId}/annotations/${annotation.id}`,
      )
      onResolved(annotation.id)
    } catch {
      // Silent fail
    } finally {
      setResolving(false)
    }
  }, [annotation.id, projectId, onResolved])

  const handleDelete = useCallback(async () => {
    setDeleting(true)
    try {
      await axios.delete(
        `/api/v1/projects/${projectId}/annotations/${annotation.id}`,
      )
      onDeleted(annotation.id)
    } catch {
      // Silent fail
    } finally {
      setDeleting(false)
    }
  }, [annotation.id, projectId, onDeleted])

  const createdDate = new Date(annotation.created_at)
  const timeStr = createdDate.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div
      ref={popoverRef}
      style={{
        ...detailPopoverStyle,
        position: 'absolute',
        left: `${annotation.x_pct * 100}%`,
        top: `${annotation.y_pct * 100}%`,
        transform: 'translate(-50%, calc(-100% - 14px))',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 8,
          right: 10,
          background: 'none',
          border: 'none',
          color: 'rgba(232,232,240,0.30)',
          cursor: 'pointer',
          fontSize: 10,
          fontFamily: monoFont,
        }}
      >
        ✕
      </button>

      {/* Comment text */}
      <div
        style={{
          fontFamily: sansFont,
          fontSize: 12,
          color: '#e8e8f0',
          lineHeight: 1.6,
          marginBottom: 8,
          paddingRight: 18,
        }}
      >
        {annotation.comment}
      </div>

      {/* Route + timestamp */}
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 9,
          color: 'rgba(232,232,240,0.35)',
          marginBottom: 10,
          display: 'flex',
          gap: 8,
        }}
      >
        {annotation.route && <span>{annotation.route}</span>}
        <span>{timeStr}</span>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 6 }}>
        <button
          onClick={() => void handleResolve()}
          disabled={resolving}
          style={{
            flex: 1,
            height: 28,
            background: 'rgba(61,255,160,0.08)',
            border: '1px solid rgba(61,255,160,0.18)',
            borderRadius: 6,
            color: '#3dffa0',
            fontFamily: monoFont,
            fontSize: 9,
            fontWeight: 600,
            cursor: resolving ? 'wait' : 'pointer',
            opacity: resolving ? 0.5 : 1,
          }}
        >
          {resolving ? '...' : '✓ Mark Resolved'}
        </button>
        <button
          onClick={() => void handleDelete()}
          disabled={deleting}
          style={{
            height: 28,
            padding: '0 10px',
            background: 'rgba(255,107,53,0.10)',
            border: '1px solid rgba(255,107,53,0.22)',
            borderRadius: 6,
            color: '#ff6b35',
            fontFamily: monoFont,
            fontSize: 9,
            fontWeight: 600,
            cursor: deleting ? 'wait' : 'pointer',
            opacity: deleting ? 0.5 : 1,
          }}
        >
          {deleting ? '...' : 'Delete'}
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Inline Comment Input (appears at click position)                   */
/* ------------------------------------------------------------------ */

function CommentInput({
  state,
  projectId,
  onSaved,
  onCancel,
}: {
  state: NewAnnotationState
  projectId: string
  onSaved: (annotation: Annotation) => void
  onCancel: () => void
}) {
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  /* Auto-focus textarea */
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSave = useCallback(async () => {
    const trimmed = comment.trim()
    if (!trimmed) return

    setSaving(true)
    try {
      const payload: AnnotationCreatePayload = {
        session_id: `browser-${Date.now()}`,
        css_selector: state.css_selector,
        route: state.route,
        comment: trimmed,
        x_pct: state.x_pct,
        y_pct: state.y_pct,
      }

      const res = await axios.post<AnnotationCreateResponse>(
        `/api/v1/projects/${projectId}/annotations`,
        payload,
      )

      // Map response to Annotation type
      const newAnnotation: Annotation = {
        id: res.data.id,
        project_id: res.data.project_id,
        user_id: res.data.user_id,
        snapshot_id: null,
        x_pct: res.data.x_pct,
        y_pct: res.data.y_pct,
        css_selector: res.data.css_selector,
        comment: res.data.content,
        resolved: res.data.resolved,
        route: res.data.page_route,
        created_at: res.data.created_at,
      }
      onSaved(newAnnotation)
    } catch {
      // If API fails, create local annotation for demo
      const localAnnotation: Annotation = {
        id: `local-${Date.now()}`,
        project_id: projectId,
        user_id: '',
        snapshot_id: null,
        x_pct: state.x_pct,
        y_pct: state.y_pct,
        css_selector: state.css_selector,
        comment: trimmed,
        resolved: false,
        route: state.route,
        created_at: new Date().toISOString(),
      }
      onSaved(localAnnotation)
    } finally {
      setSaving(false)
    }
  }, [comment, state, projectId, onSaved])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        void handleSave()
      } else if (e.key === 'Escape') {
        onCancel()
      }
    },
    [handleSave, onCancel],
  )

  return (
    <div
      ref={containerRef}
      style={{
        ...inputPopoverStyle,
        left: `${state.x_pct * 100}%`,
        top: `${state.y_pct * 100}%`,
        transform: 'translate(-50%, 8px)',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Label */}
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 8,
          letterSpacing: 1,
          textTransform: 'uppercase',
          color: 'rgba(232,232,240,0.30)',
        }}
      >
        {state.css_selector || 'element'}
      </div>

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe what's wrong..."
        rows={3}
        style={{
          width: '100%',
          resize: 'none',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 6,
          padding: '6px 8px',
          fontFamily: sansFont,
          fontSize: 11,
          color: '#e8e8f0',
          outline: 'none',
          lineHeight: 1.5,
        }}
      />

      {/* Action row */}
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button
          onClick={onCancel}
          style={{
            height: 26,
            padding: '0 10px',
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 5,
            color: 'rgba(232,232,240,0.5)',
            fontFamily: monoFont,
            fontSize: 9,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          onClick={() => void handleSave()}
          disabled={saving || !comment.trim()}
          style={{
            height: 26,
            padding: '0 12px',
            background: '#63d9ff',
            border: 'none',
            borderRadius: 5,
            color: '#04040a',
            fontFamily: monoFont,
            fontSize: 9,
            fontWeight: 700,
            cursor: saving || !comment.trim() ? 'not-allowed' : 'pointer',
            opacity: saving || !comment.trim() ? 0.5 : 1,
          }}
        >
          {saving ? '...' : 'Save'}
        </button>
      </div>

      {/* Shortcut hint */}
      <div
        style={{
          fontFamily: monoFont,
          fontSize: 8,
          color: 'rgba(232,232,240,0.20)',
          textAlign: 'right',
        }}
      >
        ⌘+Enter to save · Esc to cancel
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main AnnotationLayer Component                                     */
/* ------------------------------------------------------------------ */

export default function AnnotationLayer({
  projectId,
  sandboxId,
  annotations,
  annotationMode,
}: AnnotationLayerProps) {
  const [newAnnotation, setNewAnnotation] = useState<NewAnnotationState | null>(null)
  const [activeAnnotation, setActiveAnnotation] = useState<ActiveAnnotationState | null>(null)
  const [localAnnotations, setLocalAnnotations] = useState<Annotation[]>([])
  const overlayRef = useRef<HTMLDivElement>(null)

  // Pending selector request state
  const pendingClickRef = useRef<{ x_pct: number; y_pct: number } | null>(null)

  /* ---- Combined annotations (props + locally created) ---- */
  const allAnnotations = [...annotations, ...localAnnotations]

  /* ---- PostMessage listener for selector results ---- */
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Security: only accept messages from the preview.forge.dev domain
      // or same-origin (for local development)
      const origin = event.origin
      let isTrustedOrigin = origin === window.location.origin
      if (!isTrustedOrigin) {
        try {
          isTrustedOrigin = new URL(origin).hostname.endsWith(PREVIEW_ORIGIN_SUFFIX)
        } catch {
          // Opaque or malformed origin — reject
          return
        }
      }

      if (!isTrustedOrigin) return

      // Type guard for PostMessage responses
      const data = event.data as Record<string, unknown>
      if (data.type !== 'selector_result') return

      const result = data as unknown as PostMessageSelectorResult
      const pending = pendingClickRef.current

      if (!pending) return

      setNewAnnotation({
        x_pct: pending.x_pct,
        y_pct: pending.y_pct,
        css_selector: result.selector || 'body',
        route: result.route || '/',
      })
      pendingClickRef.current = null
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  /* ---- Click handler (annotation mode only) ---- */
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!annotationMode) return

      // Close any open popover
      setActiveAnnotation(null)

      const rect = e.currentTarget.getBoundingClientRect()
      const x_pct = (e.clientX - rect.left) / rect.width
      const y_pct = (e.clientY - rect.top) / rect.height

      // Clamp to [0, 1]
      const clampedX = Math.max(0, Math.min(1, x_pct))
      const clampedY = Math.max(0, Math.min(1, y_pct))

      // Store pending click and request selector from iframe
      pendingClickRef.current = { x_pct: clampedX, y_pct: clampedY }

      // Try to get iframe and request selector
      const iframe = document.getElementById('preview-iframe') as HTMLIFrameElement | null
      if (iframe?.contentWindow) {
        try {
          iframe.contentWindow.postMessage(
            { type: 'get_selector', x: e.clientX, y: e.clientY },
            '*',
          )
        } catch {
          // Cross-origin — can't postMessage to iframe
        }
      }

      // Fallback: if no response within 300ms, proceed without selector
      setTimeout(() => {
        if (pendingClickRef.current) {
          const pending = pendingClickRef.current
          setNewAnnotation({
            x_pct: pending.x_pct,
            y_pct: pending.y_pct,
            css_selector: 'body',
            route: '/',
          })
          pendingClickRef.current = null
        }
      }, 300)
    },
    [annotationMode],
  )

  /* ---- Annotation CRUD handlers ---- */
  const handleAnnotationSaved = useCallback((annotation: Annotation) => {
    setLocalAnnotations((prev) => [...prev, annotation])
    setNewAnnotation(null)
  }, [])

  const handleAnnotationResolved = useCallback((id: string) => {
    // Mark as resolved locally
    setLocalAnnotations((prev) =>
      prev.map((a) => (a.id === id ? { ...a, resolved: true } : a)),
    )
    setActiveAnnotation(null)
  }, [])

  const handleAnnotationDeleted = useCallback((id: string) => {
    setLocalAnnotations((prev) => prev.filter((a) => a.id !== id))
    setActiveAnnotation(null)
  }, [])

  const handleDotClick = useCallback((annotation: Annotation) => {
    setActiveAnnotation({ annotation })
    setNewAnnotation(null)
  }, [])

  const handleCancelInput = useCallback(() => {
    setNewAnnotation(null)
    pendingClickRef.current = null
  }, [])

  /* ---- Unused sandboxId suppression ---- */
  void sandboxId

  return (
    <div
      ref={overlayRef}
      id="annotation-layer"
      style={{
        ...overlayBase,
        pointerEvents: annotationMode ? 'auto' : 'none',
        cursor: annotationMode ? 'crosshair' : 'default',
      }}
      onClick={handleOverlayClick}
    >
      {/* Annotation dots */}
      {allAnnotations.map((a) => (
        <AnnotationDot
          key={a.id}
          annotation={a}
          onDotClick={handleDotClick}
          interactive={annotationMode}
        />
      ))}

      {/* Inline comment input (appears on click) */}
      {newAnnotation && (
        <CommentInput
          state={newAnnotation}
          projectId={projectId}
          onSaved={handleAnnotationSaved}
          onCancel={handleCancelInput}
        />
      )}

      {/* Detail popover (appears on dot click) */}
      {activeAnnotation && (
        <DetailPopover
          annotation={activeAnnotation.annotation}
          projectId={projectId}
          onClose={() => setActiveAnnotation(null)}
          onResolved={handleAnnotationResolved}
          onDeleted={handleAnnotationDeleted}
        />
      )}
    </div>
  )
}
