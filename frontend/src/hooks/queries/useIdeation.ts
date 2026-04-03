/**
 * TanStack Query hooks for Ideation API.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ideationApi } from '@/lib/api'

export function useStartQuestionnaire() {
  return useMutation({
    mutationFn: () => ideationApi.startQuestionnaire().then((r) => r.data),
  })
}

export function useQuestionnaire(id: string) {
  return useQuery({
    queryKey: ['ideation', 'questionnaire', id],
    queryFn: () => ideationApi.getQuestionnaire(id).then((r) => r.data),
    enabled: !!id,
  })
}

export function useAnswerQuestion(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { question_index: number; answer: unknown }) =>
      ideationApi.answerQuestion(id, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ideation', 'questionnaire', id] }) },
  })
}

export function useSkipQuestion(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => ideationApi.skipQuestion(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ideation', 'questionnaire', id] }) },
  })
}

export function useCompleteQuestionnaire(id: string) {
  return useMutation({
    mutationFn: () => ideationApi.completeQuestionnaire(id).then((r) => r.data),
  })
}

export function useIdeas(sessionId: string) {
  return useQuery({
    queryKey: ['ideation', 'ideas', sessionId],
    queryFn: () => ideationApi.getIdeas(sessionId).then((r) => r.data),
    enabled: !!sessionId,
  })
}

export function useSaveIdea() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => ideationApi.saveIdea(id).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['ideation'] }) },
  })
}

export function useSelectIdea() {
  return useMutation({
    mutationFn: (id: string) => ideationApi.selectIdea(id).then((r) => r.data),
  })
}

export function useGenerateDirect() {
  return useMutation({
    mutationFn: () => ideationApi.generateDirect().then((r) => r.data),
  })
}

export function useEnhancePrompt() {
  return useMutation({
    mutationFn: (prompt: string) => ideationApi.enhancePrompt(prompt).then((r) => r.data),
  })
}
