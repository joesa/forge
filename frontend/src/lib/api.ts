/**
 * Centralized Axios API client with auth interceptors.
 *
 * - Reads JWT from authStore and attaches as Bearer token
 * - Handles 401 by attempting token refresh
 * - All API functions return typed responses
 */

import axios, { type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor — attach JWT ────────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Read from tokens.accessToken directly — the `accessToken` getter on
  // the store state gets frozen by Zustand's Object.assign on first set().
  const token = useAuthStore.getState().tokens?.accessToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor — handle 401 ───────────────────────────────
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const currentToken = useAuthStore.getState().tokens?.accessToken

    // Skip refresh/logout cycle for dev-mode tokens — they will always
    // be rejected by the backend. Let TanStack Query handle the error.
    const isDevToken = currentToken?.startsWith('dev-')
    if (isDevToken) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const refreshToken = useAuthStore.getState().tokens?.refreshToken
        const refreshRes = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        })
        const newToken = refreshRes.data.access_token as string
        useAuthStore.getState().setAccessToken(newToken)
        if (original.headers) {
          original.headers.Authorization = `Bearer ${newToken}`
        }
        return api(original)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

// ── Auth ─────────────────────────────────────────────────────────────

export const authApi = {
  register: (data: { display_name: string; email: string; password: string }, turnstileToken?: string) =>
    api.post('/auth/register', data, {
      headers: { 'X-Turnstile-Token': turnstileToken || 'dev-bypass-token' },
    }),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  refresh: () => api.post('/auth/refresh', {}, { withCredentials: true }),
  me: () => api.get('/auth/me'),
  forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }),
  resetPassword: (token: string, newPassword: string) =>
    api.post('/auth/reset-password', { token, new_password: newPassword }),
  verify: (token: string) => api.post('/auth/verify', { token }),
}

