/* ------------------------------------------------------------------ */
/*  FORGE — File Tree Component                                        */
/*  Recursive tree with file type icons, status dots, context menu     */
/* ------------------------------------------------------------------ */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { FileTreeNode } from '@/stores/editorStore'
import { useEditorStore } from '@/stores/editorStore'

/* ------------------------------------------------------------------ */
/*  File icon mapping                                                  */
/* ------------------------------------------------------------------ */
function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const icons: Record<string, string> = {
    tsx: '⚛',
    jsx: '⚛',
    ts: '🔷',
    js: '🟡',
    css: '🎨',
    scss: '🎨',
    html: '🌐',
    json: '📋',
    md: '📝',
    py: '🐍',
    rs: '🦀',
    go: '🔹',
    sql: '🗃',
    yaml: '⚙',
    yml: '⚙',
    env: '🔐',
    svg: '🖼',
    png: '🖼',
    jpg: '🖼',
    gitignore: '🚫',
    lock: '🔒',
  }
  return icons[ext] ?? '📄'
}

/* ------------------------------------------------------------------ */
/*  Context menu items                                                 */
/* ------------------------------------------------------------------ */
interface ContextMenuItem {
  label: string
  action: string
  danger?: boolean
}

const FILE_CONTEXT_MENU: ContextMenuItem[] = [
  { label: 'New File', action: 'new-file' },
  { label: 'New Folder', action: 'new-folder' },
  { label: 'Rename', action: 'rename' },
  { label: 'Delete', action: 'delete', danger: true },
  { label: 'Copy Path', action: 'copy-path' },
]

const DIR_CONTEXT_MENU: ContextMenuItem[] = [
  { label: 'New File', action: 'new-file' },
  { label: 'New Folder', action: 'new-folder' },
  { label: 'Rename', action: 'rename' },
  { label: 'Delete', action: 'delete', danger: true },
  { label: 'Copy Path', action: 'copy-path' },
]

/* ------------------------------------------------------------------ */
/*  Context Menu Component                                             */
/* ------------------------------------------------------------------ */
interface ContextMenuProps {
  x: number
  y: number
  items: ContextMenuItem[]
  onSelect: (action: string) => void
  onClose: () => void
}

function ContextMenu({ x, y, items, onSelect, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  return (
    <div
      ref={menuRef}
      style={{
        position: 'fixed',
        left: x,
        top: y,
        background: '#0d0d1f',
        border: '1px solid rgba(255,255,255,0.10)',
        borderRadius: 6,
        padding: '4px 0',
        minWidth: 140,
        zIndex: 200,
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      }}
    >
      {items.map((item) => (
        <button
          key={item.action}
          onClick={() => {
            onSelect(item.action)
            onClose()
          }}
          style={{
            display: 'block',
            width: '100%',
            padding: '5px 12px',
            background: 'transparent',
            border: 'none',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: item.danger ? '#ff6b35' : 'rgba(232,232,240,0.65)',
            cursor: 'pointer',
            textAlign: 'left',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Tree Node Component                                                */
/* ------------------------------------------------------------------ */
interface TreeNodeProps {
  node: FileTreeNode
  depth: number
  onContextMenu: (e: React.MouseEvent, node: FileTreeNode) => void
}

function TreeNode({ node, depth, onContextMenu }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 2)
  const activeFile = useEditorStore((s) => s.activeFile)
  const modifiedFiles = useEditorStore((s) => s.modifiedFiles)
  const openFile = useEditorStore((s) => s.openFile)

  const isActive = node.type === 'file' && activeFile === node.path
  const isModified = node.type === 'file' && modifiedFiles[node.path]
  const isDir = node.type === 'directory'

  const handleClick = useCallback(() => {
    if (isDir) {
      setExpanded((v) => !v)
    } else {
      void openFile(node.path)
    }
  }, [isDir, node.path, openFile])

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      onContextMenu(e, node)
    },
    [node, onContextMenu],
  )

  /* Status dot color */
  let dotColor = 'transparent'
  if (isActive) dotColor = '#63d9ff'
  else if (isModified) dotColor = '#ff6b35'

  /* Text color */
  let textColor = 'rgba(232,232,240,0.42)'
  if (isActive) textColor = '#63d9ff'
  else if (isDir) textColor = '#e8e8f0'

  return (
    <>
      <div
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: `3px 8px 3px ${8 + depth * 14}px`,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: textColor,
          background: isActive ? 'rgba(99,217,255,0.08)' : 'transparent',
          cursor: 'pointer',
          userSelect: 'none',
          transition: 'background 80ms ease',
        }}
        onMouseEnter={(e) => {
          if (!isActive) {
            e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
            e.currentTarget.style.color = '#e8e8f0'
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive) {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = textColor
          }
        }}
      >
        {isDir ? (
          <span
            style={{
              color: '#f5c842',
              fontSize: 8,
              transition: 'transform 120ms ease',
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
              display: 'inline-block',
            }}
          >
            ▶
          </span>
        ) : (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: dotColor,
              flexShrink: 0,
            }}
          />
        )}
        {!isDir && (
          <span style={{ fontSize: 10, flexShrink: 0 }}>
            {getFileIcon(node.name)}
          </span>
        )}
        <span
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {node.name}
        </span>
      </div>

      {isDir && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onContextMenu={onContextMenu}
            />
          ))}
        </div>
      )}
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  File Tree Root Component                                           */
/* ------------------------------------------------------------------ */
export default function FileTree() {
  const fileTree = useEditorStore((s) => s.fileTree)
  const [contextMenu, setContextMenu] = useState<{
    x: number
    y: number
    node: FileTreeNode
  } | null>(null)

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, node: FileTreeNode) => {
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        node,
      })
    },
    [],
  )

  const handleContextAction = useCallback(
    (action: string) => {
      if (!contextMenu) return

      switch (action) {
        case 'copy-path':
          void navigator.clipboard.writeText(contextMenu.node.path)
          break
        // Other actions would dispatch to the store/API
        default:
          break
      }
    },
    [contextMenu],
  )

  return (
    <div
      id="file-tree"
      style={{
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          textTransform: 'uppercase',
          color: 'rgba(232,232,240,0.30)',
          padding: '9px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          justifyContent: 'space-between',
          letterSpacing: 1,
        }}
      >
        <span>Explorer</span>
        <span style={{ color: '#63d9ff', cursor: 'pointer', fontSize: 12 }}>
          +
        </span>
      </div>

      {/* Tree */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
        {fileTree.map((node) => (
          <TreeNode
            key={node.path}
            node={node}
            depth={0}
            onContextMenu={handleContextMenu}
          />
        ))}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={
            contextMenu.node.type === 'directory'
              ? DIR_CONTEXT_MENU
              : FILE_CONTEXT_MENU
          }
          onSelect={handleContextAction}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  )
}
