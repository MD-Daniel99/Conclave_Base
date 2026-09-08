import { api } from './http'
import type {
  AccountingCustomField,
  AccountingReport,
  ClientContractCoverage,
  ContractAccountingReport,
} from '@/shared/types/entities'

export interface UpdateAccountingValue {
  field_id: string
  value: string | number | null
}

export interface AccountingReportParams {
  start_date?: string | null
  end_date?: string | null
  hide_failed?: boolean
  // tax_percent поддерживает старые backend-сборки.
  tax_percent?: number
  tax_usn_percent?: number
  tax_osno_percent?: number
  acquiring_percent?: number
  vat_percent?: number
}

export async function fetchAccountingCustomFields() {
  const { data } = await api.get<AccountingCustomField[]>('/accounting/custom-fields')
  return data
}

export async function createAccountingCustomField(payload: { field_name: string; field_type: 'number' | 'text' }) {
  const { data } = await api.post<AccountingCustomField>('/accounting/custom-fields', payload)
  return data
}

export async function deleteAccountingCustomField(fieldId: string) {
  await api.delete(`/accounting/custom-fields/${fieldId}`)
}

export async function updateClientAccountingValues(clientId: string, values: UpdateAccountingValue[]) {
  const { data } = await api.patch(`/accounting/clients/${clientId}/custom-values`, { values })
  return data
}

export async function fetchAccountingReport(params: AccountingReportParams = {}) {
  const { data } = await api.get<AccountingReport>('/accounting/report', { params })
  return data
}

export async function fetchContractAccountingReport(params: AccountingReportParams = {}) {
  const { data } = await api.get<ContractAccountingReport>('/accounting/contracts', { params })
  return data
}

export async function fetchClientContractCoverage() {
  const { data } = await api.get<ClientContractCoverage[]>('/accounting/contract-coverage')
  return data
}

export async function updateContractAccounting(documentId: string, payload: Record<string, unknown>) {
  const { data } = await api.patch(`/accounting/contracts/${documentId}`, payload)
  return data
}


export interface AccountingExpenseEntry {
  id: string
  amount: number
  description: string
  created_at?: string | null
  user_id?: string | null
  username?: string | null
  paid?: boolean | null
}

export interface AccountingExpenseHistory {
  field_key: string
  total: number
  paid: boolean
  entries: AccountingExpenseEntry[]
}

export async function fetchClientExpenseHistory(clientId: string, fieldKey: string) {
  const { data } = await api.get<AccountingExpenseHistory>(`/accounting/clients/${clientId}/expenses/${encodeURIComponent(fieldKey)}`)
  return data
}

export async function addClientExpense(clientId: string, payload: { field_key: string; amount: number; description: string; paid?: boolean }) {
  const { data } = await api.post<AccountingExpenseHistory>(`/accounting/clients/${clientId}/expenses`, payload)
  return data
}

export async function updateClientExpenseStatus(clientId: string, fieldKey: string, paid: boolean) {
  const { data } = await api.patch<AccountingExpenseHistory>(`/accounting/clients/${clientId}/expenses/${encodeURIComponent(fieldKey)}/status`, { paid })
  return data
}

export async function updateClientExpense(
  clientId: string,
  fieldKey: string,
  entryId: string,
  payload: { amount: number; description: string; paid?: boolean },
) {
  const { data } = await api.patch<AccountingExpenseHistory>(
    `/accounting/clients/${clientId}/expenses/${encodeURIComponent(fieldKey)}/${encodeURIComponent(entryId)}`,
    payload,
  )
  return data
}

export async function deleteClientExpense(clientId: string, fieldKey: string, entryId: string) {
  const { data } = await api.delete<AccountingExpenseHistory>(
    `/accounting/clients/${clientId}/expenses/${encodeURIComponent(fieldKey)}/${encodeURIComponent(entryId)}`,
  )
  return data
}

export async function fetchContractExpenseHistory(documentId: string, fieldKey: string) {
  const { data } = await api.get<AccountingExpenseHistory>(`/accounting/contracts/${documentId}/expenses/${encodeURIComponent(fieldKey)}`)
  return data
}

export async function addContractExpense(
  documentId: string,
  payload: { field_key: string; amount: number; description: string; paid?: boolean },
) {
  const { data } = await api.post<AccountingExpenseHistory>(`/accounting/contracts/${documentId}/expenses`, payload)
  return data
}

export async function updateContractExpenseStatus(documentId: string, fieldKey: string, paid: boolean) {
  const { data } = await api.patch<AccountingExpenseHistory>(
    `/accounting/contracts/${documentId}/expenses/${encodeURIComponent(fieldKey)}/status`,
    { paid },
  )
  return data
}

export async function updateContractExpense(
  documentId: string,
  fieldKey: string,
  entryId: string,
  payload: { amount: number; description: string; paid?: boolean },
) {
  const { data } = await api.patch<AccountingExpenseHistory>(
    `/accounting/contracts/${documentId}/expenses/${encodeURIComponent(fieldKey)}/${encodeURIComponent(entryId)}`,
    payload,
  )
  return data
}

export async function deleteContractExpense(documentId: string, fieldKey: string, entryId: string) {
  const { data } = await api.delete<AccountingExpenseHistory>(
    `/accounting/contracts/${documentId}/expenses/${encodeURIComponent(fieldKey)}/${encodeURIComponent(entryId)}`,
  )
  return data
}