// ── Projects ─────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => api.get('/projects'),
  create: (data: { name: string; description: string; framework: string; prompt?: string }) =>
    api.post('/projects', data),
  get: (id: string) => api.get(`/projects/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  deploy: (id: string) => api.post(`/projects/${id}/deploy`),
  listBuilds: (id: string) => api.get(`/projects/${id}/builds`),
  listDeployments: (id: string) => api.get(`/projects/${id}/deployments`),
  // Files
  getFiles: (id: string) => api.get(`/projects/${id}/files`),
  getFileContent: (id: string, path: string) =>
    api.get(`/projects/${id}/files/content`, { params: { path } }),
  saveFileContent: (id: string, path: string, content: string) =>
    api.put(`/projects/${id}/files/content`, { path, content }),
  createFile: (id: string, path: string, content: string) =>
    api.post(`/projects/${id}/files`, { path, content }),
  deleteFile: (id: string, path: string) =>
    api.delete(`/projects/${id}/files`, { params: { path } }),
  renameFile: (id: string, oldPath: string, newPath: string) =>
    api.post(`/projects/${id}/files/rename`, { old_path: oldPath, new_path: newPath }),
  // Preview
  getSnapshots: (id: string) => api.get(`/projects/${id}/preview/snapshots`),
  getAnnotations: (id: string) => api.get(`/projects/${id}/annotations`),
  createAnnotation: (id: string, data: { selector: string; comment: string; x: number; y: number; route: string }) =>
    api.post(`/projects/${id}/annotations`, data),
  deleteAnnotation: (id: string, annotationId: string) =>
    api.delete(`/projects/${id}/annotations/${annotationId}`),
  clearAnnotations: (id: string) => api.delete(`/projects/${id}/annotations`),
}

// ── Pipeline ─────────────────────────────────────────────────────────

export const pipelineApi = {
  run: (data: { project_id: string; idea_spec?: Record<string, unknown> }) =>
    api.post('/pipeline/run', data),
  getStatus: (id: string) => api.get(`/pipeline/${id}/status`),
  getStages: (id: string) => api.get(`/pipeline/${id}/stages`),
  cancel: (id: string) => api.post(`/pipeline/${id}/cancel`),
  retry: (id: string) => api.post(`/pipeline/${id}/retry`),
  getLogs: (id: string) => api.get(`/pipeline/${id}/logs`),
}

// ── Ideation ─────────────────────────────────────────────────────────

export const ideationApi = {
  startQuestionnaire: () => api.post('/ideation/questionnaire/start'),
  getQuestionnaire: (id: string) => api.get(`/ideation/questionnaire/${id}`),
  answerQuestion: (id: string, data: { question_index: number; answer: unknown }) =>
    api.post(`/ideation/questionnaire/${id}/answer`, data),
  skipQuestion: (id: string) => api.post(`/ideation/questionnaire/${id}/skip`),
  completeQuestionnaire: (id: string) =>
    api.post(`/ideation/questionnaire/${id}/complete`),
  getIdeas: (id: string) => api.get(`/ideation/ideas/${id}`),
  saveIdea: (id: string) => api.post(`/ideation/ideas/${id}/save`),
  selectIdea: (id: string) => api.post(`/ideation/ideas/${id}/select`),
  regenerateIdea: (id: string) => api.post(`/ideation/ideas/${id}/regenerate`),
  generateDirect: () => api.post('/ideation/generate-direct'),
  enhancePrompt: (prompt: string) =>
    api.post('/ideation/prompt/enhance', { prompt }),
}

// ── Editor ───────────────────────────────────────────────────────────

export const editorApi = {
  createSession: (projectId: string) =>
    api.post('/editor/sessions', { project_id: projectId }),
  getSession: (id: string) => api.get(`/editor/sessions/${id}`),
  closeSession: (id: string) => api.delete(`/editor/sessions/${id}`),
  getChatHistory: (sessionId: string, limit = 50, offset = 0) =>
    api.get(`/editor/sessions/${sessionId}/chat`, { params: { limit, offset } }),
  sendChat: (sessionId: string, message: string, contextFiles: string[] = []) =>
    api.post(`/editor/sessions/${sessionId}/chat`, { message, context_files: contextFiles }),
  applyCode: (sessionId: string, messageId: string, codeBlockIndex: number) =>
    api.post(`/editor/sessions/${sessionId}/chat/apply`, {
      message_id: messageId,
      code_block_index: codeBlockIndex,
    }),
  runCommand: (sessionId: string, command: string, args: Record<string, string> = {}) =>
    api.post(`/editor/sessions/${sessionId}/command`, { command, args }),
}

// ── Build ────────────────────────────────────────────────────────────

export const buildApi = {
  start: (data: { project_id: string; pipeline_id?: string; incremental?: boolean }) =>
    api.post('/build/start', data),
  getStatus: (id: string) => api.get(`/build/${id}/status`),
  getLogs: (id: string) => api.get(`/build/${id}/logs`),
  cancel: (id: string, reason?: string) =>
    api.post(`/build/${id}/cancel`, { reason }),
  retry: (id: string, fromAgent?: number) =>
    api.post(`/build/${id}/retry`, { from_agent: fromAgent }),
}

// ── Sandbox ──────────────────────────────────────────────────────────

export const sandboxApi = {
  create: (projectId: string) =>
    api.post('/sandbox', { project_id: projectId }),
  start: (id: string) => api.post(`/sandbox/${id}/start`),
  stop: (id: string) => api.post(`/sandbox/${id}/stop`),
  destroy: (id: string) => api.delete(`/sandbox/${id}`),
  exec: (id: string, command: string) =>
    api.post(`/sandbox/${id}/exec`, { command }),
  getPreviewUrl: (id: string) => api.get(`/sandbox/${id}/preview-url`),
  checkHealth: (id: string) => api.get(`/sandbox/${id}/preview/health`),
  takeScreenshot: (id: string, data?: { route?: string; width?: number; height?: number }) =>
    api.post(`/sandbox/${id}/preview/screenshot`, data),
  createShare: (id: string, expiresHours?: number) =>
    api.post(`/sandbox/${id}/preview/share`, { expires_hours: expiresHours }),
  revokeShare: (id: string, token: string) =>
    api.delete(`/sandbox/${id}/preview/share/${token}`),
}

// ── Settings ─────────────────────────────────────────────────────────

export const settingsApi = {
  getProfile: () => api.get('/settings/profile'),
  updateProfile: (data: { display_name?: string; avatar_url?: string; timezone?: string }) =>
    api.put('/settings/profile', data),
  listProviders: () => api.get('/settings/ai-providers'),
  createProvider: (data: { provider_name: string; api_key: string; base_url?: string }) =>
    api.post('/settings/ai-providers', data),
  updateProvider: (id: string, data: { api_key?: string; base_url?: string; is_enabled?: boolean }) =>
    api.put(`/settings/ai-providers/${id}`, data),
  deleteProvider: (id: string) => api.delete(`/settings/ai-providers/${id}`),
  testProvider: (id: string) => api.post(`/settings/ai-providers/${id}/test`),
  getModelRouting: () => api.get('/settings/model-routing'),
  updateModelRouting: (rules: Array<{ stage: string; provider: string; model: string }>) =>
    api.put('/settings/model-routing', { rules }),
  listApiKeys: () => api.get('/settings/api-keys'),
  createApiKey: (data: { name: string; expires_in_days?: number }) =>
    api.post('/settings/api-keys', data),
  deleteApiKey: (id: string) => api.delete(`/settings/api-keys/${id}`),
  listIntegrations: () => api.get('/settings/integrations'),
  connectIntegration: (service: string, code: string) =>
    api.post(`/settings/integrations/${service}/connect`, { oauth_code: code }),
  disconnectIntegration: (service: string) =>
    api.delete(`/settings/integrations/${service}`),
}

// ── AI ───────────────────────────────────────────────────────────────

export const aiApi = {
  getProviders: () => api.get('/ai/providers'),
  getModels: (provider: string) => api.get(`/ai/providers/${provider}/models`),
}
