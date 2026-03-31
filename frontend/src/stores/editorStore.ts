/* ------------------------------------------------------------------ */
/*  FORGE — Editor Zustand Store                                       */
/*  Manages open files, contents, modified state, preview, annotations */
/* ------------------------------------------------------------------ */

import { create } from 'zustand'
import type { Annotation, BuildSnapshot } from '@/types'
import axios from 'axios'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileTreeNode[]
}

interface EditorState {
  /* IDs */
  projectId: string | null
  sandboxId: string | null
  sessionId: string | null

  /* File management */
  openFiles: string[]
  activeFile: string | null
  fileContents: Record<string, string>
  modifiedFiles: Record<string, boolean>
  fileTree: FileTreeNode[]

  /* Preview */
  previewVisible: boolean
  previewDevice: 'mobile' | 'tablet' | 'desktop'
  previewRoute: string

  /* Annotations */
  annotationMode: boolean
  annotations: Annotation[]

  /* Snapshots */
  snapshots: BuildSnapshot[]
  selectedSnapshot: BuildSnapshot | null

  /* Loading */
  loading: boolean
  savingFile: string | null
}

interface EditorActions {
  /* Init */
  setProjectId: (id: string) => void
  setSandboxId: (id: string) => void
  setSessionId: (id: string) => void
  setFileTree: (tree: FileTreeNode[]) => void

  /* File operations */
  openFile: (path: string) => Promise<void>
  closeFile: (path: string) => void
  setActiveFile: (path: string) => void
  updateFileContent: (path: string, content: string) => void
  saveFile: (path: string) => Promise<void>

  /* Preview */
  togglePreview: () => void
  setPreviewDevice: (device: 'mobile' | 'tablet' | 'desktop') => void
  setPreviewRoute: (route: string) => void

  /* Annotations */
  toggleAnnotationMode: () => void
  setAnnotations: (annotations: Annotation[]) => void

  /* Snapshots */
  setSnapshots: (snapshots: BuildSnapshot[]) => void
  selectSnapshot: (snapshot: BuildSnapshot | null) => void

  /* Reset */
  reset: () => void
}

const initialState: EditorState = {
  projectId: null,
  sandboxId: null,
  sessionId: null,
  openFiles: [],
  activeFile: null,
  fileContents: {},
  modifiedFiles: {},
  fileTree: [],
  previewVisible: true,
  previewDevice: 'desktop',
  previewRoute: '/',
  annotationMode: false,
  annotations: [],
  snapshots: [],
  selectedSnapshot: null,
  loading: false,
  savingFile: null,
}

export const useEditorStore = create<EditorState & EditorActions>()((set, get) => ({
  ...initialState,

  /* ----- Init ----- */
  setProjectId: (id) => set({ projectId: id }),
  setSandboxId: (id) => set({ sandboxId: id }),
  setSessionId: (id) => set({ sessionId: id }),
  setFileTree: (tree) => set({ fileTree: tree }),

  /* ----- File operations ----- */
  openFile: async (path) => {
    const state = get()

    // Already cached — just activate
    if (path in state.fileContents) {
      set({
        activeFile: path,
        openFiles: state.openFiles.includes(path)
          ? state.openFiles
          : [...state.openFiles, path],
      })
      return
    }

    // Load from API
    if (!state.projectId) return
    set({ loading: true })

    try {
      const res = await axios.get<{ content: string }>(
        `/api/v1/projects/${state.projectId}/files/content`,
        { params: { path } },
      )
      set((s) => ({
        fileContents: { ...s.fileContents, [path]: res.data.content },
        activeFile: path,
        openFiles: s.openFiles.includes(path)
          ? s.openFiles
          : [...s.openFiles, path],
        loading: false,
      }))
    } catch {
      // On error, still open with empty content so UI doesn't break
      set((s) => ({
        fileContents: { ...s.fileContents, [path]: '' },
        activeFile: path,
        openFiles: s.openFiles.includes(path)
          ? s.openFiles
          : [...s.openFiles, path],
        loading: false,
      }))
    }
  },

  closeFile: (path) => {
    const state = get()
    const newOpen = state.openFiles.filter((f) => f !== path)

    // Keep fileContents cached so reopening is instant.
    // Only clear the modified flag for the closed tab.
    const newModified = { ...state.modifiedFiles }
    delete newModified[path]

    set({
      openFiles: newOpen,
      modifiedFiles: newModified,
      activeFile:
        state.activeFile === path
          ? newOpen[newOpen.length - 1] ?? null
          : state.activeFile,
    })
  },

  setActiveFile: (path) => set({ activeFile: path }),

  updateFileContent: (path, content) => {
    set((s) => ({
      fileContents: { ...s.fileContents, [path]: content },
      modifiedFiles: { ...s.modifiedFiles, [path]: true },
    }))
  },

  saveFile: async (path) => {
    const state = get()
    if (!state.projectId) return

    const content = state.fileContents[path]
    if (content === undefined) return

    set({ savingFile: path })

    try {
      await axios.put(
        `/api/v1/projects/${state.projectId}/files/content`,
        { path, content },
      )
      set((s) => {
        const newModified = { ...s.modifiedFiles }
        delete newModified[path]
        return { modifiedFiles: newModified, savingFile: null }
      })
    } catch {
      set({ savingFile: null })
    }
  },

  /* ----- Preview ----- */
  togglePreview: () => set((s) => ({ previewVisible: !s.previewVisible })),
  setPreviewDevice: (device) => set({ previewDevice: device }),
  setPreviewRoute: (route) => set({ previewRoute: route }),

  /* ----- Annotations ----- */
  toggleAnnotationMode: () =>
    set((s) => ({ annotationMode: !s.annotationMode })),
  setAnnotations: (annotations) => set({ annotations }),

  /* ----- Snapshots ----- */
  setSnapshots: (snapshots) => set({ snapshots }),
  selectSnapshot: (snapshot) => set({ selectedSnapshot: snapshot }),

  /* ----- Reset ----- */
  reset: () => set(initialState),
}))
