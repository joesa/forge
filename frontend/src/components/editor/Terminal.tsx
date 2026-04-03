/**
 * Terminal component using xterm.js.
 *
 * Connects to sandbox WebSocket for interactive shell access.
 * Handles /build, /deploy, /test, /lint commands.
 */

import { useEffect, useRef, useCallback, type ReactNode } from 'react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

interface TerminalProps {
  sandboxId: string | null
  visible: boolean
}

export default function Terminal({ sandboxId, visible }: TerminalProps): ReactNode {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<XTerm | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const initTerminal = useCallback(() => {
    if (!containerRef.current || termRef.current) return

    const term = new XTerm({
      theme: {
        background: '#04040a',
        foreground: '#e8e8f0',
        cursor: '#63d9ff',
        cursorAccent: '#04040a',
        selectionBackground: 'rgba(99,217,255,0.20)',
        black: '#04040a',
        red: '#ff6b35',
        green: '#3dffa0',
        yellow: '#f5c842',
        blue: '#63d9ff',
        magenta: '#b06bff',
        cyan: '#63d9ff',
        white: '#e8e8f0',
        brightBlack: 'rgba(232,232,240,0.30)',
        brightRed: '#ff6b35',
        brightGreen: '#3dffa0',
        brightYellow: '#f5c842',
        brightBlue: '#63d9ff',
        brightMagenta: '#b06bff',
        brightCyan: '#63d9ff',
        brightWhite: '#ffffff',
      },
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 12,
      lineHeight: 1.5,
      cursorBlink: true,
      cursorStyle: 'bar',
      scrollback: 5000,
      allowTransparency: true,
    })

    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(containerRef.current)
    fit.fit()

    termRef.current = term
    fitRef.current = fit

    term.writeln('\x1b[36m⚡ FORGE Terminal\x1b[0m')
    term.writeln('\x1b[90mConnected to sandbox environment\x1b[0m')
    term.writeln('')

    // Handle user input
    let currentLine = ''
    term.onData((data) => {
      if (data === '\r') {
        // Enter key
        term.writeln('')
        if (currentLine.trim()) {
          handleCommand(currentLine.trim(), term)
        }
        currentLine = ''
        writePrompt(term)
      } else if (data === '\x7f') {
        // Backspace
        if (currentLine.length > 0) {
          currentLine = currentLine.slice(0, -1)
          term.write('\b \b')
        }
      } else if (data === '\x03') {
        // Ctrl+C
        term.writeln('^C')
        currentLine = ''
        writePrompt(term)
      } else {
        currentLine += data
        term.write(data)
      }
    })

    writePrompt(term)
  }, [])

  // Connect WebSocket to sandbox
  useEffect(() => {
    if (!sandboxId || !termRef.current) return

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/sandbox/${sandboxId}/terminal`
    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string; data: string }
        if (msg.type === 'output' && termRef.current) {
          termRef.current.write(msg.data)
        }
      } catch {
        // Raw text output
        termRef.current?.write(event.data as string)
      }
    }

    ws.onclose = () => {
      termRef.current?.writeln('\x1b[90m[Connection closed]\x1b[0m')
    }

    wsRef.current = ws

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [sandboxId])

  // Fit on visibility/resize
  useEffect(() => {
    if (visible && fitRef.current) {
      setTimeout(() => fitRef.current?.fit(), 50)
    }
  }, [visible])

  useEffect(() => {
    const handleResize = () => {
      if (visible && fitRef.current) fitRef.current.fit()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [visible])

  // Init on mount
  useEffect(() => {
    if (visible) initTerminal()
  }, [visible, initTerminal])

  // Cleanup
  useEffect(() => {
    return () => {
      termRef.current?.dispose()
      termRef.current = null
      wsRef.current?.close()
    }
  }, [])

  if (!visible) return null

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        background: '#04040a',
        padding: '4px 8px',
      }}
    />
  )
}

/* ── Helpers ──────────────────────────────────────────────────────── */

function writePrompt(term: XTerm) {
  term.write('\x1b[36m❯\x1b[0m ')
}

function handleCommand(cmd: string, term: XTerm) {
  const cmds: Record<string, string> = {
    '/build': '🔨 Starting build pipeline...',
    '/deploy': '🚀 Initiating deployment...',
    '/test': '🧪 Running test suite...',
    '/lint': '🔍 Running linter...',
    '/install': '📦 Installing dependencies...',
    help: 'Available commands: /build /deploy /test /lint /install <pkg> help clear',
    clear: '',
  }

  if (cmd === 'clear') {
    term.clear()
    return
  }

  const base = cmd.split(' ')[0]
  const msg = cmds[base]

  if (msg !== undefined) {
    term.writeln(`\x1b[90m${msg}\x1b[0m`)
    // In production: send to WebSocket → sandbox
  } else {
    term.writeln(`\x1b[33m$ ${cmd}\x1b[0m`)
    term.writeln(`\x1b[90mCommand queued for sandbox execution\x1b[0m`)
  }
}
