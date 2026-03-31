/* ------------------------------------------------------------------ */
/*  FORGE — Editor Tabs Component                                      */
/*  Scrollable tabs with modified indicator and close button           */
/* ------------------------------------------------------------------ */

import { useCallback, useRef, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'

/* ------------------------------------------------------------------ */
/*  File icon for tab                                                  */
/* ------------------------------------------------------------------ */
function getTabIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const icons: Record<string, string> = {
    tsx: '⚛', jsx: '⚛', ts: '🔷', js: '🟡',
    css: '🎨', html: '🌐', json: '📋', md: '📝',
    py: '🐍', rs: '🦀', go: '🔹',
  }
  return icons[ext] ?? '📄'
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function EditorTabs() {
  const openFiles = useEditorStore((s) => s.openFiles)
  const activeFile = useEditorStore((s) => s.activeFile)
  const modifiedFiles = useEditorStore((s) => s.modifiedFiles)
  const setActiveFile = useEditorStore((s) => s.setActiveFile)
  const closeFile = useEditorStore((s) => s.closeFile)
  const containerRef = useRef<HTMLDivElement>(null)

  /* Auto-scroll active tab into view */
  useEffect(() => {
    if (!containerRef.current || !activeFile) return
    const activeTab = containerRef.current.querySelector(
      `[data-tab-path="${CSS.escape(activeFile)}"]`,
    )
    if (activeTab) {
      activeTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
    }
  }, [activeFile])

  const handleClose = useCallback(
    (e: React.MouseEvent, path: string) => {
      e.stopPropagation()
      closeFile(path)
    },
    [closeFile],
  )

  if (openFiles.length === 0) return null

  return (
    <div
      ref={containerRef}
      style={{
        height: 34,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        overflowX: 'auto',
        flexShrink: 0,
      }}
    >
      {openFiles.map((path) => {
        const fileName = path.split('/').pop() ?? path
        const isActive = path === activeFile
        const isModified = modifiedFiles[path]

        return (
          <div
            key={path}
            data-tab-path={path}
            onClick={() => setActiveFile(path)}
            style={{
              minWidth: 90,
              maxWidth: 180,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '0 12px',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: isActive ? '#e8e8f0' : 'rgba(232,232,240,0.40)',
              borderBottom: isActive
                ? '2px solid #63d9ff'
                : '2px solid transparent',
              background: isActive
                ? 'rgba(255,255,255,0.02)'
                : 'transparent',
              cursor: 'pointer',
              flexShrink: 0,
              transition: 'all 100ms ease',
              borderRight: '1px solid rgba(255,255,255,0.04)',
              userSelect: 'none',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = 'rgba(232,232,240,0.65)'
                e.currentTarget.style.background = 'rgba(255,255,255,0.015)'
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = 'rgba(232,232,240,0.40)'
                e.currentTarget.style.background = 'transparent'
              }
            }}
          >
            {/* Modified dot */}
            {isModified && (
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#ff6b35',
                  flexShrink: 0,
                }}
              />
            )}

            {/* File icon */}
            <span style={{ fontSize: 10, flexShrink: 0 }}>
              {getTabIcon(fileName)}
            </span>

            {/* File name */}
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1,
              }}
            >
              {fileName}
            </span>

            {/* Close button */}
            <span
              onClick={(e) => handleClose(e, path)}
              style={{
                fontSize: 12,
                color: 'rgba(232,232,240,0.25)',
                cursor: 'pointer',
                flexShrink: 0,
                lineHeight: 1,
                padding: '0 2px',
                borderRadius: 3,
                transition: 'all 100ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#e8e8f0'
                e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'rgba(232,232,240,0.25)'
                e.currentTarget.style.background = 'transparent'
              }}
            >
              ×
            </span>
          </div>
        )
      })}
    </div>
  )
}
