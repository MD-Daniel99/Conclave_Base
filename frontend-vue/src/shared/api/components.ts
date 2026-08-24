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

export async function updateComponent(
  componentId: string,
  payload: ComponentUpdatePayload,
  operationQuantity?: number,
) {
  const { data } = await api.patch<ComponentItem>(`/components/${componentId}`, payload, {
    params: operationQuantity ? { operation_quantity: operationQuantity } : undefined,
  })
  return data
}

export async function archiveComponent(componentId: string, quantity = 1) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/archive`, undefined, { params: { quantity } })
  return data
}

export async function restoreComponent(componentId: string, quantity = 1) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/restore`, undefined, { params: { quantity } })
  return data
}

export async function moveComponentToStock(componentId: string, quantity = 1) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/stock`, undefined, { params: { quantity } })
  return data
}

export async function moveComponentToWorkStock(componentId: string, quantity = 1) {
  const { data } = await api.post<ComponentItem>(`/components/${componentId}/work-stock`, undefined, { params: { quantity } })
  return data
}

export async function deleteComponent(componentId: string, quantity = 1) {
  await api.delete(`/components/${componentId}`, { params: { quantity } })
}
