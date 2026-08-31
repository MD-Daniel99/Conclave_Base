import { api } from './http'
import type { ClientDocument, ContractGenerationPayload } from '@/shared/types/entities'

export type ContractTemplateOption = {
  value: string
  label: string
}

export type MtzTemplateOption = {
  value: string
  label: string
  tsr_code: string
}

export type MtzGenerationPayload = {
  template_type: string
  mtz_number: string
  document_date: string
  disability_group_reason: string
  certificate_reference: string
  diagnosis: string
  amputation_level: string
  weight_kg: string
}

export async function fetchContractTemplates() {
  const { data } = await api.get<ContractTemplateOption[]>('/documents/contract_templates')
  return data
}

export async function fetchNextContractNumber() {
  const { data } = await api.get<{ number: string }>('/documents/contracts/next_number')
  return data.number
}

export async function fetchMtzTemplates() {
  const { data } = await api.get<MtzTemplateOption[]>('/documents/mtz_templates')
  return data
}

export async function fetchClientDocuments(clientId: string) {
  const { data } = await api.get<ClientDocument[]>(`/documents/clients/${clientId}/list`)
  return data
}

export async function uploadClientDocument(clientId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post<ClientDocument>(`/documents/clients/${clientId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteDocument(documentId: string) {
  await api.delete(`/documents/${documentId}`)
}

export async function generateClientContract(clientId: string, payload: ContractGenerationPayload) {
  const { data } = await api.post<ClientDocument>(`/documents/clients/${clientId}/generate_contract`, payload)
  return data
}

export async function generateClientMtz(clientId: string, payload: MtzGenerationPayload) {
  const { data } = await api.post<ClientDocument>(`/documents/clients/${clientId}/generate_mtz`, payload)
  return data
}

export async function downloadDocumentBlob(documentId: string) {
  const response = await api.get(`/documents/download/${documentId}`, { responseType: 'blob' })
  return {
    blob: response.data as Blob,
    contentDisposition: String(response.headers['content-disposition'] ?? ''),
  }
}
