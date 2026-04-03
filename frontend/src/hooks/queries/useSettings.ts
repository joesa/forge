/**
 * TanStack Query hooks for Settings API.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

function shouldRetrySettingsQuery(failureCount: number, error: unknown): boolean {
  const err = error as { response?: { status?: number } } | null
  if (err?.response?.status === 401) return false
  return failureCount < 1
}

function useSettingsQueryEnabled(): boolean {
  return useAuthStore((s) => s.isAuthenticated())
}

export function useProfile() {
  const enabled = useSettingsQueryEnabled()
  return useQuery({
    queryKey: ['settings', 'profile'],
    queryFn: () => settingsApi.getProfile().then((r) => r.data),
    enabled,
    retry: shouldRetrySettingsQuery,
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { display_name?: string; avatar_url?: string; timezone?: string }) =>
      settingsApi.updateProfile(data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'profile'] }) },
  })
}

export function useProviders() {
  const enabled = useSettingsQueryEnabled()
  return useQuery({
    queryKey: ['settings', 'providers'],
    queryFn: () => settingsApi.listProviders().then((r) => r.data),
    enabled,
    retry: shouldRetrySettingsQuery,
  })
}

export function useCreateProvider() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { provider_name: string; api_key: string; base_url?: string }) =>
      settingsApi.createProvider(data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'providers'] }) },
  })
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (id: string) => settingsApi.testProvider(id).then((r) => r.data),
  })
}

export function useDeleteProvider() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => settingsApi.deleteProvider(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'providers'] }) },
  })
}

export function useModelRouting() {
  const enabled = useSettingsQueryEnabled()
  return useQuery({
    queryKey: ['settings', 'model-routing'],
    queryFn: () => settingsApi.getModelRouting().then((r) => r.data),
    enabled,
    retry: shouldRetrySettingsQuery,
  })
}

export function useUpdateModelRouting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (rules: Array<{ stage: string; provider: string; model: string }>) =>
      settingsApi.updateModelRouting(rules).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'model-routing'] }) },
  })
}

export function useApiKeys() {
  const enabled = useSettingsQueryEnabled()
  return useQuery({
    queryKey: ['settings', 'api-keys'],
    queryFn: () => settingsApi.listApiKeys().then((r) => r.data),
    enabled,
    retry: shouldRetrySettingsQuery,
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; expires_in_days?: number }) =>
      settingsApi.createApiKey(data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'api-keys'] }) },
  })
}

export function useDeleteApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => settingsApi.deleteApiKey(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings', 'api-keys'] }) },
  })
}

export function useIntegrations() {
  const enabled = useSettingsQueryEnabled()
  return useQuery({
    queryKey: ['settings', 'integrations'],
    queryFn: () => settingsApi.listIntegrations().then((r) => r.data),
    enabled,
    retry: shouldRetrySettingsQuery,
  })
}
