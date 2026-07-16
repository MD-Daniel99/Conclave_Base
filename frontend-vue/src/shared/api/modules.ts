import { api } from './http'
import type { ModuleCreatePayload, ModuleItem, ModuleUpdatePayload } from '@/shared/types/entities'

export interface ListModulesParams {
  skip?: number
  limit?: number
  q?: string
  supplier?: string
  client_id?: string
  unassigned?: boolean
}

export async function fetchModules(params: ListModulesParams = {}) {
  const { data } = await api.get<ModuleItem[]>('/modules/', { params })
  return data
}

export async function createModule(payload: ModuleCreatePayload) {
  const { data } = await api.post<ModuleItem>('/modules/', payload)
  return data
}

export async function updateModule(moduleId: string, payload: ModuleUpdatePayload) {
  const { data } = await api.patch<ModuleItem>(`/modules/${moduleId}`, payload)
  return data
}

export async function deleteModule(moduleId: string) {
  await api.delete(`/modules/${moduleId}`)
}
