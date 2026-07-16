import { api } from './http'
import type {
  Agent,
  AgentCreate,
  AgentUpdate,
} from '@/shared/types/entities'

export interface ListAgentsParams {
  skip?: number
  limit?: number
  q?: string
}

export async function fetchAgents(params: ListAgentsParams = {}) {
  const { data } = await api.get<Agent[]>('/agents/', { params })
  return data
}

export const listAgents = fetchAgents

export async function createAgent(payload: AgentCreate) {
  const { data } = await api.post<Agent>('/agents/', payload)
  return data
}

export async function updateAgent(agentId: string, payload: AgentUpdate) {
  const { data } = await api.patch<Agent>(`/agents/${agentId}`, payload)
  return data
}

export async function deleteAgent(agentId: string) {
  await api.delete(`/agents/${agentId}`)
}