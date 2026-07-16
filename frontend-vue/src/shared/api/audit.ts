import { api } from './http'
import type { AuditLogItem } from '@/shared/types/entities'

export async function fetchEntityAudit(entity: string, entityId: string) {
  const { data } = await api.get<AuditLogItem[]>(`/audit/entity/${entity}/${entityId}`)
  return data
}

export async function fetchRecentAudit(limit = 30) {
  const { data } = await api.get<AuditLogItem[]>('/audit/recent', {
    params: { limit },
  })
  return data
}
