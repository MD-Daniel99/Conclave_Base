import { api } from './http'
import type {
  Client,
  ClientCreatePayload,
  ClientPassport,
  ClientPassportCreate,
  ClientPassportUpdate,
  ClientPhone,
  ClientPhoneCreate,
  ClientPhoneUpdate,
  ClientSnils,
  ClientSnilsCreate,
  ClientSnilsUpdate,
  ClientUpdatePayload,
  ClientTsr,
  ModuleItem,
} from '@/shared/types/entities'

export interface ListClientsParams {
  skip?: number
  limit?: number
  q?: string
  status?: string
  agent_id?: string
  current_stage?: string
  archived?: boolean
}

export async function fetchClients(params: ListClientsParams = {}) {
  const { data } = await api.get<Client[]>('/clients/', { params })
  return data
}

export async function fetchClient(clientId: string) {
  const { data } = await api.get<Client>(`/clients/${clientId}`)
  return data
}

export async function createClient(payload: ClientCreatePayload) {
  const { data } = await api.post<Client>('/clients/', payload)
  return data
}

export async function updateClient(clientId: string, payload: ClientUpdatePayload) {
  const { data } = await api.patch<Client>(`/clients/${clientId}`, payload)
  return data
}

export async function deleteClient(clientId: string) {
  await api.delete(`/clients/${clientId}`)
}

export async function archiveClient(clientId: string) {
  const { data } = await api.post<Client>(`/clients/${clientId}/archive`)
  return data
}

export async function restoreClient(clientId: string) {
  const { data } = await api.post<Client>(`/clients/${clientId}/restore`)
  return data
}

export async function assignClientComponentsTsr(
  clientId: string,
  payload: { component_ids: string[]; tsr_id: string },
) {
  await api.patch(`/clients/${clientId}/components/tsr`, payload)
}


export async function setClientComponentsProsthetistState(
  clientId: string,
  payload: {
    client_tsr_id: string
    component_ids: string[]
    at_prosthetist: boolean
  },
) {
  const { data } = await api.patch<ModuleItem[]>(`/clients/${clientId}/components/prosthetist`, payload)
  return data
}


export async function fetchClientTsr(clientId: string) {
  const { data } = await api.get<ClientTsr[]>(`/clients/${clientId}/tsr`)
  return data
}

export async function attachClientTsr(
  clientId: string,
  payload: {
    tsr_id: string
    check_date?: string | null
    certificate_price?: string | null
    prosthetist?: 'Дмитрий' | 'Никита' | null
    repeat_visit_date?: string | null
  },
) {
  const { data } = await api.post<ClientTsr>(`/clients/${clientId}/tsr`, payload)
  return data
}

export async function updateClientTsr(
  clientId: string,
  clientTsrId: string,
  payload: {
    check_date?: string | null
    certificate_price?: string | null
    prosthetist?: 'Дмитрий' | 'Никита' | null
    repeat_visit_date?: string | null
  },
) {
  const { data } = await api.patch<ClientTsr>(`/clients/${clientId}/tsr/${clientTsrId}`, payload)
  return data
}

export async function detachClientTsr(clientId: string, clientTsrId: string) {
  await api.delete(`/clients/${clientId}/tsr/${clientTsrId}`)
}

export async function fetchClientPhones(clientId: string) {
  const { data } = await api.get<ClientPhone[]>(`/clients/${clientId}/phones`)
  return data
}

export async function createClientPhone(clientId: string, payload: ClientPhoneCreate) {
  const { data } = await api.post<ClientPhone>(`/clients/${clientId}/phones`, payload)
  return data
}

export async function updateClientPhone(phoneId: string | number, payload: ClientPhoneUpdate) {
  const { data } = await api.patch<ClientPhone>(`/phones/${phoneId}`, payload)
  return data
}

export async function deleteClientPhone(phoneId: string | number) {
  await api.delete(`/phones/${phoneId}`)
}

export async function createClientPassport(clientId: string, payload: ClientPassportCreate) {
  const { data } = await api.post<ClientPassport>(`/clients/${clientId}/passports`, payload)
  return data
}

export async function updateClientPassport(passportId: string, payload: ClientPassportUpdate) {
  const { data } = await api.patch<ClientPassport>(`/passports/${passportId}`, payload)
  return data
}

export async function deleteClientPassport(passportId: string) {
  await api.delete(`/passports/${passportId}`)
}

export async function createClientSnils(clientId: string, payload: ClientSnilsCreate) {
  const { data } = await api.post<ClientSnils>(`/clients/${clientId}/snils`, payload)
  return data
}

export async function updateClientSnils(snilsId: string, payload: ClientSnilsUpdate) {
  const { data } = await api.patch<ClientSnils>(`/snils/${snilsId}`, payload)
  return data
}

export async function deleteClientSnils(snilsId: string) {
  await api.delete(`/snils/${snilsId}`)
}
