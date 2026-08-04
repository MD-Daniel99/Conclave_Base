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
