/* ------------------------------------------------------------------ */
/*  FORGE — usePreview Hook                                            */
/*  Manages preview pane state: URL fetching, health polling,          */
/*  snapshot display, and HMR update signaling via opacity flash.      */
/* ------------------------------------------------------------------ */

import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import type { BuildSnapshot } from '@/types'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PreviewUrlResponse {
  url: string
}

interface PreviewHealthResponse {
  healthy: boolean
}

interface UsePreviewReturn {
  previewUrl: string | null
  isHealthy: boolean
  isLoading: boolean
  selectedSnapshot: BuildSnapshot | null
  selectSnapshot: (snapshot: BuildSnapshot | null) => void
  hmrFlash: boolean
  refreshPreview: () => void
  iframeRef: React.RefObject<HTMLIFrameElement | null>
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const HEALTH_POLL_INTERVAL = 30_000 // 30 seconds
const HMR_FLASH_DURATION = 100       // 100ms opacity flash

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function usePreview(sandboxId: string | null): UsePreviewReturn {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isHealthy, setIsHealthy] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<BuildSnapshot | null>(null)
  const [hmrFlash, setHmrFlash] = useState(false)

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const healthTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Derive isLoading: loading when we have a sandboxId but URL hasn't resolved yet
  const isLoading = sandboxId !== null && previewUrl === null

  /* ---- Fetch preview URL ---- */
  useEffect(() => {
    if (!sandboxId) return

    let cancelled = false

    const fetchUrl = async () => {
      try {
        const res = await axios.get<PreviewUrlResponse>(
          `/api/v1/sandbox/${sandboxId}/preview-url`,
        )
        if (!cancelled) {
          setPreviewUrl(res.data.url)
        }
      } catch {
        if (!cancelled) {
          // Fallback: construct URL from sandbox ID for dev mode
          setPreviewUrl(`https://${sandboxId}.preview.forge.dev`)
        }
      }
    }

    void fetchUrl()

    return () => {
      cancelled = true
    }
  }, [sandboxId])

  /* ---- Health polling ---- */
  useEffect(() => {
    if (!sandboxId) return

    const checkHealth = async () => {
      try {
        const res = await axios.get<PreviewHealthResponse>(
          `/api/v1/sandbox/${sandboxId}/preview/health`,
        )
        setIsHealthy(res.data.healthy)
      } catch {
        setIsHealthy(false)
      }
    }

    // Initial check
    void checkHealth()

    // Poll every 30s
    healthTimerRef.current = setInterval(() => {
      void checkHealth()
    }, HEALTH_POLL_INTERVAL)

    return () => {
      if (healthTimerRef.current) {
        clearInterval(healthTimerRef.current)
        healthTimerRef.current = null
      }
    }
  }, [sandboxId])

  /* ---- HMR WebSocket listener ---- */
  useEffect(() => {
    if (!sandboxId || !previewUrl) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    let cancelled = false
    let flashTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (cancelled) return

      let ws: WebSocket | null = null

      try {
        ws = new WebSocket(
          `${protocol}//${window.location.host}/api/v1/sandbox/${sandboxId}/hmr`,
        )

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data as string) as { type: string }
            if (data.type === 'hmr_update' || data.type === 'reload') {
              // Trigger flash
              setHmrFlash(true)
              if (flashTimer) clearTimeout(flashTimer)
              flashTimer = setTimeout(() => setHmrFlash(false), HMR_FLASH_DURATION)

              // Reload iframe
              if (iframeRef.current) {
                iframeRef.current.contentWindow?.location.reload()
              }
            }
          } catch {
            // Ignore malformed messages
          }
        }

        ws.onclose = () => {
          wsRef.current = null
          if (!cancelled) {
            // Reconnect after 5s if still mounted
            reconnectTimer = setTimeout(connect, 5000)
          }
        }

        wsRef.current = ws
      } catch {
        // WebSocket not available — degrade gracefully
      }
    }

    connect()

    return () => {
      cancelled = true
      if (flashTimer) clearTimeout(flashTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [sandboxId, previewUrl])

  /* ---- Snapshot selection ---- */
  const selectSnapshot = useCallback((snapshot: BuildSnapshot | null) => {
    setSelectedSnapshot(snapshot)
  }, [])

  /* ---- Refresh ---- */
  const refreshPreview = useCallback(() => {
    if (iframeRef.current) {
      iframeRef.current.contentWindow?.location.reload()
    }
  }, [])

  return {
    previewUrl,
    isHealthy,
    isLoading,
    selectedSnapshot,
    selectSnapshot,
    hmrFlash,
    refreshPreview,
    iframeRef,
  }
}
