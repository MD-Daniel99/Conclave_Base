import { api } from './http'
import type { ReferenceItem } from '@/shared/types/entities'

export async function fetchStatuses() {
  const { data } = await api.get<ReferenceItem[]>('/status/')
  return data
}

export async function createStatus(payload: Partial<ReferenceItem>) {
  const { data } = await api.post<ReferenceItem>('/status/', payload)
  return data
}

export async function fetchStages() {
  const { data } = await api.get<ReferenceItem[]>('/stages/')
  return data
}

export async function createStage(payload: Partial<ReferenceItem>) {
  const { data } = await api.post<ReferenceItem>('/stages/', payload)
  return data
}

export async function fetchTsrReferences() {
  const { data } = await api.get<ReferenceItem[]>('/references/tsr')
  return data
}

export async function createTsrReference(payload: Partial<ReferenceItem>) {
  const { data } = await api.post<ReferenceItem>('/references/tsr', payload)
  return data
}

export async function updateTsrReference(tsrId: string | number, payload: Partial<ReferenceItem>) {
  const { data } = await api.put<ReferenceItem>(`/references/tsr/${tsrId}`, payload)
  return data
}

export async function deleteTsrReference(tsrId: string | number) {
  await api.delete(`/references/tsr/${tsrId}`)
}

export async function fetchProsthesisReferences() {
  const { data } = await api.get<ReferenceItem[]>('/references/prosthesis')
  return data
}

export async function createProsthesisReference(payload: Partial<ReferenceItem>) {
  const { data } = await api.post<ReferenceItem>('/references/prosthesis', payload)
  return data
}

export async function updateProsthesisReference(prosthesisId: string | number, payload: Partial<ReferenceItem>) {
  const { data } = await api.put<ReferenceItem>(`/references/prosthesis/${prosthesisId}`, payload)
  return data
}

export async function deleteProsthesisReference(prosthesisId: string | number) {
  await api.delete(`/references/prosthesis/${prosthesisId}`)
}

export async function fetchNameIndexReferences() {
  const { data } = await api.get<ReferenceItem[]>('/references/name_index')
  return data
}

export async function createNameIndexReference(payload: Partial<ReferenceItem>) {
  const { data } = await api.post<ReferenceItem>('/references/name_index', payload)
  return data
}

export async function deleteNameIndexReference(moduleId: string | number) {
  await api.delete(`/references/name_index/${moduleId}`)
}
