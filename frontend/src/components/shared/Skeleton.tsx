/**
 * Loading skeleton with shimmer animation.
 *
 * DESIGN_BRIEF: background rgba(255,255,255,0.04),
 * animated gradient sweeping left to right.
 */

import type { CSSProperties, ReactNode } from 'react'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  borderRadius?: number
  style?: CSSProperties
}

export default function Skeleton({
  width = '100%',
  height = 16,
  borderRadius = 6,
  style,
}: SkeletonProps): ReactNode {
  return (
    <div
      className="skeleton-shimmer"
      style={{
        width,
        height,
        borderRadius,
        background: 'rgba(255,255,255,0.04)',
        position: 'relative',
        overflow: 'hidden',
        ...style,
      }}
    />
  )
}

/* ── Pre-built skeleton patterns ──────────────────────────────── */

export function SkeletonCard(): ReactNode {
  return (
    <div
      style={{
        background: '#0d0d1f',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12,
        padding: 22,
      }}
    >
      <Skeleton height={90} borderRadius={8} style={{ marginBottom: 12 }} />
      <Skeleton width={80} height={12} style={{ marginBottom: 6 }} />
      <Skeleton width="80%" height={14} style={{ marginBottom: 3 }} />
      <Skeleton width="60%" height={11} style={{ marginBottom: 14 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Skeleton width={60} height={10} />
        <Skeleton width={100} height={32} borderRadius={8} />
      </div>
    </div>
  )
}

export function SkeletonRow(): ReactNode {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px' }}>
      <Skeleton width={8} height={8} borderRadius={4} />
      <div style={{ flex: 1 }}>
        <Skeleton width="40%" height={13} style={{ marginBottom: 4 }} />
        <Skeleton width="60%" height={10} />
      </div>
      <Skeleton width={60} height={10} />
    </div>
  )
}
