/**
 * TanStack Query hooks for Projects API.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then((r) => r.data),
  })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => projectsApi.get(id).then((r) => r.data),
    enabled: !!id,
  })
}

export function useProjectBuilds(id: string) {
  return useQuery({
    queryKey: ['projects', id, 'builds'],
    queryFn: () => projectsApi.listBuilds(id).then((r) => r.data),
    enabled: !!id,
  })
}

export function useProjectDeployments(id: string) {
  return useQuery({
    queryKey: ['projects', id, 'deployments'],
    queryFn: () => projectsApi.listDeployments(id).then((r) => r.data),
    enabled: !!id,
  })
}

export function useProjectFiles(id: string) {
  return useQuery({
    queryKey: ['projects', id, 'files'],
    queryFn: () => projectsApi.getFiles(id).then((r) => r.data),
    enabled: !!id,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description: string; framework: string; prompt?: string }) =>
      projectsApi.create(data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }) },
  })
}

export function useUpdateProject(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      projectsApi.update(id, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects', id] }) },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => projectsApi.delete(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }) },
  })
}

export function useDeployProject(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => projectsApi.deploy(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects', id, 'deployments'] }) },
  })
}
