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
  builtin?: boolean
  pdf_transcribed?: boolean
  revision?: number
}

export type MtzConclusionItem = { template_type: string; amputation_level: string; amputation_code?: string; extra_fields?: Record<string,string> }

export type MtzCustomField = {
  key: string; label: string; kind: 'text' | 'select' | 'auto'
  scope: 'shared' | 'per_item'; required: boolean; placeholder: string
  options?: string[]; source?: string
}
export type MtzFieldSettings = { label: string; options?: string[]; placeholder?: string; source?: string; default?: string }
export type MtzFormConfig = {
  version: number
  auto: Record<string, MtzFieldSettings>
  manual: Record<string, MtzFieldSettings>
  codes: { activity_level: Record<string,string> }
  custom_fields: MtzCustomField[]
}
export type MtzTemplateCell = { col: number; text: string }
export type MtzTemplateRow = { source_index: number | null; clone_from?: number; cells: MtzTemplateCell[] }
export type MtzTemplateEditor = {
  value: string; title: string; tsr_code: string; builtin: boolean; revision: number
  history: { revision: number; label: string }[]; rows: MtzTemplateRow[]
}

export type MtzGenerationPayload = {
  items: MtzConclusionItem[]
  disability_group_reason: string
  diagnoses: string[]
  stump_condition: string
  activity_level: string
  weight_kg: string
  extra_fields?: Record<string,string>
}

export async function fetchMtzConfig() {
  const { data } = await api.get<MtzFormConfig>('/documents/mtz_templates/config')
  return data
}
export async function saveMtzConfig(config: MtzFormConfig) {
  const { data } = await api.put<MtzFormConfig>('/documents/mtz_templates/config', config)
  return data
}
export async function fetchMtzTemplateEditor(key: string) {
  const { data } = await api.get<MtzTemplateEditor>(`/documents/mtz_templates/${encodeURIComponent(key)}/editor`)
  return data
}
export async function saveMtzTemplateEditor(key: string, edit: MtzTemplateEditor) {
  const { data } = await api.put<MtzTemplateEditor>(`/documents/mtz_templates/${encodeURIComponent(key)}/editor`, edit)
  return data
}
export async function restoreMtzTemplateEditor(key: string, targetRevision: number, expectedRevision: number) {
  const { data } = await api.post<MtzTemplateEditor>(`/documents/mtz_templates/${encodeURIComponent(key)}/restore`, {
    target_revision: targetRevision, expected_revision: expectedRevision,
  })
  return data
}

export async function fetchContractTemplates() {
  const { data } = await api.get<ContractTemplateOption[]>('/documents/contract_templates')
  return data
}

export async function fetchNextContractNumber(templateType: string = 'llc_contract') {
  const { data } = await api.get<{ number: string }>('/documents/contracts/next_number', { params: { template_type: templateType } })
  return data.number
}

export async function fetchMtzTemplates() {
  const { data } = await api.get<MtzTemplateOption[]>('/documents/mtz_templates')
  return data
}

export async function uploadMtzTemplate(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post<MtzTemplateOption[]>('/documents/mtz_templates/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function downloadMtzTemplate(templateKey: string) {
  const { data } = await api.get(`/documents/mtz_templates/${encodeURIComponent(templateKey)}/download`, { responseType: 'blob' })
  return data as Blob
}

export async function deleteMtzTemplate(templateKey: string) {
  await api.delete(`/documents/mtz_templates/${encodeURIComponent(templateKey)}`)
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

export async function updateDocumentStatus(documentId: string, payload: { contract_status?: string | null; act_status?: string | null }) {
  const { data } = await api.patch<ClientDocument>(`/documents/${documentId}/status`, payload)
  return data
}
