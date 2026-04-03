/**
 * Toast notification system.
 *
 * Position: fixed top-right, 16px from edge, z-index: 9999
 * Width: 360px, auto-dismiss after 4s, hover pauses timer.
 * Colors: jade (success), ember (error), forge (info)
 */

import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react'
import { create } from 'zustand'

/* ── Types ────────────────────────────────────────────────────────── */

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: string
  type: ToastType
  message: string
  duration: number
}

interface ToastStore {
  toasts: ToastItem[]
  add: (type: ToastType, message: string, duration?: number) => void
  remove: (id: string) => void
}

/* ── Store ─────────────────────────────────────────────────────── */

let nextId = 0

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (type, message, duration = 4000) => {
    const id = `toast-${++nextId}`
    set((s) => ({ toasts: [...s.toasts, { id, type, message, duration }] }))
  },
  remove: (id) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
  },
}))

/* ── Convenience hook ─────────────────────────────────────────── */

export function useToast() {
  const add = useToastStore((s) => s.add)
  return {
    success: (msg: string) => add('success', msg),
    error: (msg: string) => add('error', msg),
    info: (msg: string) => add('info', msg),
  }
}

/* ── Individual Toast ─────────────────────────────────────────── */

const colorMap: Record<ToastType, { border: string; dot: string }> = {
  success: { border: '#3dffa0', dot: '#3dffa0' },
  error: { border: '#ff6b35', dot: '#ff6b35' },
  info: { border: '#63d9ff', dot: '#63d9ff' },
}

function SingleToast({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false)
  const [opacity, setOpacity] = useState(0)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null)
  const colors = colorMap[toast.type]

  const startTimer = useCallback(() => {
    timerRef.current = setTimeout(() => {
      setOpacity(0)
      setTimeout(onDismiss, 200)
    }, toast.duration)
  }, [toast.duration, onDismiss])

  useEffect(() => {
    setOpacity(1)
    startTimer()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [startTimer])

  useEffect(() => {
    if (paused && timerRef.current) {
      clearTimeout(timerRef.current)
    } else if (!paused) {
      startTimer()
    }
  }, [paused, startTimer])

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      style={{
        background: '#0d0d1f',
        borderLeft: `3px solid ${colors.border}`,
        border: `1px solid rgba(255,255,255,0.08)`,
        borderRadius: 8,
        padding: '14px 16px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        opacity,
        transform: opacity ? 'translateX(0)' : 'translateX(20px)',
        transition: 'all 200ms ease',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }}
    >
      <span style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: colors.dot,
        marginTop: 4,
        flexShrink: 0,
      }} />
      <span style={{
        fontFamily: "'Syne', sans-serif",
        fontSize: 12,
        color: '#e8e8f0',
        lineHeight: 1.5,
        flex: 1,
      }}>
        {toast.message}
      </span>
      <button
        onClick={() => {
          setOpacity(0)
          setTimeout(onDismiss, 200)
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'rgba(232,232,240,0.30)',
          cursor: 'pointer',
          fontSize: 14,
          padding: 0,
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  )
}

/* ── Toast Container (render once in App) ─────────────────────── */

export function ToastContainer(): ReactNode {
  const toasts = useToastStore((s) => s.toasts)
  const remove = useToastStore((s) => s.remove)

  if (toasts.length === 0) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        width: 360,
      }}
    >
      {toasts.map((t) => (
        <SingleToast key={t.id} toast={t} onDismiss={() => remove(t.id)} />
      ))}
    </div>
  )
}
