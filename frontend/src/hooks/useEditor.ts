/* ------------------------------------------------------------------ */
/*  FORGE — useEditor Hook                                             */
/*  Initializes editor session, loads file tree, manages WebSocket,    */
/*  and handles debounced auto-save                                    */
/* ------------------------------------------------------------------ */

import { useEffect, useRef, useCallback } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import type { FileTreeNode } from '@/stores/editorStore'
import axios from 'axios'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface FileTreeAPINode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileTreeAPINode[]
}

interface EditorSessionResponse {
  id: string
  sandbox_id: string
}

/* ------------------------------------------------------------------ */
/*  Debounce utility                                                   */
/* ------------------------------------------------------------------ */
function debounce<T extends (...args: never[]) => void>(
  fn: T,
  ms: number,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), ms)
  }
}

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */
export function useEditor(projectId: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const initializedRef = useRef(false)

  // Use getState() for actions to avoid subscribing to entire store.
  // This prevents re-renders on every keystroke / state change.
  const getStore = useCallback(() => useEditorStore.getState(), [])

  /* ---- Init session ---- */
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    const store = getStore()
    store.setProjectId(projectId)

    const init = async () => {
      try {
        // 1. Create editor session
        const sessionRes = await axios.post<EditorSessionResponse>(
          '/api/v1/editor/sessions',
          { project_id: projectId },
        )
        getStore().setSessionId(sessionRes.data.id)
        getStore().setSandboxId(sessionRes.data.sandbox_id)

        // 2. Load file tree
        const treeRes = await axios.get<FileTreeAPINode[]>(
          `/api/v1/projects/${projectId}/files`,
        )
        getStore().setFileTree(treeRes.data as FileTreeNode[])

        // 3. Auto-open first file
        const firstFile = findFirstFile(treeRes.data as FileTreeNode[])
        if (firstFile) {
          await getStore().openFile(firstFile)
        }

        // 4. WebSocket connection
        connectWebSocket(sessionRes.data.id)
      } catch {
        // Backend may not be running — degrade gracefully with demo data
        loadDemoData()
      }
    }

    init()

    return () => {
      wsRef.current?.close()
      getStore().reset()
      initializedRef.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  /* ---- WebSocket ---- */
  const connectWebSocket = useCallback(
    (sessionId: string) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/editor/sessions/${sessionId}/stream`,
      )

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            type: string
            path?: string
            content?: string
          }
          if (data.type === 'file_changed' && data.path && data.content) {
            getStore().updateFileContent(data.path, data.content)
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = () => {
        // Reconnect after 3s
        setTimeout(() => {
          if (initializedRef.current) {
            connectWebSocket(sessionId)
          }
        }, 3000)
      }

      wsRef.current = ws
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  /* ---- Debounced auto-save ---- */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSave = useCallback(
    debounce((path: string) => {
      void getStore().saveFile(path)
    }, 500),
    [],
  )

  const handleContentChange = useCallback(
    (path: string, content: string) => {
      getStore().updateFileContent(path, content)
      debouncedSave(path)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [debouncedSave],
  )

  return {
    handleContentChange,
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function findFirstFile(nodes: FileTreeNode[]): string | null {
  for (const node of nodes) {
    if (node.type === 'file') return node.path
    if (node.children) {
      const found = findFirstFile(node.children)
      if (found) return found
    }
  }
  return null
}

/** Load demo data when backend is unavailable */
function loadDemoData() {
  const store = useEditorStore.getState()

  const demoTree: FileTreeNode[] = [
    {
      name: 'src',
      path: 'src',
      type: 'directory',
      children: [
        {
          name: 'app',
          path: 'src/app',
          type: 'directory',
          children: [
            { name: 'layout.tsx', path: 'src/app/layout.tsx', type: 'file' },
            { name: 'page.tsx', path: 'src/app/page.tsx', type: 'file' },
            { name: 'globals.css', path: 'src/app/globals.css', type: 'file' },
            {
              name: 'dashboard',
              path: 'src/app/dashboard',
              type: 'directory',
              children: [
                {
                  name: 'page.tsx',
                  path: 'src/app/dashboard/page.tsx',
                  type: 'file',
                },
              ],
            },
          ],
        },
        {
          name: 'components',
          path: 'src/components',
          type: 'directory',
          children: [
            {
              name: 'Header.tsx',
              path: 'src/components/Header.tsx',
              type: 'file',
            },
            {
              name: 'Sidebar.tsx',
              path: 'src/components/Sidebar.tsx',
              type: 'file',
            },
            {
              name: 'Chart.tsx',
              path: 'src/components/Chart.tsx',
              type: 'file',
            },
          ],
        },
        {
          name: 'lib',
          path: 'src/lib',
          type: 'directory',
          children: [
            { name: 'utils.ts', path: 'src/lib/utils.ts', type: 'file' },
            { name: 'api.ts', path: 'src/lib/api.ts', type: 'file' },
          ],
        },
      ],
    },
    { name: 'package.json', path: 'package.json', type: 'file' },
    { name: 'tsconfig.json', path: 'tsconfig.json', type: 'file' },
  ]

  store.setFileTree(demoTree)

  // Pre-populate some file contents
  const demoContents: Record<string, string> = {
    'src/app/page.tsx': `import { Metadata } from 'next'
import { DashboardShell } from '@/components/shell'
import { StatsCards } from '@/components/stats'

export const metadata: Metadata = {
  title: 'Dashboard | SaaS App',
  description: 'Analytics dashboard',
}

export default async function DashboardPage() {
  const stats = await getStats()
  const projects = await getProjects()

  return (
    <DashboardShell>
      <div className="grid gap-4 md:grid-cols-4">
        <StatsCards data={stats} />
      </div>
      <div className="mt-8">
        <h2 className="text-xl font-bold">
          Recent Projects
        </h2>
        {projects.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </DashboardShell>
  )
}`,
    'src/app/layout.tsx': `import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'SaaS Dashboard',
  description: 'A modern SaaS application',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  )
}`,
    'src/components/Header.tsx': `interface HeaderProps {
  title: string
  subtitle?: string
}

export function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="flex items-center justify-between p-4 border-b">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        {subtitle && (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>
      <nav className="flex items-center gap-4">
        <button className="btn btn-ghost">Settings</button>
        <button className="btn btn-primary">Deploy</button>
      </nav>
    </header>
  )
}`,
    'src/lib/utils.ts': `export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ')
}

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}`,
  }

  // Set contents and open the first file
  for (const [path, content] of Object.entries(demoContents)) {
    store.updateFileContent(path, content)
  }

  // Clear modified flags for preloaded content
  useEditorStore.setState({ modifiedFiles: {} })

  // Open main file
  const firstPath = 'src/app/page.tsx'
  useEditorStore.setState({
    openFiles: [firstPath],
    activeFile: firstPath,
  })
}
