/* ------------------------------------------------------------------ */
/*  FORGE — Monaco Editor Component                                    */
/*  Custom FORGE dark theme + keybindings                              */
/* ------------------------------------------------------------------ */

import { useRef, useCallback } from 'react'
import Editor, { type OnMount, type BeforeMount } from '@monaco-editor/react'
import type * as MonacoType from 'monaco-editor'
import { useEditorStore } from '@/stores/editorStore'

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */
interface MonacoEditorProps {
  filePath: string
  content: string
  onChange: (path: string, content: string) => void
}

/* ------------------------------------------------------------------ */
/*  FORGE dark theme definition                                        */
/* ------------------------------------------------------------------ */
const FORGE_THEME_NAME = 'forge-dark'

function defineForgeTheme(monaco: typeof MonacoType) {
  monaco.editor.defineTheme(FORGE_THEME_NAME, {
    base: 'vs-dark',
    inherit: false,
    rules: [
      /* Keywords: violet */
      { token: 'keyword', foreground: 'b06bff', fontStyle: 'bold' },
      { token: 'keyword.control', foreground: 'b06bff' },
      { token: 'storage', foreground: 'b06bff' },
      { token: 'storage.type', foreground: 'b06bff' },

      /* Functions: forge cyan */
      { token: 'entity.name.function', foreground: '63d9ff' },
      { token: 'support.function', foreground: '63d9ff' },
      { token: 'meta.function-call', foreground: '63d9ff' },

      /* Strings: jade */
      { token: 'string', foreground: '3dffa0' },
      { token: 'string.template', foreground: '3dffa0' },
      { token: 'string.regexp', foreground: '3dffa0' },

      /* Types: gold */
      { token: 'type', foreground: 'f5c842' },
      { token: 'type.identifier', foreground: 'f5c842' },
      { token: 'entity.name.type', foreground: 'f5c842' },
      { token: 'support.type', foreground: 'f5c842' },
      { token: 'entity.name.class', foreground: 'f5c842' },

      /* Comments: faint + italic */
      { token: 'comment', foreground: 'e8e8f040', fontStyle: 'italic' },
      { token: 'comment.line', foreground: 'e8e8f040', fontStyle: 'italic' },
      { token: 'comment.block', foreground: 'e8e8f040', fontStyle: 'italic' },

      /* Operators: ember */
      { token: 'delimiter', foreground: 'ff6b35' },
      { token: 'delimiter.bracket', foreground: 'e8e8f0' },
      { token: 'operator', foreground: 'ff6b35' },

      /* Numbers */
      { token: 'number', foreground: 'f5c842' },
      { token: 'constant.numeric', foreground: 'f5c842' },

      /* Variables / identifiers */
      { token: 'variable', foreground: 'e8e8f0' },
      { token: 'variable.parameter', foreground: 'e8e8f0' },
      { token: 'identifier', foreground: 'e8e8f0' },

      /* JSX tags */
      { token: 'tag', foreground: '63d9ff' },
      { token: 'metatag', foreground: '63d9ff' },
      { token: 'tag.attribute.name', foreground: 'e8e8f0' },

      /* Default */
      { token: '', foreground: 'e8e8f0' },
    ],
    colors: {
      'editor.background': '#04040a',
      'editor.foreground': '#e8e8f0',
      'editor.lineHighlightBackground': '#ffffff08',
      'editor.selectionBackground': '#63d9ff20',
      'editor.inactiveSelectionBackground': '#63d9ff10',
      'editorLineNumber.foreground': '#e8e8f026',
      'editorLineNumber.activeForeground': '#63d9ff80',
      'editorCursor.foreground': '#63d9ff',
      'editorWhitespace.foreground': '#e8e8f010',
      'editorIndentGuide.background': '#e8e8f008',
      'editorIndentGuide.activeBackground': '#e8e8f015',
      'editor.findMatchBackground': '#63d9ff30',
      'editor.findMatchHighlightBackground': '#63d9ff18',
      'editorBracketMatch.background': '#63d9ff15',
      'editorBracketMatch.border': '#63d9ff40',
      'editorGutter.background': '#04040a',
      'editorOverviewRuler.border': '#ffffff06',
      'editorWidget.background': '#0d0d1f',
      'editorWidget.border': '#ffffff0f',
      'editorSuggestWidget.background': '#0d0d1f',
      'editorSuggestWidget.border': '#ffffff0f',
      'editorSuggestWidget.selectedBackground': '#63d9ff15',
      'editorHoverWidget.background': '#0d0d1f',
      'editorHoverWidget.border': '#ffffff0f',
      'minimap.background': '#04040a',
      'minimapSlider.background': '#63d9ff10',
      'minimapSlider.hoverBackground': '#63d9ff18',
      'minimapSlider.activeBackground': '#63d9ff22',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#63d9ff20',
      'scrollbarSlider.hoverBackground': '#63d9ff40',
      'scrollbarSlider.activeBackground': '#63d9ff60',
    },
  })
}

/* ------------------------------------------------------------------ */
/*  Language detection (from file extension)                           */
/* ------------------------------------------------------------------ */
function getLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    json: 'json',
    css: 'css',
    scss: 'scss',
    html: 'html',
    md: 'markdown',
    yaml: 'yaml',
    yml: 'yaml',
    py: 'python',
    rs: 'rust',
    go: 'go',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
    toml: 'toml',
    xml: 'xml',
    svg: 'xml',
    env: 'plaintext',
    txt: 'plaintext',
    gitignore: 'plaintext',
  }
  return map[ext] ?? 'plaintext'
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function MonacoEditor({
  filePath,
  content,
  onChange,
}: MonacoEditorProps) {
  const editorRef = useRef<MonacoType.editor.IStandaloneCodeEditor | null>(null)
  const saveFile = useEditorStore((s) => s.saveFile)

  /* Register theme before mount */
  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    defineForgeTheme(monaco)
  }, [])

  /* On mount: register Ctrl/Cmd+S keybinding */
  const handleMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor

      // Ctrl/Cmd+S → immediate save
      editor.addCommand(
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
        () => {
          void saveFile(filePath)
        },
      )

      // Focus the editor
      editor.focus()
    },
    [filePath, saveFile],
  )

  /* Handle content changes */
  const handleChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined) {
        onChange(filePath, value)
      }
    },
    [filePath, onChange],
  )

  return (
    <Editor
      height="100%"
      language={getLanguage(filePath)}
      value={content}
      theme={FORGE_THEME_NAME}
      beforeMount={handleBeforeMount}
      onMount={handleMount}
      onChange={handleChange}
      options={{
        fontSize: 12,
        lineHeight: 22,
        fontFamily: "'JetBrains Mono', monospace",
        fontLigatures: true,
        minimap: {
          enabled: true,
          maxColumn: 80,
          renderCharacters: false,
          side: 'right',
        },
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        renderLineHighlight: 'line',
        wordWrap: 'off',
        tabSize: 2,
        insertSpaces: true,
        automaticLayout: true,
        padding: { top: 16, bottom: 16 },
        lineNumbersMinChars: 3,
        glyphMargin: false,
        folding: true,
        bracketPairColorization: { enabled: true },
        guides: {
          indentation: true,
          bracketPairs: true,
        },
        suggest: {
          showStatusBar: true,
        },
        quickSuggestions: true,
        parameterHints: { enabled: true },
      }}
      loading={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            background: '#04040a',
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10,
              color: 'rgba(232,232,240,0.25)',
              letterSpacing: 2,
              textTransform: 'uppercase',
            }}
          >
            Loading editor...
          </div>
        </div>
      }
    />
  )
}
