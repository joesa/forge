/* ------------------------------------------------------------------ */
/*  FORGE — PreviewToolbar                                             */
/*  38px toolbar above the preview iframe with navigation, device      */
/*  switching, screenshot, annotate, share, and error badge.           */
/* ------------------------------------------------------------------ */

import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import { useEditorStore } from '@/stores/editorStore'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PreviewToolbarProps {
  previewUrl: string | null
  onRefresh: () => void
}

interface ShareResponse {
  share_url: string
  expires_at: string
}

interface ScreenshotResponse {
  screenshot_url: string
}

/* ------------------------------------------------------------------ */
/*  Shared button style                                                */
/* ------------------------------------------------------------------ */
const navBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'rgba(232,232,240,0.40)',
  cursor: 'pointer',
  fontSize: 11,
  padding: '2px 3px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function PreviewToolbar({ previewUrl, onRefresh }: PreviewToolbarProps) {
  const previewRoute = useEditorStore((s) => s.previewRoute)
  const previewDevice = useEditorStore((s) => s.previewDevice)
  const setPreviewDevice = useEditorStore((s) => s.setPreviewDevice)
  const annotationMode = useEditorStore((s) => s.annotationMode)
  const toggleAnnotationMode = useEditorStore((s) => s.toggleAnnotationMode)
  const sandboxId = useEditorStore((s) => s.sandboxId)

  /* ---- Share popover ---- */
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [shareCopied, setShareCopied] = useState(false)
  const shareRef = useRef<HTMLDivElement>(null)
  const shareTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /* ---- Console error count (demo) ---- */
  const [errorCount] = useState(2)

  /* ---- History stacks for navigation ---- */
  const [historyBack, setHistoryBack] = useState<string[]>([])
  const [historyForward, setHistoryForward] = useState<string[]>([])

  const setPreviewRoute = useEditorStore((s) => s.setPreviewRoute)

  const handleBack = useCallback(() => {
    if (historyBack.length === 0) return
    const prev = historyBack[historyBack.length - 1]
    setHistoryBack((h) => h.slice(0, -1))
    setHistoryForward((h) => [...h, previewRoute])
    setPreviewRoute(prev)
  }, [historyBack, previewRoute, setPreviewRoute])

  const handleForward = useCallback(() => {
    if (historyForward.length === 0) return
    const next = historyForward[historyForward.length - 1]
    setHistoryForward((h) => h.slice(0, -1))
    setHistoryBack((h) => [...h, previewRoute])
    setPreviewRoute(next)
  }, [historyForward, previewRoute, setPreviewRoute])

  /* ---- Screenshot ---- */
  const handleScreenshot = useCallback(async () => {
    if (!sandboxId) return
    try {
      const res = await axios.post<ScreenshotResponse>(
        `/api/v1/sandbox/${sandboxId}/preview/screenshot`,
      )
      // Fetch as blob to support cross-origin R2 URLs
      const blobRes = await fetch(res.data.screenshot_url)
      const blob = await blobRes.blob()
      const blobUrl = URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = blobUrl
      link.download = `preview-${Date.now()}.png`
      link.click()

      // Clean up blob URL after a short delay
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000)
    } catch {
      // Silently fail — backend may not be running
    }
  }, [sandboxId])

  /* ---- Share ---- */
  const handleShare = useCallback(async () => {
    if (!sandboxId) return
    try {
      const res = await axios.post<ShareResponse>(
        `/api/v1/sandbox/${sandboxId}/preview/share`,
      )
      setShareUrl(res.data.share_url)
      setShareCopied(false)

      // Auto-dismiss after 5s
      if (shareTimerRef.current) clearTimeout(shareTimerRef.current)
      shareTimerRef.current = setTimeout(() => {
        setShareUrl(null)
      }, 5000)
    } catch {
      // Silently fail
    }
  }, [sandboxId])

  const handleCopyShare = useCallback(async () => {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShareCopied(true)
    } catch {
      // Clipboard API may not be available
    }
  }, [shareUrl])

  /* ---- Outside click to dismiss share popover ---- */
  useEffect(() => {
    if (!shareUrl) return

    const handleClickOutside = (e: MouseEvent) => {
      if (shareRef.current && !shareRef.current.contains(e.target as Node)) {
        setShareUrl(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [shareUrl])

  /* ---- Cleanup share timer ---- */
  useEffect(() => {
    return () => {
      if (shareTimerRef.current) clearTimeout(shareTimerRef.current)
    }
  }, [])

  /* ---- Device button helper ---- */
  const deviceBtn = (device: 'mobile' | 'tablet' | 'desktop', icon: string): React.ReactElement => {
    const isActive = previewDevice === device
    return (
      <button
        id={`preview-device-${device}`}
        onClick={() => setPreviewDevice(device)}
        style={{
          background: isActive ? 'rgba(99,217,255,0.08)' : 'none',
          border: isActive ? '1px solid rgba(99,217,255,0.22)' : '1px solid transparent',
          color: isActive ? '#63d9ff' : 'rgba(232,232,240,0.40)',
          cursor: 'pointer',
          fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
          padding: '2px 5px',
          borderRadius: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        {icon}
      </button>
    )
  }

  /* ---- Render ---- */
  return (
    <div
      id="preview-toolbar"
      style={{
        height: 38,
        background: 'rgba(4,4,10,0.95)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px',
        gap: 5,
        flexShrink: 0,
        position: 'relative',
      }}
    >
      {/* Navigation arrows */}
      <button
        id="preview-nav-back"
        onClick={handleBack}
        style={{
          ...navBtnStyle,
          opacity: historyBack.length > 0 ? 1 : 0.3,
        }}
        disabled={historyBack.length === 0}
      >
        ←
      </button>
      <button
        id="preview-nav-forward"
        onClick={handleForward}
        style={{
          ...navBtnStyle,
          opacity: historyForward.length > 0 ? 1 : 0.3,
        }}
        disabled={historyForward.length === 0}
      >
        →
      </button>

      {/* URL bar */}
      <div
        id="preview-url-bar"
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
          textOverflow: 'ellipsis',
          minWidth: 0,
        }}
      >
        {previewUrl
          ? (() => {
              try {
                return `${new URL(previewUrl).host}${previewRoute}`
              } catch {
                return previewUrl + previewRoute
              }
            })()
          : 'loading...'}
      </div>

      {/* Device buttons */}
      {deviceBtn('mobile', '📱')}
      {deviceBtn('tablet', '💻')}
      {deviceBtn('desktop', '🖥️')}

      {/* Separator dot */}
      <div
        style={{
          width: 1,
          height: 14,
          background: 'rgba(255,255,255,0.06)',
          flexShrink: 0,
        }}
      />

      {/* Action buttons */}
      <button
        id="preview-refresh"
        onClick={onRefresh}
        style={navBtnStyle}
        title="Refresh"
      >
        ↺
      </button>

      <button
        id="preview-screenshot"
        onClick={() => void handleScreenshot()}
        style={navBtnStyle}
        title="Screenshot"
      >
        📷
      </button>

      <button
        id="preview-annotate"
        onClick={toggleAnnotationMode}
        style={{
          ...navBtnStyle,
          color: annotationMode ? '#ff6b35' : 'rgba(232,232,240,0.40)',
          background: annotationMode ? 'rgba(255,107,53,0.12)' : 'none',
          borderRadius: 3,
          padding: '2px 4px',
        }}
        title="Annotate"
      >
        ✏️
      </button>

      <button
        id="preview-share"
        onClick={() => void handleShare()}
        style={navBtnStyle}
        title="Share"
      >
        🔗
      </button>

      {/* Error badge */}
      {errorCount > 0 && (
        <span
          id="preview-error-badge"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: '#ff6b35',
            flexShrink: 0,
          }}
        >
          ● {errorCount}
        </span>
      )}

      {/* Share popover */}
      {shareUrl && (
        <div
          ref={shareRef}
          id="share-popover"
          style={{
            position: 'absolute',
            top: 42,
            right: 10,
            zIndex: 200,
            background: '#0d0d1f',
            border: '1px solid rgba(99,217,255,0.22)',
            borderRadius: 10,
            padding: '14px 16px',
            width: 260,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: 'rgba(232,232,240,0.35)',
              letterSpacing: 1,
              textTransform: 'uppercase',
              marginBottom: 8,
            }}
          >
            Share Preview
          </div>
          <div
            onClick={() => void handleCopyShare()}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: '#63d9ff',
              background: 'rgba(99,217,255,0.06)',
              border: '1px solid rgba(99,217,255,0.18)',
              borderRadius: 5,
              padding: '6px 8px',
              cursor: 'pointer',
              wordBreak: 'break-all',
              marginBottom: 6,
            }}
          >
            {shareUrl}
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: shareCopied ? '#3dffa0' : 'rgba(232,232,240,0.30)',
            }}
          >
            {shareCopied ? '✓ Copied!' : 'Click to copy'} · Expires in 24h
          </div>
        </div>
      )}
    </div>
  )
}
