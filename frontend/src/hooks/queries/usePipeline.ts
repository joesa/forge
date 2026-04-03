/**
 * TanStack Query hooks for Pipeline + Build APIs.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pipelineApi, buildApi } from '@/lib/api'

// ── Pipeline ─────────────────────────────────────────────────────────
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function isUuid(value: string): boolean {
  return UUID_RE.test(value)
}

export function usePipelineStatus(id: string) {
  const validId = isUuid(id)

  return useQuery({
    queryKey: ['pipeline', id, 'status'],
    queryFn: () => pipelineApi.getStatus(id).then((r) => r.data),
    enabled: validId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed' || status === 'error') return false
      // Stop polling on terminal HTTP errors — no point hammering a rejected endpoint
      const err = query.state.error as { response?: { status?: number } } | null
      const errStatus = err?.response?.status
      if (errStatus === 401 || errStatus === 422 || errStatus === 404) return false
      return 3000
    },
    retry: (failureCount, error) => {
      const err = error as { response?: { status?: number } } | null
      const errStatus = err?.response?.status
      if (errStatus === 401 || errStatus === 422 || errStatus === 404) return false
      return failureCount < 1
    },
  })
}

export function usePipelineStages(id: string) {
  const validId = isUuid(id)

  return useQuery({
    queryKey: ['pipeline', id, 'stages'],
    queryFn: () => pipelineApi.getStages(id).then((r) => r.data),
    enabled: validId,
    refetchInterval: 3000,
  })
}

export function useRunPipeline() {
  return useMutation({
    mutationFn: (data: { project_id: string; idea_spec?: Record<string, unknown> }) =>
      pipelineApi.run(data).then((r) => r.data),
  })
}

export function useCancelPipeline(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => pipelineApi.cancel(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['pipeline', id] }) },
  })
}

// ── Build ────────────────────────────────────────────────────────────

export function useBuildStatus(id: string) {
  return useQuery({
    queryKey: ['build', id, 'status'],
    queryFn: () => buildApi.getStatus(id).then((r) => r.data),
    enabled: !!id,
    refetchInterval: 3000,
  })
}

export function useBuildLogs(id: string) {
  return useQuery({
    queryKey: ['build', id, 'logs'],
    queryFn: () => buildApi.getLogs(id).then((r) => r.data),
    enabled: !!id,
    refetchInterval: 5000,
  })
}

export function useStartBuild() {
  return useMutation({
    mutationFn: (data: { project_id: string; pipeline_id?: string; incremental?: boolean }) =>
      buildApi.start(data).then((r) => r.data),
  })
}

export function useCancelBuild(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reason?: string) => buildApi.cancel(id, reason).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['build', id] }) },
  })
}

export function useRetryBuild(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (fromAgent?: number) => buildApi.retry(id, fromAgent).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['build', id] }) },
  })
}
