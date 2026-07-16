import { api } from './http'
import type { ModuleComponentItem, ModuleComponentPayload } from '@/shared/types/entities'

export async function fetchComponents(params: Record<string, unknown> = {}) {
  const { data } = await api.get<ModuleComponentItem[]>('/components/', { params })
  return data
}

export async function createComponent(payload: ModuleComponentPayload) {
  const { data } = await api.post<ModuleComponentItem>('/components/', payload)
  return data
}

export async function updateComponent(componentId: string, payload: Partial<ModuleComponentPayload>) {
  const { data } = await api.patch<ModuleComponentItem>(`/components/${componentId}`, payload)
  return data
}

export async function deleteComponent(componentId: string) {
  await api.delete(`/components/${componentId}`)
}
