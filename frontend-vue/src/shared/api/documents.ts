import { api } from './http'
import type { ClientDocument, ContractGenerationPayload } from '@/shared/types/entities'


export type ContractTemplateOption = {
  value: string
  label: string
}

export async function fetchContractTemplates() {
  const { data } = await api.get<ContractTemplateOption[]>('/documents/contract_templates')
  return data
}

export async function fetchClientDocuments(clientId: string) {
  const { data } = await api.get<ClientDocument[]>(`/documents/clients/${clientId}/list`)
  return data
}

export async function uploadClientDocument(clientId: string, file: File) {
  const form = new FormData()
  form.append('file', file)

  const { data } = await api.post<ClientDocument>(`/documents/clients/${clientId}/upload`, form)
  return data
}

export async function deleteDocument(documentId: string) {
  await api.delete(`/documents/${documentId}`)
}

export async function generateClientContract(clientId: string, payload: ContractGenerationPayload) {
  const { data } = await api.post<ClientDocument>(`/documents/clients/${clientId}/generate_contract`, payload)
  return data
}

export async function downloadDocumentBlob(documentId: string) {
  const { data, headers } = await api.get<Blob>(`/documents/download/${documentId}`, {
    responseType: 'blob',
  })

  return {
    blob: data,
    contentDisposition: headers['content-disposition'] as string | undefined,
  }
}
