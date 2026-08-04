import type {
  AccountingCustomFieldRead,
  AgentRead,
  AgentCreate,
  AgentUpdate,
  AgentSummary,
  AuditLogRead,
  ClientRead,
  ClientCreate,
  ClientUpdate,
  ContractGeneration,
  DocumentRead,
  ModuleCreate,
  ModuleNameIndexRead,
  ModuleRead,
  ModuleUpdate,
  PassportCreate,
  PassportRead,
  PassportUpdate,
  PhoneCreate,
  PhoneRead,
  PhoneUpdate,
  ProsthesisRefRead,
  SnilsCreate,
  SnilsRead,
  SnilsUpdate,
  StageRead,
  StatusRead,
  TstCodeRefRead,
} from '@/shared/api/generated/types.gen'

export type Agent = AgentRead
export interface ClientTsr {
  client_tsr_id: string
  client_id: string
  tsr_id: string
  check_date?: string | null
  certificate_price?: string | null
  prosthetist?: 'Дмитрий' | 'Никита' | null
  place_of_residence?: string | null
  repeat_visit_date?: string | null
  tsr: {
    id?: string
    tsr_id?: string
    full_tsr_code?: string | null
  }
  created_at?: string | null
  updated_at?: string | null
}

export type Client = Omit<ClientRead, 'modules' | 'tsr_items'> & {
  prosthetist?: string | null
  is_archived?: boolean
  taxation_system?: 'УСН' | 'ОСНО'
  prosthetist_work?: number | null
  patient_travel?: number | null
  patient_accommodation?: number | null
  patient_meals?: number | null
  patient_payment?: number | null
  other_expenses?: number | null
  agency_expenses?: number | null
  modules?: ComponentItem[]
  tsr_items?: ClientTsr[]
}
export type ClientPhone = PhoneRead
export type ClientPhoneCreate = PhoneCreate
export type ClientPhoneUpdate = PhoneUpdate
export type ClientPassport = PassportRead
export type ClientPassportCreate = PassportCreate
export type ClientPassportUpdate = PassportUpdate
export type ClientSnils = SnilsRead
export type ClientSnilsCreate = SnilsCreate
export type ClientSnilsUpdate = SnilsUpdate
export type ClientCreatePayload = ClientCreate & {
  prosthetist?: string | null
  taxation_system?: 'УСН' | 'ОСНО'
}
export type ClientUpdatePayload = ClientUpdate & {
  prosthetist?: string | null
  taxation_system?: 'УСН' | 'ОСНО'
  prosthetist_work?: number | null
  patient_travel?: number | null
  patient_accommodation?: number | null
  patient_meals?: number | null
  patient_payment?: number | null
  other_expenses?: number | null
  agency_expenses?: number | null
}
export type ClientDocument = DocumentRead
export type ContractGenerationPayload = ContractGeneration & {
  selected_client_tsr_ids?: string[]
  selected_tsr_ids?: string[]
}
export type ComponentItem = ModuleRead & {
  is_archived?: boolean
  is_manually_archived?: boolean
}
export type ComponentCreatePayload = ModuleCreate
export type ComponentUpdatePayload = ModuleUpdate
// Внутренние имена API сохранены для совместимости со схемой БД.
export type ModuleItem = ComponentItem
export type ModuleCreatePayload = ModuleCreate
export type ModuleUpdatePayload = ModuleUpdate
export type AuditLogItem = AuditLogRead

export type {
  AgentCreate,
  AgentUpdate,
  AgentRead,
  AgentSummary,
  AccountingCustomFieldRead,
  ClientCreate,
  ClientRead,
  ClientUpdate,
  ContractGeneration,
  DocumentRead,
  ModuleCreate,
  ModuleRead,
  ModuleUpdate,
  PassportCreate,
  PassportRead,
  PassportUpdate,
  PhoneCreate,
  PhoneRead,
  PhoneUpdate,
  SnilsCreate,
  SnilsRead,
  SnilsUpdate,
  StageRead,
  StatusRead,
  TstCodeRefRead,
}

export type ReferenceItem = Partial<
  StatusRead & StageRead & TstCodeRefRead & ProsthesisRefRead & ModuleNameIndexRead
> & {
  id?: string | number
  prosthesis_id?: string | number
  tsr_id?: string | number
  name_index_id?: string | number
  code?: string
  name?: string | null
  status_code?: string
  stage_code?: string
  full_tsr_code?: string | null
  name_index?: string | null
  description?: string
  title?: string
  [key: string]: unknown
}

export interface AccountingCustomField extends Partial<AccountingCustomFieldRead> {
  id?: string
  name?: string
  label?: string
  title?: string
  type?: string
  [key: string]: unknown
}

export interface AccountingReportClient {
  client_id?: string | null
  external_id?: number
  full_name: string
  status?: string | null
  current_stage?: string | null
  agent_id?: string | null
  date?: string | null
  taxation_system?: 'УСН' | 'ОСНО'
}

export interface AccountingReportAmounts {
  revenue: number
  cost: number
  salary: number
  custom_expenses: number
  vat: number
  tax: number
  acquiring: number
  profit: number
}

export interface AccountingReportField {
  key: string
  label: string
  type: string
}

export interface AccountingReportRow {
  client: AccountingReportClient
  amounts: AccountingReportAmounts
  custom_values: Record<string, number>
}

export interface AccountingReport {
  filters: {
    start_date?: string | null
    end_date?: string | null
    hide_failed: boolean
    tax_percent: number
    tax_usn_percent?: number
    tax_osno_percent?: number
    acquiring_percent: number
    vat_percent?: number
  }
  custom_fields: AccountingReportField[]
  rows: AccountingReportRow[]
  totals: AccountingReportAmounts
}

export interface ContractAccountingAmounts {
  certificate: number
  certificate_original?: number
  certificate_remaining?: number
  modules_cost: number
  prosthetist_work: number
  patient_travel: number
  patient_accommodation: number
  patient_meals: number
  patient_payment: number
  other_expenses: number
  agency_expenses: number
  custom_expenses: number
  vat: number
  tax: number
  tax_percent?: number
  acquiring: number
  profit: number
  applies_percentage_expenses?: boolean
  contract_index?: number
  contract_count?: number
}

export interface ContractAccountingRow {
  document: {
    document_id: string
    filename: string
    document_number?: string | null
    document_type?: string | null
    date?: string | null
    created_at?: string | null
  }
  client: {
    client_id: string
    full_name: string
    short_name: string
    status?: string | null
    current_stage?: string | null
    taxation_system?: 'УСН' | 'ОСНО'
  }
  amounts: ContractAccountingAmounts
  custom_values: Record<string, string | number>
}

export interface ContractAccountingReport {
  custom_fields: AccountingReportField[]
  rows: ContractAccountingRow[]
  totals: ContractAccountingAmounts
}

export interface ClientContractCoverage {
  client_id: string
  is_working: boolean
  requires_contract: boolean
  contract_count: number
  total_modules: number
  covered_modules: number
  latest_contract_date?: string | null
  uncovered_module_ids: string[]
  uncovered_module_names: string[]
}
