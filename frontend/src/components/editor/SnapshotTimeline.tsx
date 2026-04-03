/* ------------------------------------------------------------------ */
/*  FORGE — SnapshotTimeline                                           */
/*  Scrub through 10 build-agent snapshots in the PreviewPane.         */
/*  Shows a track of dots, connecting segments, LIVE indicator,        */
/*  and hover popovers with thumbnails.                                */
/* ------------------------------------------------------------------ */

import { useState, useCallback } from 'react'
import type { BuildSnapshot } from '@/types'

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const AGENT_LABELS: readonly string[] = [
  'Scaffold',
  'Router',
  'Component',
  'Page',
  'API',
  'DB',
  'Auth',
  'Style',
  'Test',
  'Review',
] as const

const TOTAL_DOTS = 10

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface SnapshotTimelineProps {
  snapshots: BuildSnapshot[]
  selectedSnapshot: BuildSnapshot | null
  onSelectSnapshot: (snapshot: BuildSnapshot | null) => void
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/**
 * Format ISO timestamp to "H:MM AM/PM".
 */
function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const h = d.getHours()
    const m = d.getMinutes()
    const ampm = h >= 12 ? 'PM' : 'AM'
    const hh = h % 12 || 12
    const mm = String(m).padStart(2, '0')
    return `${hh}:${mm} ${ampm}`
  } catch {
    return ''
  }
}

/* ------------------------------------------------------------------ */
/*  Shimmer placeholder for loading thumbnails                         */
/* ------------------------------------------------------------------ */

function ThumbnailShimmer() {
  return (
    <div
      style={{
        width: 180,
        height: 110,
        borderRadius: 4,
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
            'linear-gradient(90deg, transparent 0%, rgba(99,217,255,0.06) 50%, transparent 100%)',
          animation: 'shimmer 1.5s ease-in-out infinite',
        }}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  SnapshotDot — individual dot with hover popover                    */
/* ------------------------------------------------------------------ */

interface SnapshotDotProps {
  index: number
  snapshot: BuildSnapshot | null
  isSelected: boolean
  onSelect: (snapshot: BuildSnapshot | null) => void
  isLast: boolean
}

function SnapshotDot({ index, snapshot, isSelected, onSelect, isLast }: SnapshotDotProps) {
  const [hovered, setHovered] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)

  const isDone = snapshot !== null

  const handleClick = useCallback(() => {
    if (!isDone) return
    if (isSelected) {
      onSelect(null)
    } else {
      onSelect(snapshot)
    }
  }, [isDone, isSelected, onSelect, snapshot])

  /* ---- Dot styles ---- */
  const baseDot: React.CSSProperties = {
    borderRadius: '50%',
    flexShrink: 0,
    cursor: isDone ? 'pointer' : 'default',
    transition: 'all 0.15s ease',
    position: 'relative',
  }

  const dotStyle: React.CSSProperties = isSelected
    ? {
        ...baseDot,
        width: 12,
        height: 12,
        margin: -2,
        background: '#63d9ff',
        border: '2px solid #63d9ff',
        boxShadow: '0 0 0 3px rgba(99,217,255,0.20)',
      }
    : isDone
      ? {
          ...baseDot,
          width: 8,
          height: 8,
          background: '#3dffa0',
          border: 'none',
        }
      : {
          ...baseDot,
          width: 8,
          height: 8,
          background: 'rgba(255,255,255,0.10)',
          border: 'none',
        }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        flex: isLast ? undefined : 1,
        position: 'relative',
      }}
    >
      {/* Dot */}
      <div
        style={dotStyle}
        onClick={handleClick}
        onMouseEnter={() => isDone && setHovered(true)}
        onMouseLeave={() => {
          setHovered(false)
          setImgLoaded(false)
        }}
        role="button"
        tabIndex={isDone ? 0 : -1}
        aria-label={
          isDone
            ? `Snapshot ${index + 1}: ${AGENT_LABELS[index]}`
            : `Agent ${index + 1}: ${AGENT_LABELS[index]} — pending`
        }
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        }}
      />

      {/* Hover popover */}
      {hovered && isDone && snapshot && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginBottom: 10,
            background: '#0d0d1f',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 8,
            padding: 8,
            zIndex: 100,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            minWidth: 180,
          }}
        >
          {/* Thumbnail or shimmer */}
          {!imgLoaded && <ThumbnailShimmer />}
          <img
            src={snapshot.image_url}
            alt={`${AGENT_LABELS[index]} snapshot`}
            style={{
              width: 180,
              height: 'auto',
              borderRadius: 4,
              display: imgLoaded ? 'block' : 'none',
            }}
            onLoad={() => setImgLoaded(true)}
          />

          {/* Agent label */}
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: '#e8e8f0',
              fontWeight: 600,
              marginTop: 6,
              letterSpacing: 0.5,
            }}
          >
            {AGENT_LABELS[index]}
          </div>

          {/* Timestamp */}
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 8,
              color: 'rgba(232,232,240,0.35)',
              marginTop: 2,
            }}
          >
            {formatTime(snapshot.created_at)}
          </div>
        </div>
      )}

      {/* Connecting segment */}
      {!isLast && (
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
}

/* ------------------------------------------------------------------ */
/*  Main SnapshotTimeline Component                                    */
/* ------------------------------------------------------------------ */

export default function SnapshotTimeline({
  snapshots,
  selectedSnapshot,
  onSelectSnapshot,
}: SnapshotTimelineProps) {
  /**
   * Build a lookup: snapshots may arrive out-of-order or sparse,
   * so we index by agent_index for each dot position.
   */
  const snapshotByIndex = (index: number): BuildSnapshot | null => {
    return snapshots.find((s) => s.agent_index === index) ?? null
  }

  return (
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
      {/* BUILD label */}
      <span
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 7,
          color: 'rgba(238,240,246,0.30)',
          flexShrink: 0,
          letterSpacing: 1,
          textTransform: 'uppercase',
          userSelect: 'none',
        }}
      >
        BUILD
      </span>

      {/* Track */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
        {Array.from({ length: TOTAL_DOTS }, (_, i) => {
          const snapshot = snapshotByIndex(i)
          const isSelected = selectedSnapshot !== null && snapshot !== null && selectedSnapshot.id === snapshot.id

          return (
            <SnapshotDot
              key={i}
              index={i}
              snapshot={snapshot}
              isSelected={isSelected}
              onSelect={onSelectSnapshot}
              isLast={i === TOTAL_DOTS - 1}
            />
          )
        })}
      </div>

      {/* LIVE dot */}
      <div
        id="snapshot-live-dot"
        onClick={() => onSelectSnapshot(null)}
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
        role="button"
        tabIndex={0}
        aria-label="Return to live preview"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onSelectSnapshot(null)
          }
        }}
      />

      {/* Status label */}
      <span
        id="snapshot-status-label"
        onClick={() => {
          if (selectedSnapshot === null) return
          onSelectSnapshot(null)
        }}
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 7,
          color: selectedSnapshot ? 'rgba(238,240,246,0.35)' : '#3dffa0',
          flexShrink: 0,
          cursor: selectedSnapshot ? 'pointer' : 'default',
          userSelect: 'none',
          letterSpacing: 0.3,
        }}
      >
        {selectedSnapshot
          ? `After Agent ${selectedSnapshot.agent_index}`
          : '● LIVE'}
      </span>
    </div>
  )
}
