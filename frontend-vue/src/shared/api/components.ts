import { api } from './http'
import type { ComponentCreatePayload, ComponentItem, ComponentUpdatePayload } from '@/shared/types/entities'

export interface ListComponentsParams {
  skip?: number
  limit?: number
  q?: string
  supplier?: string
  client_id?: string
  unassigned?: boolean
  archived?: boolean
  in_stock?: boolean
}

export async function fetchComponents(params: ListComponentsParams = {}) {
  const { data } = await api.get<ComponentItem[]>('/components/', { params })
  return data
}

export async function fetchStockComponentCount() {
  const { data } = await api.get<number>('/components/stock/count')
  return data
}

export async function createComponent(payload: ComponentCreatePayload) {
  const { data } = await api.post<ComponentItem>('/components/', payload)
  return data
}

export async function updateComponent(componentId: string, payload: ComponentUpdatePayload) {
  const { data } = await api.patch<ComponentItem>(`/components/${componentId}`, payload)
  return data
}

export async function archiveComponent(componentId: string) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/archive`)
  return data
}

export async function restoreComponent(componentId: string) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/restore`)
  return data
}

export async function moveComponentToStock(componentId: string) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/stock`)
  return data
}

export async function moveComponentToWorkStock(componentId: string) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/work-stock`)
  return data
}

export async function deleteComponent(componentId: string) {
  await api.delete(`/components/${componentId}`)
}
