<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import {
  Archive,
  Eye,
  File,
  FileImage,
  Files,
  FileText,
  History,
  IdCard,
  Mail,
  PackageOpen,
  Plus,
  RotateCcw,
  Save,
  Search,
  Trash2,
  UserRound,
  X,
} from '@lucide/vue'
import { useAuthStore } from '@/app/stores/auth'
import DateInput from '@/shared/ui/DateInput.vue'
import NameIndexAutocomplete from '@/shared/ui/NameIndexAutocomplete.vue'
import NameIndexManagerModal from '@/shared/ui/NameIndexManagerModal.vue'
import ActionMenu, { type ActionMenuItem } from '@/shared/ui/ActionMenu.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'
import StatusPill from '@/shared/ui/StatusPill.vue'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import { matchesTableFilter, nextSortState, sortTableRows, type SortDirection } from '@/shared/lib/table'
import SortableFilterHeader from '@/shared/ui/SortableFilterHeader.vue'
import { formatMoney, formatMoneyInput, parseMoney } from '@/shared/lib/money'
import { COMPONENT_SUPPLIERS } from '@/shared/lib/componentSuppliers'
import { calculateTsrRepeatVisitDate, hasAutomaticRepeatVisitTerm } from '@/shared/lib/tsrRepeatTerms'
import { fetchAgents } from '@/shared/api/agents'
import { fetchEntityAudit } from '@/shared/api/audit'
import {
  archiveClient,
  attachClientTsr,
  createClient,
  createClientPassport,
  createClientPhone,
  createClientSnils,
  deleteClient,
  deleteClientPassport,
  deleteClientPhone,
  deleteClientSnils,
  detachClientTsr,
  fetchClient,
  fetchClientPhones,
  fetchClients,
  restoreClient,
  setClientComponentsProsthetistState,
  updateClient,
  updateClientPassport,
  updateClientPhone,
  updateClientSnils,
  updateClientTsr,
} from '@/shared/api/clients'
import {
  deleteDocument,
  downloadDocumentBlob,
  fetchClientDocuments,
  fetchContractTemplates,
  fetchMtzTemplates,
  fetchNextContractNumber,
  generateClientContract,
  generateClientMtz,
  uploadClientDocument,
  type MtzTemplateOption,
} from '@/shared/api/documents'
import { getApiErrorMessage } from '@/shared/api/http'
import {
  formatAuditAction,
  formatAuditActor,
  formatAuditTime,
  summarizeAuditDetails,
} from '@/shared/lib/audit'
import {
  createComponent as createModule,
  deleteComponent as deleteModule,
  fetchComponents as fetchModules,
  updateComponent as updateModule,
} from '@/shared/api/components'
import {
  createTsrReference,
  deleteTsrReference,
  fetchNameIndexReferences,
  fetchStages,
  fetchStatuses,
  fetchTsrReferences,
  updateTsrReference,
} from '@/shared/api/references'
import type {
  Agent,
  AuditLogItem,
  Client,
  ClientDocument,
  ClientCreatePayload,
  ClientPassport,
  ClientPassportCreate,
  ClientPassportUpdate,
  ClientPhone,
  ClientSnils,
  ClientSnilsCreate,
  ClientSnilsUpdate,
  ClientUpdatePayload,
  ContractGenerationPayload,
  DocumentStatus,
  ModuleItem,
  ModuleCreatePayload,
  ModuleUpdatePayload,
  ReferenceItem,
} from '@/shared/types/entities'

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024
const ALLOWED_UPLOAD_TYPES = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

function sanitizeDigits(value: string, maxLength: number): string {
  return value.replace(/\D/g, '').slice(0, maxLength);
}

// Очистка для серии паспорта: разрешаем цифры и пробелы (не более 7 символов)
function sanitizeSeries(value: string): string {
  return value.replace(/[^0-9 ]/g, '').slice(0, 7);
}

// Форматирование СНИЛС: 123-456-789 01
function formatSnils(value: string): string {
  const digits = sanitizeDigits(value, 11);
  if (!digits) return '';
  let result = '';
  for (let i = 0; i < digits.length; i++) {
    if (i === 3 || i === 6) result += '-';
    if (i === 9) result += ' ';
    result += digits[i];
  }
  return result;
}

// Форматирование кода подразделения: 123-456
function formatDepartmentCode(value: string): string {
  const digits = sanitizeDigits(value, 6);
  if (digits.length <= 3) return digits;
  return digits.slice(0, 3) + '-' + digits.slice(3);
}

function formatIpraNumber(value: string): string {
  const digits = sanitizeDigits(value, 12);
  if (!digits) return '';
  if (digits.length <= 3) return `ИПРА-${digits}`;
  return `ИПРА-${digits.slice(0, 3)}-${digits.slice(3)}`;
}

function formatSeries(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 4);
  if (digits.length <= 2) return digits;
  return digits.slice(0, 2) + ' ' + digits.slice(2);
}

type ContractTemplateOption = { value: string; label: string }

const contractTemplateOptions = ref<ContractTemplateOption[]>([
  { value: 'llc_contract', label: 'ООО Смарт Движение · Договор' },
  { value: 'dmk_contract', label: 'ИП ДМК · Договор' },
  { value: 'dmk_instrument', label: 'ИП ДМК · Акт' },
])

type ClientForm = {
  last_name: string
  first_name: string
  middle_name: string
  status: string
  current_stage: string
  contract_status: DocumentStatus | ''
  act_status: DocumentStatus | ''
  agent_id: string
  prosthesis_type: string
  taxation_system: 'УСН' | 'ОСНО'
  notes: string
}

type ClientTab = 'main' | 'identity' | 'phones' | 'modules' | 'documents' | 'history'
type DetailTab = Exclude<ClientTab, 'main'>
type ClientListMode = 'active' | 'archive'
type CountInput = string | number
type ComponentEntryMode = 'new' | 'catalog' | 'warehouse'

type ClientModuleForm = {
  tsr_id: string
  client_tsr_id: string
  module_name_index: string
  supplier: string
  quantity: string
  unit_cost: string
  unit_price: string
  size: string
  stiffness: string
  side: string
  ordered: CountInput
  recd: CountInput
  order_date_acc_num: string
  properties: string
  prosthetist_keep: CountInput
  notes: string
}

type ClientTsrGroup = {
  key: string
  clientTsrId: string
  tsrId: string
  tsr: string
  checkDate: string
  certificatePrice: string
  prosthetist: '' | 'Дмитрий' | 'Никита'
  placeOfResidence: string
  repeatVisitDate: string
  components: ModuleItem[]
}

type ClientTsrDraft = {
  checkDate: string
  certificatePrice: string
  prosthetist: '' | 'Дмитрий' | 'Никита'
  repeatVisitDate: string
}

const PROSTHETIST_ADDRESSES: Record<'Дмитрий' | 'Никита', string> = {
  Дмитрий: 'Ивана Сусанина, д. 3',
  Никита: 'Большая Почтовая, д. 18/20',
}

const DIAGNOSIS_OPTIONS = [
  { value: 'Верхних конечностей', label: 'Верхних конечностей' },
  { value: 'Нижних конечностей', label: 'Нижних конечностей' },
  { value: 'Верхних и нижних конечностей', label: 'Верхних и нижних конечностей' },
]

const DOCUMENT_STATUS_OPTIONS: Array<{ value: DocumentStatus; label: string }> = [
  { value: 'Подписан', label: 'Подписан' },
  { value: 'Сделан', label: 'Сделан' },
  { value: 'Отправлен', label: 'Отправлен' },
]

type ClientDocumentStatusField = 'contract_status' | 'act_status'

const emptyForm: ClientForm = {
  last_name: '',
  first_name: '',
  middle_name: '',
  status: '',
  current_stage: '',
  contract_status: '',
  act_status: '',
  agent_id: '',
  prosthesis_type: '',
  taxation_system: 'УСН',
  notes: '',
}

const authStore = useAuthStore()
const route = useRoute()

const emptyModuleForm: ClientModuleForm = {
  tsr_id: '',
  client_tsr_id: '',
  module_name_index: '',
  supplier: '',
  quantity: '1',
  unit_cost: '',
  unit_price: '',
  size: '',
  stiffness: '',
  side: '',
  ordered: '0',
  recd: '0',
  order_date_acc_num: '-',
  properties: '-',
  prosthetist_keep: '0',
  notes: '',
}

const clients = ref<Client[]>([])
const agents = ref<Agent[]>([])
const statuses = ref<ReferenceItem[]>([])
const stages = ref<ReferenceItem[]>([])
const tsrReferences = ref<ReferenceItem[]>([])
const nameIndexReferences = ref<ReferenceItem[]>([])
const phones = ref<ClientPhone[]>([])
const documents = ref<ClientDocument[]>([])
const clientModules = ref<ModuleItem[]>([])
const workingWarehouseModules = ref<ModuleItem[]>([])
const stockWarehouseModules = ref<ModuleItem[]>([])
const auditItems = ref<AuditLogItem[]>([])
const query = ref('')
const clientColumnFilters = reactive<Record<string, string>>({ patient: '', prosthetist: '', tsr: '', check_date: '', certificate: '', status: '', stage: '', contract_status: '', act_status: '', agent: '', repeat_visit: '' })
const clientSortKey = ref<string | null>(null)
const clientSortDirection = ref<SortDirection>(null)
const pageLimit = ref(100)
const currentPage = ref(1)
const activeClientListMode = ref<ClientListMode>('active')
const selectedClientIds = ref<string[]>([])
const selectedClient = ref<Client | null>(null)
const isClientCardOpen = ref(false)
const activeTab = ref<ClientTab>('main')
const form = reactive<ClientForm>({ ...emptyForm })
const moduleForm = reactive<ClientModuleForm>({ ...emptyModuleForm })
const newPhone = reactive({ phone: '', comment: '' })
const emailDraft = ref('')
const editingPhoneId = ref<string | number | null>(null)
const editingPassportId = ref<string | null>(null)
const editingSnilsId = ref<string | null>(null)
const passportForm = reactive({
  series: '',
  number: '',
  birth_date: '',
  birth_place: '',
  issued_by: '',
  issue_date: '', 
  department_code: '',
  registration_address: '',
})
const snilsForm = reactive({
  number: '',
  ipra_number: '',
  ipra_date: '',
})
const selectedModuleId = ref('')
const warehouseAssignQuantity = ref('1')
const moduleOperationQuantities = reactive<Record<string, string>>({})
const selectedContractClientTsrIds = ref<string[]>([])
const selectedContractModuleIds = ref<string[]>([])
const editingModuleId = ref<string | null>(null)
const documentGeneratorTab = ref<'contracts' | 'mtz'>('contracts')
const contractType = ref('llc_contract')
const contractNumberPrefix = ref('СД')
const contractNumberSuffix = ref('001')
const contractDate = ref(new Date().toISOString().slice(0, 10))
const contractPlanDate = ref(new Date().toISOString().slice(0, 10))
const contractAppendixDate = ref(new Date().toISOString().slice(0, 10))
const mtzTemplateOptions = ref<MtzTemplateOption[]>([])
const mtzType = ref('mtz_8_1_07_14')
const mtzNumber = ref('')
const mtzDate = ref(new Date().toISOString().slice(0, 10))
const mtzDisabilityGroupReason = ref('')
const mtzCertificateReference = ref('')
const mtzDiagnosis = ref('')
const mtzAmputationLevel = ref('')
const mtzWeightKg = ref('')
const selectedFile = ref<File | null>(null)
const isLoading = ref(false)
const detailLoadingTab = ref<DetailTab | ''>('')
const loadedDetailTabs = reactive<Record<DetailTab, boolean>>({
  identity: false,
  phones: false,
  modules: false,
  documents: false,
  history: false,
})
const isSaving = ref(false)
const inlineDocumentStatusSaving = reactive<Record<string, boolean>>({})
const error = ref('')
const successMessage = ref('')
const lastSavedClientState = ref('')
const lastSavedDetailStates = reactive<Record<DetailTab, string>>({
  identity: '',
  phones: '',
  modules: '',
  documents: '',
  history: '',
})
const lastSavedIdentityStates = reactive({ passport: '', snils: '' })
const lastSavedContactStates = reactive({ email: '', phone: '' })
const isReferenceManagerOpen = ref(false)
const isNameIndexManagerOpen = ref(false)
const referenceSearch = ref('')
const referenceDraft = ref('')
const referenceEditingId = ref<string | number | null>(null)
const referenceError = ref('')
const referenceSuccess = ref('')
const isReferenceSaving = ref(false)
const clientTsrDrafts = reactive<Record<string, ClientTsrDraft>>({})
const passportFormExpanded = ref(false)
const snilsFormExpanded = ref(false)
const componentFormExpanded = ref(false)
const componentEntryMode = ref<ComponentEntryMode>('new')
const componentWarehouseSource = ref<'working' | 'stock'>('working')

const isEditing = computed(() => Boolean(selectedClient.value?.client_id))
const isClientPersisted = computed(() => Boolean(selectedClient.value && getClientId(selectedClient.value)))
const modalMessageId = computed(() => (error.value ? 'client-modal-error' : successMessage.value ? 'client-modal-success' : undefined))
const activeClientFilterCount = computed(() => [
  query.value.trim(),
  ...Object.values(clientColumnFilters).map((value) => value.trim()),
].filter(Boolean).length)
const CLIENT_TAB_LABELS: Record<ClientTab, string> = {
  main: 'Основное',
  identity: 'Личные документы',
  phones: 'Контакты',
  modules: 'Комплектующие',
  documents: 'Документы',
  history: 'История',
}

function getPassportDraftState() {
  return JSON.stringify(passportForm)
}

function getSnilsDraftState() {
  return JSON.stringify(snilsForm)
}

function getEmailDraftState() {
  return emailDraft.value
}

function getPhoneDraftState() {
  return JSON.stringify({ phone: newPhone.phone, comment: newPhone.comment })
}

function getDetailTabDraftState(tab: DetailTab) {
  if (tab === 'identity') {
    return JSON.stringify({ passport: getPassportDraftState(), snils: getSnilsDraftState() })
  }

  if (tab === 'phones') {
    return JSON.stringify({ email: getEmailDraftState(), phone: getPhoneDraftState() })
  }

  if (tab === 'modules') {
    return JSON.stringify({
      form: moduleForm,
      selectedWarehouseModuleId: selectedModuleId.value,
      mode: componentEntryMode.value,
    })
  }

  if (tab === 'documents') {
    return JSON.stringify({
      contractType: contractType.value,
      contractNumberPrefix: contractNumberPrefix.value,
      contractNumberSuffix: contractNumberSuffix.value,
      contractDate: contractDate.value,
      contractPlanDate: contractPlanDate.value,
      contractAppendixDate: contractAppendixDate.value,
      selectedClientTsrIds: selectedContractClientTsrIds.value,
      selectedModuleIds: selectedContractModuleIds.value,
      documentGeneratorTab: documentGeneratorTab.value,
      mtzType: mtzType.value,
      mtzNumber: mtzNumber.value,
      mtzDate: mtzDate.value,
      mtzDisabilityGroupReason: mtzDisabilityGroupReason.value,
      mtzCertificateReference: mtzCertificateReference.value,
      mtzDiagnosis: mtzDiagnosis.value,
      mtzAmputationLevel: mtzAmputationLevel.value,
      mtzWeightKg: mtzWeightKg.value,
      file: selectedFile.value
        ? {
            name: selectedFile.value.name,
            size: selectedFile.value.size,
            lastModified: selectedFile.value.lastModified,
          }
        : null,
    })
  }

  return ''
}

function rememberPassportDraftState() {
  lastSavedIdentityStates.passport = getPassportDraftState()
}

function rememberSnilsDraftState() {
  lastSavedIdentityStates.snils = getSnilsDraftState()
}

function rememberEmailDraftState() {
  lastSavedContactStates.email = getEmailDraftState()
}

function rememberPhoneDraftState() {
  lastSavedContactStates.phone = getPhoneDraftState()
}

function rememberDetailTabState(tab: DetailTab) {
  if (tab === 'identity') {
    rememberPassportDraftState()
    rememberSnilsDraftState()
  } else if (tab === 'phones') {
    rememberEmailDraftState()
    rememberPhoneDraftState()
  }

  lastSavedDetailStates[tab] = getDetailTabDraftState(tab)
}

function hasUnsavedClientTsrDrafts() {
  return Object.entries(clientTsrDrafts).some(([clientTsrId, draft]) => {
    const group = clientTsrGroups.value.find((item) => item.clientTsrId === clientTsrId)
    if (!group) {
      return true
    }

    const draftPrice = parseMoneyInput(draft.certificatePrice)
    const savedPrice = parseMoneyInput(group.certificatePrice)
    return draft.checkDate !== group.checkDate
      || draftPrice !== savedPrice
      || draft.prosthetist !== group.prosthetist
      || draft.repeatVisitDate !== group.repeatVisitDate
  })
}

function hasUnsavedChangesForTab(tab: ClientTab) {
  if (tab === 'main') {
    return JSON.stringify(form) !== lastSavedClientState.value || hasUnsavedClientTsrDrafts()
  }

  if (tab === 'identity') {
    return getPassportDraftState() !== lastSavedIdentityStates.passport
      || getSnilsDraftState() !== lastSavedIdentityStates.snils
  }

  if (tab === 'phones') {
    return getEmailDraftState() !== lastSavedContactStates.email
      || getPhoneDraftState() !== lastSavedContactStates.phone
  }

  return getDetailTabDraftState(tab) !== lastSavedDetailStates[tab]
}

const dirtyClientTabs = computed(() => (
  (Object.keys(CLIENT_TAB_LABELS) as ClientTab[]).filter(hasUnsavedChangesForTab)
))
const hasUnsavedClientChanges = computed(() => (
  isClientCardOpen.value && dirtyClientTabs.value.length > 0
))
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Пациенты')
useSuccessToast(referenceSuccess, 'Справочник ТСР')

const canManageReferences = computed(() => authStore.isAdmin)
const filteredReferenceItems = computed(() => {
  const search = referenceSearch.value.trim().toLowerCase()

  if (!search) {
    return tsrReferences.value
  }

  return tsrReferences.value.filter((item) => getReferenceLabel(item).toLowerCase().includes(search))
})
const isEditingReference = computed(() => referenceEditingId.value !== null)

const statusOptions = computed(() => statuses.value.map(normalizeReferenceOption))
const stageOptions = computed(() => stages.value.map(normalizeReferenceOption))
const prosthesisOptions = computed(() => DIAGNOSIS_OPTIONS)
const nameIndexOptions = computed(() => nameIndexReferences.value
  .map((item) => {
    const label = String(item.name_index ?? '').trim()
    return { value: label, label }
  })
  .filter((option) => option.label))
const passportItems = computed(() => latestSingleItem(selectedClient.value?.passports ?? []))
const snilsItems = computed(() => latestSingleItem(selectedClient.value?.snils ?? []))
const currentSkip = computed(() => (currentPage.value - 1) * pageLimit.value)
const clientAgentFilterOptions = computed(() => agents.value.map((agent) => ({
  value: getAgentName(agent),
  label: getAgentName(agent),
})))
const clientStatusFilterOptions = computed(() => statusOptions.value.map((option) => ({ value: option.label, label: option.label })))
const clientStageFilterOptions = computed(() => stageOptions.value.map((option) => ({ value: option.label, label: option.label })))

function clientColumnValue(client: Client, key: string): unknown {
  if (key === 'number') return client.external_id ?? getClientId(client)
  if (key === 'patient') return `${getClientName(client)} ${getClientPrimaryPhone(client)}`
  if (key === 'prosthetist') return getClientProsthetistLabel(client)
  if (key === 'tsr') return getClientTsrLabel(client)
  if (key === 'check_date') return getClientCheckDates(client)
  if (key === 'certificate') return getClientCertificateTotal(client)
  if (key === 'status') return getClientStatusLabel(client)
  if (key === 'stage') return getClientStageLabel(client)
  if (key === 'contract_status') return client.contract_status ?? ''
  if (key === 'act_status') return client.act_status ?? ''
  if (key === 'agent') return getAgentLabel(client.agent_id)
  if (key === 'repeat_visit') return getClientRepeatVisitDates(client)
  return ''
}

function sortClients(key: string) {
  const next = nextSortState({ key: clientSortKey.value, direction: clientSortDirection.value }, key)
  clientSortKey.value = next.key
  clientSortDirection.value = next.direction
  currentPage.value = 1
}

const filteredClients = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('ru-RU')
  const filtered = clients.value.filter((client) => {
    if (needle && !getClientSearchText(client).includes(needle)) return false
    return Object.entries(clientColumnFilters).every(([key, filter]) => {
      const kind = key === 'number' || key === 'certificate'
        ? 'number'
        : key === 'check_date' || key === 'repeat_visit'
          ? 'date'
          : key === 'status' || key === 'stage' || key === 'contract_status' || key === 'act_status' || key === 'agent'
            ? 'select'
            : 'text'
      return matchesTableFilter(clientColumnValue(client, key), filter, kind)
    })
  })
  return sortTableRows(filtered, clientSortKey.value, clientSortDirection.value, clientColumnValue)
})
const pagedClients = computed(() => filteredClients.value.slice(currentSkip.value, currentSkip.value + pageLimit.value))
const selectedClients = computed(() => {
  const ids = new Set(selectedClientIds.value)
  return clients.value.filter((client) => ids.has(getClientId(client)))
})
const pagedClientIds = computed(() => pagedClients.value.map(getClientId).filter(Boolean))
const allPagedClientsSelected = computed(() => (
  pagedClientIds.value.length > 0 && pagedClientIds.value.every((id) => selectedClientIds.value.includes(id))
))
const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => currentSkip.value + pageLimit.value < filteredClients.value.length)
const attachedTsrOptions = computed(() => {
  const items = [...(selectedClient.value?.tsr_items ?? [])].sort((left, right) => {
    const createdCompare = String(left.created_at ?? '').localeCompare(String(right.created_at ?? ''))
    return createdCompare || String(left.client_tsr_id ?? '').localeCompare(String(right.client_tsr_id ?? ''))
  })
  return items.map((item) => {
    const tsrId = String(item.tsr_id || item.tsr?.tsr_id || item.tsr?.id || '')
    const value = String(item.client_tsr_id || '')
    const code = String(item.tsr?.full_tsr_code || 'ТСР без кода')
    return {
      value,
      tsrId,
      label: code,
    }
  }).filter((item) => item.value && item.tsrId)
})

const attachedTsrCounts = computed(() => attachedTsrOptions.value.reduce((result, item) => {
  result.set(item.tsrId, (result.get(item.tsrId) ?? 0) + 1)
  return result
}, new Map<string, number>()))

const warehouseModules = computed(() => (
  componentWarehouseSource.value === 'stock' ? stockWarehouseModules.value : workingWarehouseModules.value
))

const workingWarehouseUnitCount = computed(() => workingWarehouseModules.value.reduce(
  (sum, item) => sum + Math.max(1, Number(item.quantity ?? 1)),
  0,
))

const stockWarehouseUnitCount = computed(() => stockWarehouseModules.value.reduce(
  (sum, item) => sum + Math.max(1, Number(item.quantity ?? 1)),
  0,
))

const clientModuleUnitCount = computed(() => clientModules.value.reduce(
  (sum, item) => sum + Math.max(1, Number(item.quantity ?? 1)),
  0,
))

const selectedWarehouseModule = computed(() => warehouseModules.value.find(
  (item) => String(item.module_id ?? '') === selectedModuleId.value,
) ?? null)
const selectedWarehouseAvailableQuantity = computed(() => (
  selectedWarehouseModule.value ? getModuleUnitCount(selectedWarehouseModule.value) : 1
))

const selectedWarehouseTargetMismatch = computed(() => {
  const warehouseModule = selectedWarehouseModule.value
  const target = selectedComponentTsrGroup.value
  if (!warehouseModule || !target) return false

  const warehouseTsrId = String(warehouseModule.tsr_id ?? warehouseModule.tsr?.id ?? '')
  return Boolean(warehouseTsrId && warehouseTsrId !== target.tsrId)
})

const clientTsrGroups = computed<ClientTsrGroup[]>(() => {
  const source = clientModules.value.length ? clientModules.value : (selectedClient.value?.modules ?? [])
  const groups = new Map<string, ClientTsrGroup>()
  const firstAssignmentByTsr = new Map<string, string>()

  for (const item of selectedClient.value?.tsr_items ?? []) {
    const clientTsrId = String(item.client_tsr_id || '')
    const tsrId = String(item.tsr_id || item.tsr?.tsr_id || item.tsr?.id || '')
    if (!clientTsrId || !tsrId) continue
    firstAssignmentByTsr.set(tsrId, firstAssignmentByTsr.get(tsrId) ?? clientTsrId)
    groups.set(clientTsrId, {
      key: clientTsrId,
      clientTsrId,
      tsrId,
      tsr: String(item.tsr?.full_tsr_code || 'ТСР без кода'),
      checkDate: String(item.check_date || '').slice(0, 10),
      certificatePrice: item.certificate_price == null ? '' : formatMoneyInput(item.certificate_price),
      prosthetist: item.prosthetist === 'Дмитрий' || item.prosthetist === 'Никита' ? item.prosthetist : '',
      placeOfResidence: String(item.place_of_residence || ''),
      repeatVisitDate: String(item.repeat_visit_date || '').slice(0, 10),
      components: [],
    })
  }

  for (const component of source) {
    const tsrId = String(component.tsr_id ?? component.tsr?.id ?? '')
    const explicitAssignmentId = String(component.client_tsr_id ?? '')
    const key = explicitAssignmentId || firstAssignmentByTsr.get(tsrId) || (tsrId ? `legacy:${tsrId}` : '__unassigned__')
    const group = groups.get(key)
    if (group) {
      group.components.push(component)
    } else {
      groups.set(key, {
        key,
        clientTsrId: explicitAssignmentId,
        tsrId,
        tsr: component.tsr?.full_tsr_code || 'ТСР не выбран',
        checkDate: '',
        certificatePrice: '',
        prosthetist: '',
        placeOfResidence: '',
        repeatVisitDate: '',
        components: [component],
      })
    }
  }

  return [...groups.values()].sort((left, right) => {
    if (left.key === '__unassigned__') return 1
    if (right.key === '__unassigned__') return -1
    return left.tsr.localeCompare(right.tsr, 'ru')
  })
})

const selectedComponentTsrGroup = computed(() => clientTsrGroups.value.find(
  (group) => group.clientTsrId && group.clientTsrId === moduleForm.client_tsr_id,
) ?? null)

const contractTsrGroups = computed(() => clientTsrGroups.value.filter(
  (group) => Boolean(group.clientTsrId && group.tsrId),
))

const statusFallbackLabels: Record<string, string> = {
  new: 'Новый',
  work: 'В работе',
  success: 'Успешно завершен',
  fail: 'Отказ',
  hold: 'Отложен',
  // Совместимость с историческими кодами.
  inwork: 'В работе',
  active: 'Активный',
  completed: 'Успешно завершен',
  failed: 'Отказ',
  postponed: 'Отложен',
}

const stageFallbackLabels: Record<string, string> = {
  contact: 'Первичный контакт',
  meeting: 'Встреча/Переговоры',
  contract: 'Договор',
  prepay: 'Оплата',
  production: 'Протезирование',
  done: 'Закрытие актов',
  shipping: 'Выполнено',
  // Совместимость с историческими кодами.
  documents: 'Документы',
  measurement: 'Замер',
  fitting: 'Примерка',
  contractsign: 'Подписание договора',
  delivery: 'Выдача',
  payment: 'Оплата',
  completed: 'Закрытие актов',
}


function parseMaybeJson(value: unknown): unknown {
  if (typeof value !== 'string') {
    return value
  }

  const trimmed = value.trim()

  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
    return value
  }

  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return value
  }
}

function latestSingleItem<T extends { created_at?: string | null }>(items: T[]): T[] {
  const [latest] = [...items].sort((left, right) => (
    String(right.created_at ?? '').localeCompare(String(left.created_at ?? ''))
  ))
  return latest ? [latest] : []
}

function getReferenceValue(item: ReferenceItem | Record<string, unknown> | string | number | null | undefined) {
  const parsed = parseMaybeJson(item)

  if (parsed === null || parsed === undefined) {
    return ''
  }

  if (typeof parsed !== 'object') {
    return String(parsed)
  }

  const record = parsed as Record<string, unknown>
  const value =
    record.status_code ??
    record.stage_code ??
    record.full_tsr_code ??
    record.prosthesis_code ??
    record.name_index ??
    record.module_name_index ??
    record.catalogue_index ??
    record.code ??
    record.name ??
    record.title ??
    record.id ??
    ''

  return String(value)
}

function getReferenceLabel(item: ReferenceItem | Record<string, unknown> | string | number | null | undefined) {
  const parsed = parseMaybeJson(item)

  if (parsed === null || parsed === undefined) {
    return ''
  }

  if (typeof parsed !== 'object') {
    return String(parsed)
  }

  const record = parsed as Record<string, unknown>
  const label =
    record.description ??
    record.status_name ??
    record.stage_name ??
    record.name ??
    record.title ??
    record.full_tsr_code ??
    record.prosthesis_code ??
    record.name_index ??
    record.module_name_index ??
    record.catalogue_index ??
    record.code ??
    getReferenceValue(record)

  return String(label)
}

function normalizeReferenceOption(item: ReferenceItem) {
  return {
    value: getReferenceValue(item),
    label: getReferenceLabel(item),
  }
}

function getReferenceId(item: ReferenceItem) {
  return item.id ?? item.prosthesis_id ?? item.tsr_id ?? item.name_index_id ?? ''
}

function resetReferenceManagerMessages() {
  referenceError.value = ''
  referenceSuccess.value = ''
}

function resetReferenceManagerForm() {
  referenceDraft.value = ''
  referenceEditingId.value = null
  resetReferenceManagerMessages()
}

function openReferenceManager() {
  referenceSearch.value = ''
  resetReferenceManagerForm()
  isReferenceManagerOpen.value = true
}

function closeReferenceManager() {
  if (isReferenceSaving.value) {
    return
  }

  isReferenceManagerOpen.value = false
  resetReferenceManagerForm()
}

function startEditReference(item: ReferenceItem) {
  const id = getReferenceId(item)

  if (!id) {
    referenceError.value = 'Не удалось определить ID записи справочника.'
    return
  }

  referenceEditingId.value = id
  referenceDraft.value = getReferenceLabel(item)
  resetReferenceManagerMessages()
}

async function reloadManagedReferences() {
  tsrReferences.value = await fetchTsrReferences()
}

async function refreshTsrDependentViews() {
  await reloadManagedReferences()

  const selectedClientId = selectedClient.value ? getClientId(selectedClient.value) : ''
  if (selectedClientId) {
    await refreshSelectedClient(selectedClientId, false)
    if (loadedDetailTabs.modules) {
      await loadClientTabData('modules', true)
    }
  }

  await loadClients()
}

async function saveManagedReference() {
  if (!canManageReferences.value) {
    referenceError.value = 'Управлять справочниками может только администратор.'
    return
  }

  const value = referenceDraft.value.trim()
  if (!value) {
    referenceError.value = 'Введите код ТСР.'
    return
  }

  isReferenceSaving.value = true
  resetReferenceManagerMessages()

  try {
    if (referenceEditingId.value) {
      await updateTsrReference(referenceEditingId.value, { full_tsr_code: value })
      referenceSuccess.value = 'Код ТСР обновлен.'
    } else {
      await createTsrReference({ full_tsr_code: value })
      referenceSuccess.value = 'Код ТСР добавлен.'
    }

    await refreshTsrDependentViews()
    referenceDraft.value = ''
    referenceEditingId.value = null
  } catch (caughtError) {
    referenceError.value = getApiErrorMessage(caughtError)
  } finally {
    isReferenceSaving.value = false
  }
}

async function removeManagedReference(item: ReferenceItem) {
  if (!canManageReferences.value) {
    referenceError.value = 'Управлять справочниками может только администратор.'
    return
  }

  const id = getReferenceId(item)
  const label = getReferenceLabel(item)

  if (!id) {
    referenceError.value = 'Не удалось определить ID записи справочника.'
    return
  }

  if (!(await confirmAction({
    message: `Удалить запись «${label}» из справочника ТСР?`,
    danger: true,
  }))) {
    return
  }

  isReferenceSaving.value = true
  resetReferenceManagerMessages()

  try {
    await deleteTsrReference(id)
    referenceSuccess.value = 'Код ТСР удален.'

    await refreshTsrDependentViews()
    if (referenceEditingId.value === id) {
      resetReferenceManagerForm()
    }
  } catch (caughtError) {
    referenceError.value = getApiErrorMessage(caughtError)
  } finally {
    isReferenceSaving.value = false
  }
}

function getOptionLabel(
  options: Array<{ value: string; label: string }>,
  rawValue: unknown,
  fallbackLabels: Record<string, string> = {},
) {
  const parsed = parseMaybeJson(rawValue)
  const value = getReferenceValue(parsed as ReferenceItem | Record<string, unknown> | string | number | null | undefined)
  const directLabel = getReferenceLabel(parsed as ReferenceItem | Record<string, unknown> | string | number | null | undefined)

  if (!value && !directLabel) {
    return '-'
  }

  const option = options.find((item) => item.value === value || item.label === directLabel || item.label === value)

  if (option) {
    return option.label
  }

  return fallbackLabels[value] ?? fallbackLabels[directLabel] ?? directLabel ?? value
}

function getClientId(client: Client) {
  return client.client_id ? String(client.client_id) : ''
}

function getClientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ') || 'Без имени'
}

function getClientInitials(client: Client) {
  return [client.last_name, client.first_name]
    .filter(Boolean)
    .map((part) => String(part).slice(0, 1))
    .join('')
    .toUpperCase() || 'КЛ'
}

function getClientActions(client: Client): ActionMenuItem[] {
  const isArchived = activeClientListMode.value === 'archive'

  return [
    {
      label: 'Открыть карточку',
      icon: Eye,
      action: () => selectClient(client),
    },
    {
      label: isArchived ? 'Восстановить' : 'Переместить в Выполненные',
      icon: isArchived ? RotateCcw : Archive,
      disabled: isSaving.value,
      action: () => changeClientArchiveState(client, !isArchived),
    },
    {
      label: 'Удалить',
      icon: Trash2,
      danger: true,
      disabled: isSaving.value,
      action: () => removeClient(client),
    },
  ]
}

function getClientStatusLabel(client: Client) {
  return client.status?.description ?? getOptionLabel(statusOptions.value, client.status_code, statusFallbackLabels)
}

function getClientStageLabel(client: Client) {
  return client.stage?.description ?? getOptionLabel(stageOptions.value, client.current_stage, stageFallbackLabels)
}

function getClientDocumentStatusLabel(value: DocumentStatus | null | undefined) {
  return DOCUMENT_STATUS_OPTIONS.find((option) => option.value === value)?.label ?? 'Не выбран'
}

function getInlineDocumentStatusSavingKey(client: Client) {
  return getClientId(client)
}

function isInlineDocumentStatusSaving(client: Client) {
  return Boolean(inlineDocumentStatusSaving[getInlineDocumentStatusSavingKey(client)])
}

async function updateClientDocumentStatus(
  client: Client,
  field: ClientDocumentStatusField,
  event: Event,
) {
  const select = event.target as HTMLSelectElement
  const nextStatus = DOCUMENT_STATUS_OPTIONS.find((option) => option.value === select.value)?.value
  const clientId = getClientId(client)

  if (!clientId || !nextStatus || isInlineDocumentStatusSaving(client)) return

  const previousStatus = client[field] ?? null
  if (previousStatus === nextStatus) return

  const savingKey = getInlineDocumentStatusSavingKey(client)
  inlineDocumentStatusSaving[savingKey] = true
  client[field] = nextStatus
  resetMessages()

  try {
    const updatedClient = await updateClient(clientId, {
      [field]: nextStatus,
    } as ClientUpdatePayload)
    Object.assign(client, updatedClient)

    if (selectedClient.value && getClientId(selectedClient.value) === clientId) {
      Object.assign(selectedClient.value, updatedClient)
    }

    successMessage.value = `${field === 'contract_status' ? 'Статус договоров' : 'Статус актов'}: ${nextStatus}`
  } catch (caughtError) {
    client[field] = previousStatus
    select.value = previousStatus ?? ''
    error.value = getApiErrorMessage(caughtError)
  } finally {
    delete inlineDocumentStatusSaving[savingKey]
  }
}

function getCountedLabels(values: string[]) {
  const counts = new Map<string, number>()
  for (const rawValue of values) {
    const value = rawValue.trim()
    if (!value) continue
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([value, count]) => count > 1 ? `${value} (x${count})` : value)
    .join('; ')
}

function getClientTsrLabel(client: Client) {
  const values = (client.tsr_items ?? [])
    .map((item) => String(item.tsr?.full_tsr_code || ''))
    .filter(Boolean)
  return getCountedLabels(values) || '-'
}

function getClientProsthetistLabel(client: Client) {
  const values = (client.tsr_items ?? [])
    .map((item) => String(item.prosthetist || ''))
    .filter(Boolean)
  if ((client.tsr_items ?? []).length) {
    return getCountedLabels(values) || '—'
  }
  return String(client.prosthetist || '—')
}

function getClientPrimaryPhone(client: Client) {
  return String(client.phones?.[0]?.number ?? '-')
}

function getClientCheckDates(client: Client) {
  const dates = (client.tsr_items ?? [])
    .map((item) => String(item.check_date || '').slice(0, 10))
    .filter(Boolean)
  if (dates.length > 0) return dates
  const legacy = String(client.check_date ?? '').slice(0, 10)
  return legacy ? [legacy] : []
}

function getClientRepeatVisitDates(client: Client) {
  const dates = (client.tsr_items ?? [])
    .map((item) => String(item.repeat_visit_date || '').slice(0, 10))
    .filter(Boolean)
  if (dates.length > 0) return dates
  const legacy = String(client.deadline ?? '').slice(0, 10)
  return legacy ? [legacy] : []
}

function getClientCertificateTotal(client: Client) {
  const items = client.tsr_items ?? []
  if (items.length > 0) {
    return items.reduce((sum, item) => sum + parseMoney(item.certificate_price), 0)
  }
  return parseMoney(client.certificate_price)
}

function getClientSearchText(client: Client) {
  return [
    getClientName(client), client.external_id, getClientStatusLabel(client), getClientStageLabel(client),
    client.contract_status, client.act_status,
    getAgentLabel(client.agent_id), client.notes, client.ipra_code, client.place_of_residence,
    ...(client.phones ?? []).map((phone) => phone.number),
    ...(client.passports ?? []).flatMap((passport) => [
      passport.full_name, passport.series_number, passport.birth_place,
      passport.issued_by, passport.department_code, passport.registration_address,
    ]),
    ...(client.snils ?? []).map((snils) => snils.number),
    ...(client.tsr_items ?? []).flatMap((item) => [
      item.tsr?.full_tsr_code, item.certificate_price, item.check_date,
      item.prosthetist, item.place_of_residence, item.repeat_visit_date,
    ]),
  ].filter(Boolean).join(' ').toLocaleLowerCase('ru-RU')
}

function getClientDate(client: Client) {
  const dates = getClientCheckDates(client)
    .map(formatShortDate)
  return getCountedLabels(dates) || '—'
}

function getClientDeadline(client: Client) {
  const values = (client.tsr_items ?? [])
    .map((item) => String(item.repeat_visit_date || '').slice(0, 10))
    .filter(Boolean)
    .map(formatShortDate)
  if ((client.tsr_items ?? []).length) {
    return getCountedLabels(values) || '—'
  }
  return formatShortDate(String(client.deadline ?? ''))
}

function getClientTsrCardStyle(index: number) {
  // A fixed stepped palette keeps neighbouring TSR cards visibly different
  // even when a patient has many records. All shades stay inside the
  // purple/blue/teal palette used by the application.
  const accents = [
    '158 105 247', // violet
    '55 196 214',  // cyan-teal
    '92 126 250',  // indigo-blue
    '50 211 154',  // green-teal
    '202 92 232',  // magenta-violet
    '58 165 246',  // sky blue
    '123 101 245', // indigo
    '40 190 181',  // teal
  ]

  return {
    '--tsr-card-accent-rgb': accents[index % accents.length],
  }
}

function getClientTsrGroupStyle(group: ClientTsrGroup) {
  const coloredGroups = clientTsrGroups.value.filter((item) => item.clientTsrId)
  const colorIndex = coloredGroups.findIndex((item) => item.key === group.key)

  return colorIndex >= 0 ? getClientTsrCardStyle(colorIndex) : {}
}

function getProsthetistAddress(prosthetist: string, fallback = '') {
  if (prosthetist === 'Дмитрий' || prosthetist === 'Никита') {
    return PROSTHETIST_ADDRESSES[prosthetist]
  }
  return fallback || 'Адрес появится после выбора протезиста'
}

function getAgentName(agent: Agent) {
  return [agent.last_name, agent.first_name, agent.middle_name].filter(Boolean).join(' ') || 'Без имени'
}

function getAgentLabel(agentId?: string) {
  if (!agentId) {
    return '-'
  }

  const agent = agents.value.find((item) => item.agent_id === agentId)
  return agent ? getAgentName(agent) : agentId
}

function getDocumentName(document: ClientDocument) {
  return document.filename || document.document_id || 'Документ'
}

function getFilenameFromDisposition(contentDisposition?: string) {
  if (!contentDisposition) {
    return ''
  }

  const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)

  if (utfMatch?.[1]) {
    return decodeURIComponent(utfMatch[1])
  }

  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/)
  return plainMatch?.[1] ?? ''
}

function getPhoneValue(phone: ClientPhone) {
  return phone.number || '-'
}

function getModuleName(moduleItem: ModuleItem) {
  return moduleItem.module_name_index ?? moduleItem.module_id ?? 'Комплектующая'
}

function isModuleAtProsthetist(moduleItem: ModuleItem) {
  return Number(moduleItem.prosthetist_keep ?? 0) > 0
}

function hasModuleDeliveryShortfall(moduleItem: ModuleItem) {
  const ordered = Math.max(0, Number(moduleItem.ordered ?? 0))
  const received = Math.max(0, Number(moduleItem.recd ?? 0))
  return ordered > received
}

function getGroupComponentIds(group: ClientTsrGroup) {
  return group.components
    .map((component) => String(component.module_id ?? ''))
    .filter(Boolean)
}

function isGroupFullyAtProsthetist(group: ClientTsrGroup) {
  return group.components.length > 0 && group.components.every(isModuleAtProsthetist)
}

function isGroupPartiallyAtProsthetist(group: ClientTsrGroup) {
  return group.components.some(isModuleAtProsthetist) && !isGroupFullyAtProsthetist(group)
}

function getModuleUnitCount(moduleItem: ModuleItem) {
  return Math.max(1, Math.trunc(Number(moduleItem.quantity ?? 1) || 1))
}

function getModuleOperationQuantity(moduleItem: ModuleItem) {
  const id = String(moduleItem.module_id ?? '')
  return id ? (moduleOperationQuantities[id] ?? '1') : '1'
}

function setModuleOperationQuantity(moduleItem: ModuleItem, value: string | number) {
  const id = String(moduleItem.module_id ?? '')
  if (!id) return
  const available = getModuleUnitCount(moduleItem)
  const parsed = Math.max(1, Math.min(available, Math.trunc(Number(value) || 1)))
  moduleOperationQuantities[id] = String(parsed)
}

function handleModuleOperationQuantityInput(moduleItem: ModuleItem, event: Event) {
  setModuleOperationQuantity(moduleItem, (event.target as HTMLInputElement).value)
}

function parseModuleOperationQuantity(moduleItem: ModuleItem, value: string | number) {
  const available = getModuleUnitCount(moduleItem)
  const parsed = Math.trunc(Number(value))
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > available) {
    throw new Error(`Укажите количество от 1 до ${available}.`)
  }
  return parsed
}

function getGroupComponentUnitCount(group: ClientTsrGroup) {
  return group.components.reduce((sum, component) => sum + getModuleUnitCount(component), 0)
}

function getModuleWarehouseAttributes(moduleItem: ModuleItem) {
  return [
    `Размер: ${moduleItem.size || '—'}`,
    `Жёсткость: ${moduleItem.stiffness || '—'}`,
    `Сторона: ${moduleItem.side || '—'}`,
  ].join(' · ')
}

function getGroupTotalCost(group: ClientTsrGroup) {
  return group.components.reduce((sum, component) => sum + parseMoney(component.cost), 0)
}

function getGroupCertificatePrice(group: ClientTsrGroup) {
  // Contract generation now saves selected TSR drafts automatically, so the
  // selector may safely preview the same certificate price the user entered.
  const draft = group.clientTsrId ? clientTsrDrafts[group.clientTsrId] : undefined
  return parseMoney(draft?.certificatePrice ?? group.certificatePrice)
}

function getClientTsrDraft(group: ClientTsrGroup): ClientTsrDraft {
  if (!group.clientTsrId) {
    return {
      checkDate: group.checkDate,
      certificatePrice: group.certificatePrice,
      prosthetist: group.prosthetist,
      repeatVisitDate: group.repeatVisitDate,
    }
  }
  return clientTsrDrafts[group.clientTsrId] ?? {
    checkDate: group.checkDate,
    certificatePrice: group.certificatePrice,
    prosthetist: group.prosthetist,
    repeatVisitDate: group.repeatVisitDate,
  }
}

function setClientTsrDraft(
  group: ClientTsrGroup,
  field: keyof ClientTsrDraft,
  value: string | null | undefined,
) {
  if (!group.clientTsrId) return
  const current = getClientTsrDraft(group)
  const normalizedValue = String(value ?? '')
  const prosthetist = normalizedValue === 'Дмитрий' || normalizedValue === 'Никита'
    ? normalizedValue
    : ''

  const nextCheckDate = field === 'checkDate' ? normalizedValue : current.checkDate
  const automaticRepeat = hasAutomaticRepeatVisitTerm(group.tsr)
    ? calculateTsrRepeatVisitDate(group.tsr, nextCheckDate)
    : null

  clientTsrDrafts[group.clientTsrId] = {
    checkDate: nextCheckDate,
    certificatePrice: field === 'certificatePrice' ? normalizedValue : current.certificatePrice,
    prosthetist: field === 'prosthetist' ? prosthetist : current.prosthetist,
    repeatVisitDate: hasAutomaticRepeatVisitTerm(group.tsr)
      ? (automaticRepeat ?? '')
      : current.repeatVisitDate,
  }
}

function setClientTsrDraftFromEvent(
  group: ClientTsrGroup,
  field: keyof ClientTsrDraft,
  event: Event,
) {
  setClientTsrDraft(group, field, (event.target as HTMLInputElement).value)
}

function getContractGroupIds(group: ClientTsrGroup) {
  return group.components
    .map((component) => String(component.module_id ?? ''))
    .filter(Boolean)
}

function isContractGroupSelected(group: ClientTsrGroup) {
  return Boolean(group.clientTsrId) && selectedContractClientTsrIds.value.includes(group.clientTsrId)
}

function isContractGroupPartiallySelected(group: ClientTsrGroup) {
  if (!isContractGroupSelected(group)) return false
  const ids = getContractGroupIds(group)
  if (ids.length === 0) return false
  const selectedCount = ids.filter((id) => selectedContractModuleIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < ids.length
}

function toggleContractGroup(group: ClientTsrGroup, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  if (!group.clientTsrId) return

  const selectedTsr = new Set(selectedContractClientTsrIds.value)
  const selectedModules = new Set(selectedContractModuleIds.value)
  const groupModuleIds = getContractGroupIds(group)

  if (checked) {
    selectedTsr.add(group.clientTsrId)
    groupModuleIds.forEach((id) => selectedModules.add(id))
  } else {
    selectedTsr.delete(group.clientTsrId)
    groupModuleIds.forEach((id) => selectedModules.delete(id))
  }

  selectedContractClientTsrIds.value = [...selectedTsr]
  selectedContractModuleIds.value = [...selectedModules]
}

function toggleContractComponent(group: ClientTsrGroup, componentId: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  if (!group.clientTsrId) return

  const selectedTsr = new Set(selectedContractClientTsrIds.value)
  const selectedModules = new Set(selectedContractModuleIds.value)

  if (checked) {
    selectedTsr.add(group.clientTsrId)
    selectedModules.add(componentId)
  } else {
    selectedModules.delete(componentId)
  }

  selectedContractClientTsrIds.value = [...selectedTsr]
  selectedContractModuleIds.value = [...selectedModules]
}

function selectAllContractTsrGroups() {
  selectedContractClientTsrIds.value = contractTsrGroups.value.map((group) => group.clientTsrId).filter(Boolean)
  selectedContractModuleIds.value = [...new Set(contractTsrGroups.value.flatMap(getContractGroupIds))]
}

function clearContractTsrSelection() {
  selectedContractClientTsrIds.value = []
  selectedContractModuleIds.value = []
}

async function persistSelectedContractTsrDrafts(clientId: string) {
  const selectedGroups = contractTsrGroups.value.filter(
    (group) => group.clientTsrId && selectedContractClientTsrIds.value.includes(group.clientTsrId),
  )

  for (const group of selectedGroups) {
    if (getGroupCertificatePrice(group) <= 0) {
      throw new Error(`Для ТСР «${group.tsr}» укажите стоимость сертификата.`)
    }

    const draft = clientTsrDrafts[group.clientTsrId]
    if (!draft) continue

    await updateClientTsr(clientId, group.clientTsrId, {
      check_date: draft.checkDate || null,
      certificate_price: draft.certificatePrice.trim() || null,
      prosthetist: draft.prosthetist || null,
    })
    delete clientTsrDrafts[group.clientTsrId]
  }
}

function formatDate(value?: string) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

function formatShortDate(value?: string | null) {
  if (!value) {
    return '-'
  }

  const normalized = String(value)
  const date = new Date(normalized)

  if (Number.isNaN(date.getTime())) {
    return normalized.slice(0, 10) || '-'
  }

  return new Intl.DateTimeFormat('ru-RU').format(date)
}

function formatContractDate(value: string) {
  if (!value) {
    return ''
  }

  const [year, month, day] = value.slice(0, 10).split('-')

  if (!year || !month || !day) {
    return value
  }

  return `${day}.${month}.${year}`
}

function getContractPrefixForTemplate(templateType: string) {
  const normalized = templateType.toLowerCase()

  if (normalized.includes('dmk')) {
    return 'ДМК'
  }

  return 'СД'
}

const showExtendedContractDates = computed(() => contractType.value === 'llc_contract')
const selectedMtzTemplate = computed(() => mtzTemplateOptions.value.find((item) => item.value === mtzType.value))
const mtzAutofillData = computed(() => {
  const client = selectedClient.value
  const passports = [...(client?.passports ?? [])].sort((a, b) => Number(b.version ?? 0) - Number(a.version ?? 0))
  const phoneItems = phones.value.length ? phones.value : (client?.phones ?? [])
  return {
    fullName: client ? getClientName(client) : '—',
    birthDate: String(passports[0]?.birth_date ?? '').slice(0, 10) || '—',
    phone: String(phoneItems[0]?.number ?? '') || '—',
  }
})

watch(contractType, (templateType, previousTemplateType) => {
  const previousPrefix = getContractPrefixForTemplate(previousTemplateType || '')

  if (!contractNumberPrefix.value.trim() || contractNumberPrefix.value.trim() === previousPrefix) {
    contractNumberPrefix.value = getContractPrefixForTemplate(templateType)
  }
})

function formatFileSize(bytes?: number | null) {
  const value = Number(bytes ?? 0)

  if (!Number.isFinite(value) || value <= 0) {
    return 'размер не указан'
  }

  if (value < 1024 * 1024) {
    return `${Math.ceil(value / 1024)} КБ`
  }

  return `${(value / 1024 / 1024).toFixed(1)} МБ`
}

function getDocumentIcon(document: ClientDocument) {
  const contentType = String(document.content_type ?? '').toLowerCase()

  if (contentType.includes('pdf')) {
    return FileText
  }

  if (contentType.includes('image')) {
    return FileImage
  }

  if (contentType.includes('wordprocessingml')) {
    return Files
  }

  return File
}

function parseMoneyInput(value: string) {
  if (!value.trim()) {
    return null
  }

  const parsed = parseMoney(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatModuleMoneyField(field: 'unit_cost' | 'unit_price') {
  moduleForm[field] = formatMoneyInput(moduleForm[field])
}

function parsePositiveInteger(value: string, fallback = 1) {
  const parsed = Number.parseInt(value.trim(), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function parseNonNegativeInteger(value: CountInput | null | undefined) {
  const parsed = Number.parseInt(String(value ?? '').trim(), 10)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
}

function resetModuleForm(preserveTarget = true) {
  const target = preserveTarget ? selectedComponentTsrGroup.value : null
  Object.assign(moduleForm, emptyModuleForm)
  if (target) {
    moduleForm.tsr_id = target.tsrId
    moduleForm.client_tsr_id = target.clientTsrId
  }
  selectedModuleId.value = ''
  warehouseAssignQuantity.value = '1'
  editingModuleId.value = null
  rememberDetailTabState('modules')
}

function prepareNewComponentForTsr(group: ClientTsrGroup) {
  Object.assign(moduleForm, emptyModuleForm)
  moduleForm.tsr_id = group.tsrId
  moduleForm.client_tsr_id = group.clientTsrId
  editingModuleId.value = null
  selectedModuleId.value = ''
  warehouseAssignQuantity.value = '1'
  componentEntryMode.value = 'new'
  componentFormExpanded.value = true
  resetMessages()
  rememberDetailTabState('modules')
}

function getComponentTsrOptionLabel(group: ClientTsrGroup) {
  const details = [
    group.checkDate ? `дата ${formatShortDate(group.checkDate)}` : '',
    getGroupCertificatePrice(group) > 0 ? `сертификат ${formatMoney(getGroupCertificatePrice(group))}` : '',
  ].filter(Boolean)

  return details.length ? `${group.tsr} · ${details.join(' · ')}` : group.tsr
}

function handleComponentTargetChange() {
  const target = selectedComponentTsrGroup.value
  moduleForm.tsr_id = target?.tsrId ?? ''

  const warehouseModule = selectedWarehouseModule.value
  const warehouseTsrId = String(warehouseModule?.tsr_id ?? warehouseModule?.tsr?.id ?? '')
  if (warehouseModule && target && warehouseTsrId !== target.tsrId) {
    selectedModuleId.value = ''
  }

  resetMessages()
}

function setComponentEntryMode(mode: ComponentEntryMode) {
  if (componentEntryMode.value === mode && !editingModuleId.value) {
    componentFormExpanded.value = true
    return
  }

  const target = selectedComponentTsrGroup.value
  Object.assign(moduleForm, emptyModuleForm)
  if (target) {
    moduleForm.tsr_id = target.tsrId
    moduleForm.client_tsr_id = target.clientTsrId
  }
  selectedModuleId.value = ''
  warehouseAssignQuantity.value = '1'
  editingModuleId.value = null
  componentEntryMode.value = mode
  componentFormExpanded.value = true
  resetMessages()
  rememberDetailTabState('modules')
}

function setComponentWarehouseSource(source: 'working' | 'stock') {
  if (componentWarehouseSource.value === source) return
  componentWarehouseSource.value = source
  selectedModuleId.value = ''
  warehouseAssignQuantity.value = '1'
  resetMessages()
}

function handleWarehouseModuleChange() {
  const warehouseModule = selectedWarehouseModule.value
  warehouseAssignQuantity.value = '1'
  if (!warehouseModule) return

  const warehouseTsrId = String(warehouseModule.tsr_id ?? warehouseModule.tsr?.id ?? '')
  const matchingTargets = clientTsrGroups.value.filter(
    (group) => group.clientTsrId && group.tsrId === warehouseTsrId,
  )
  const currentTarget = selectedComponentTsrGroup.value

  if (matchingTargets.length === 1 && currentTarget?.tsrId !== warehouseTsrId) {
    moduleForm.client_tsr_id = matchingTargets[0].clientTsrId
    moduleForm.tsr_id = matchingTargets[0].tsrId
  }
}

async function submitComponentForm() {
  if (componentEntryMode.value === 'warehouse' && !editingModuleId.value) {
    await assignModule()
    return
  }

  await saveClientModule()
}

function fillModuleForm(moduleItem: ModuleItem) {
  const quantity = Number(moduleItem.quantity ?? 1) || 1
  const cost = Number(moduleItem.cost ?? 0)
  const price = Number(moduleItem.price ?? 0)

  editingModuleId.value = moduleItem.module_id ? String(moduleItem.module_id) : null
  componentEntryMode.value = 'new'
  componentFormExpanded.value = true
  const group = clientTsrGroups.value.find((item) => item.components.some(
    (component) => String(component.module_id) === String(moduleItem.module_id),
  ))
  moduleForm.tsr_id = String(moduleItem.tsr_id ?? moduleItem.tsr?.id ?? group?.tsrId ?? '')
  moduleForm.client_tsr_id = String(moduleItem.client_tsr_id ?? group?.clientTsrId ?? '')
  moduleForm.module_name_index = moduleItem.module_name_index ?? ''
  moduleForm.supplier = moduleItem.supplier ?? ''
  moduleForm.quantity = String(quantity)
  moduleForm.unit_cost = moduleItem.cost == null ? '' : formatMoneyInput(cost / quantity)
  moduleForm.unit_price = moduleItem.price == null ? '' : formatMoneyInput(price / quantity)
  moduleForm.size = moduleItem.size ?? ''
  moduleForm.stiffness = moduleItem.stiffness ?? ''
  moduleForm.side = moduleItem.side ?? ''
  moduleForm.ordered = String(moduleItem.ordered ?? 0)
  moduleForm.recd = String(moduleItem.recd ?? 0)
  moduleForm.prosthetist_keep = String(moduleItem.prosthetist_keep ?? 0)
  moduleForm.order_date_acc_num = moduleItem.order_date_acc_num ?? '-'
  moduleForm.properties = moduleItem.properties ?? '-'
  moduleForm.notes = moduleItem.notes ?? ''
  resetMessages()
  rememberDetailTabState('modules')
}

function buildModulePayload(clientId: string): ModuleCreatePayload {
  const quantity = parsePositiveInteger(moduleForm.quantity)
  const unitCost = parseMoneyInput(moduleForm.unit_cost) ?? 0
  const unitPrice = parseMoneyInput(moduleForm.unit_price) ?? 0

  return {
    client_id: clientId,
    tsr_id: moduleForm.tsr_id,
    client_tsr_id: moduleForm.client_tsr_id && moduleForm.client_tsr_id !== '__new__'
      ? moduleForm.client_tsr_id
      : null,
    module_name_index: moduleForm.module_name_index.trim(),
    supplier: moduleForm.supplier.trim(),
    quantity,
    cost: unitCost * quantity,
    price: unitPrice * quantity,
    size: optionalString(moduleForm.size),
    stiffness: optionalString(moduleForm.stiffness),
    side: optionalString(moduleForm.side),
    ordered: parseNonNegativeInteger(moduleForm.ordered),
    recd: parseNonNegativeInteger(moduleForm.recd),
    prosthetist_keep: parseNonNegativeInteger(moduleForm.prosthetist_keep),
    order_date_acc_num: moduleForm.order_date_acc_num.trim() || '-',
    properties: moduleForm.properties.trim() || '-',
    notes: optionalString(moduleForm.notes),
  }
}

function validateModuleForm() {
  if (!moduleForm.tsr_id || !moduleForm.client_tsr_id) {
    error.value = 'Сначала выберите ТСР пациента, для которого добавляется комплектующая.'
    return false
  }
  if (!moduleForm.module_name_index.trim()) {
    error.value = 'Для комплектующей нужно заполнить индекс/название.'
    return false
  }

  if (!moduleForm.supplier.trim()) {
    error.value = 'Для комплектующей нужно заполнить поставщика.'
    return false
  }

  return true
}
function resetMessages() {
  successMessage.value = ''
  error.value = ''
}

function optionalString(value: string) {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function resetDetailState() {
  loadedDetailTabs.identity = false
  loadedDetailTabs.phones = false
  loadedDetailTabs.modules = false
  loadedDetailTabs.documents = false
  loadedDetailTabs.history = false
  detailLoadingTab.value = ''
  phones.value = []
  documents.value = []
  clientModules.value = []
  workingWarehouseModules.value = []
  stockWarehouseModules.value = []
  auditItems.value = []
  selectedContractClientTsrIds.value = []
  selectedContractModuleIds.value = []
  documentGeneratorTab.value = 'contracts'
  mtzNumber.value = ''
  mtzDate.value = new Date().toISOString().slice(0, 10)
  mtzDisabilityGroupReason.value = ''
  mtzCertificateReference.value = ''
  mtzDiagnosis.value = ''
  mtzAmputationLevel.value = ''
  mtzWeightKg.value = ''
  Object.keys(clientTsrDrafts).forEach((key) => delete clientTsrDrafts[key])
}

function rememberClientFormState() {
  lastSavedClientState.value = JSON.stringify(form)
}

function rememberAllDetailTabStates() {
  const tabs: DetailTab[] = ['identity', 'phones', 'modules', 'documents', 'history']
  tabs.forEach(rememberDetailTabState)
}

function resetForm() {
  Object.assign(form, emptyForm)
  Object.assign(passportForm, {
    series: '',
    number: '',
    birth_date: '',
    birth_place: '',
    issued_by: '',
    issue_date: '',
    department_code: '',
    registration_address: '',
  })
  Object.assign(snilsForm, {
    number: '',
    ipra_number: '',
    ipra_date: '',
  })
  selectedClient.value = null
  activeTab.value = 'main'
  resetDetailState()
  selectedModuleId.value = ''
  emailDraft.value = ''
  resetModuleForm(false)
  editingPhoneId.value = null
  editingPassportId.value = null
  editingSnilsId.value = null
  passportFormExpanded.value = false
  snilsFormExpanded.value = false
  componentFormExpanded.value = false
  componentEntryMode.value = 'new'
  isReferenceManagerOpen.value = false
  resetReferenceManagerForm()
  resetMessages()
  rememberClientFormState()
  rememberAllDetailTabStates()
}

function setBodyModalLock(locked: boolean) {
  window.document.body.classList.toggle('modal-open', locked)
}

async function openNewClient() {
  if (hasUnsavedClientChanges.value) {
    const shouldContinue = await confirmAction({
      header: 'Несохранённые изменения',
      message: 'Начать новую карточку? Изменения в текущей карточке будут потеряны.',
      acceptLabel: 'Начать новую',
    })

    if (!shouldContinue) {
      return
    }
  }

  resetForm()
  isClientCardOpen.value = true
}

async function closeClientCard() {
  if (isSaving.value) {
    return
  }

  if (hasUnsavedClientChanges.value) {
    const shouldClose = await confirmAction({
      header: 'Есть несохранённые изменения',
      message: `Закрыть карточку без сохранения изменений в разделах: ${dirtyClientTabs.value.map((tab) => CLIENT_TAB_LABELS[tab]).join(', ')}?`,
      acceptLabel: 'Закрыть без сохранения',
    })

    if (!shouldClose) {
      return
    }
  }

  isClientCardOpen.value = false
}

async function handleClientModalEscape() {
  if (isReferenceManagerOpen.value) {
    return
  }

  await closeClientCard()
}

async function openClientTab(tab: ClientTab) {
  if (tab === activeTab.value) {
    return true
  }

  if (tab !== 'main' && !isClientPersisted.value) {
    error.value = 'Сначала сохрани основную карточку пациента.'
    activeTab.value = 'main'
    return false
  }

  const currentTab = activeTab.value
  if (hasUnsavedChangesForTab(currentTab)) {
    const shouldSwitch = await confirmAction({
      header: 'Есть несохранённые изменения',
      message: `Перейти из раздела «${CLIENT_TAB_LABELS[currentTab]}» без сохранения изменений?`,
      acceptLabel: 'Перейти без сохранения',
    })

    if (!shouldSwitch) {
      return false
    }
  }

  activeTab.value = tab

  if (tab !== 'main') {
    await loadClientTabData(tab)
  }

  return true
}

function isTabLoading(tab: DetailTab) {
  return detailLoadingTab.value === tab
}

function fillForm(client: Client) {
  const passports = Array.isArray(client.passports) ? client.passports : []
  const firstPassport = passports[0]
  const passportRaw = String(firstPassport?.series_number ?? '');
  const parts = passportRaw.split(/\s+/);
  if (parts.length > 1) {
    passportForm.number = parts.pop() ?? '';   // забираем последнюю часть как номер
    passportForm.series = parts.join(' ');     // всё остальное – серия (с пробелами)
  } else {
    passportForm.series = parts[0] ?? '';
    passportForm.number = '';
  }
    
  form.last_name = String(client.last_name ?? '')
  form.first_name = String(client.first_name ?? '')
  form.middle_name = String(client.middle_name ?? '')
  form.status = getReferenceValue(client.status_code)
  form.current_stage = getReferenceValue(client.current_stage)
  form.contract_status = client.contract_status ?? ''
  form.act_status = client.act_status ?? ''
  form.agent_id = String(client.agent_id ?? '')
  const diagnosis = String(client.prosthesis_type ?? '')
  form.prosthesis_type = DIAGNOSIS_OPTIONS.some((option) => option.value === diagnosis) ? diagnosis : ''
  form.taxation_system = client.taxation_system === 'ОСНО' ? 'ОСНО' : 'УСН'
  form.notes = String(client.notes ?? '')
  emailDraft.value = String(client.email ?? '')
  snilsForm.ipra_number = formatIpraNumber(String(client.ipra_code ?? ''));
  const firstSnils = (client.snils ?? [])[0];
  snilsForm.number = firstSnils ? formatSnils(firstSnils.number) : '';

  
  passportForm.birth_date = String(firstPassport?.birth_date ?? '').slice(0, 10)
  passportForm.birth_place = String(firstPassport?.birth_place ?? '')
  passportForm.issued_by = String(firstPassport?.issued_by ?? '')
  passportForm.issue_date = String(firstPassport?.issue_date ?? '').slice(0, 10)
  passportForm.department_code = String(firstPassport?.department_code ?? '')
  passportForm.registration_address = String(firstPassport?.registration_address ?? '')
  rememberClientFormState()
}

function buildCreatePayload(): ClientCreatePayload {
  return {
    last_name: form.last_name.trim(),
    first_name: form.first_name.trim(),
    middle_name: optionalString(form.middle_name),
    status_code: form.status.trim(),
    current_stage: form.current_stage.trim(),
    contract_status: form.contract_status || null,
    act_status: form.act_status || null,
    agent_id: form.agent_id,
    prosthesis_type: optionalString(form.prosthesis_type),
    taxation_system: form.taxation_system,
    notes: optionalString(form.notes),
    phones: [],
  }
}

function buildUpdatePayload(): ClientUpdatePayload {
  return {
    last_name: form.last_name.trim(),
    first_name: form.first_name.trim(),
    middle_name: optionalString(form.middle_name),
    status_code: form.status.trim(),
    current_stage: form.current_stage.trim(),
    contract_status: form.contract_status || null,
    act_status: form.act_status || null,
    agent_id: form.agent_id,
    prosthesis_type: optionalString(form.prosthesis_type),
    taxation_system: form.taxation_system,
    notes: optionalString(form.notes),
  }
}

async function ensureClientExists() {
  if (selectedClient.value) {
    const existingId = getClientId(selectedClient.value)

    if (existingId) {
      return existingId
    }
  }

  if (!validateClientForm()) {
    return ''
  }

  const createdClient = await createClient(buildCreatePayload())
  const clientId = getClientId(createdClient)

  selectedClient.value = createdClient
  fillForm(createdClient)
  await refreshSelectedClient(clientId)
  await loadClients()

  return clientId
}

function validateClientForm() {
  if (!form.last_name.trim() || !form.first_name.trim()) {
    error.value = 'Заполни минимум фамилию и имя пациента.'
    return false
  }

  if (!form.status.trim()) {
    error.value = 'Выбери статус пациента.'
    return false
  }

  if (!form.current_stage.trim()) {
    error.value = 'Выбери этап пациента.'
    return false
  }

  if (!form.agent_id) {
    error.value = 'Выбери агента. По backend-схеме agent_id обязателен для пациента.'
    return false
  }

  return true
}

async function loadClients() {
  isLoading.value = true
  error.value = ''

  try {
    clients.value = await fetchClients({
      skip: 0,
      limit: 100000,
      archived: activeClientListMode.value === 'archive',
    })
    const availableIds = new Set(clients.value.map(getClientId))
    selectedClientIds.value = selectedClientIds.value.filter((id) => availableIds.has(id))
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

function applyClientFilters() {
  currentPage.value = 1
}

function resetClientFilters() {
  query.value = ''
  Object.keys(clientColumnFilters).forEach((key) => { clientColumnFilters[key] = '' })
  clientSortKey.value = null
  clientSortDirection.value = null
  currentPage.value = 1
}

function switchClientListMode(mode: ClientListMode) {
  if (activeClientListMode.value === mode) {
    return
  }

  activeClientListMode.value = mode
  selectedClientIds.value = []
  currentPage.value = 1
  selectedClient.value = null
  isClientCardOpen.value = false
  resetMessages()
  void loadClients()
}

function isClientSelected(client: Client) {
  return selectedClientIds.value.includes(getClientId(client))
}

function toggleClientSelection(client: Client, checked: boolean) {
  const id = getClientId(client)
  if (!id) return
  const ids = new Set(selectedClientIds.value)
  if (checked) ids.add(id)
  else ids.delete(id)
  selectedClientIds.value = [...ids]
}

function toggleAllPagedClients(checked: boolean) {
  const ids = new Set(selectedClientIds.value)
  for (const id of pagedClientIds.value) {
    if (checked) ids.add(id)
    else ids.delete(id)
  }
  selectedClientIds.value = [...ids]
}

function handleToggleAllClients(event: Event) {
  toggleAllPagedClients((event.target as HTMLInputElement).checked)
}

function handleToggleClient(client: Client, event: Event) {
  toggleClientSelection(client, (event.target as HTMLInputElement).checked)
}

async function runBulkClientAction(action: 'archive' | 'restore' | 'delete') {
  const items = selectedClients.value
  if (!items.length) return

  const actionLabel = action === 'archive'
    ? 'переместить в Выполненные'
    : action === 'restore'
      ? 'восстановить'
      : 'удалить'
  if (!(await confirmAction({
    header: 'Множественная операция',
    message: `${actionLabel[0].toUpperCase()}${actionLabel.slice(1)} выбранных пациентов (${items.length})?`,
    acceptLabel: actionLabel,
    danger: action === 'delete',
  }))) return

  isSaving.value = true
  resetMessages()
  let completed = 0
  const failures: string[] = []
  for (const client of items) {
    const id = getClientId(client)
    try {
      if (action === 'archive') await archiveClient(id)
      else if (action === 'restore') await restoreClient(id)
      else await deleteClient(id)
      completed += 1
    } catch (caughtError) {
      failures.push(`${getClientName(client)}: ${getApiErrorMessage(caughtError)}`)
    }
  }

  selectedClientIds.value = []
  if (completed) successMessage.value = `Операция выполнена для ${completed} пациентов`
  if (failures.length) error.value = `Не удалось обработать ${failures.length}: ${failures.join('; ')}`
  await loadClients()
  isSaving.value = false
}

async function goToPreviousClientsPage() {
  if (!hasPreviousPage.value) {
    return
  }

  currentPage.value -= 1
}

async function goToNextClientsPage() {
  if (!hasNextPage.value) {
    return
  }

  currentPage.value += 1
}

async function reloadNameIndexReferences() {
  nameIndexReferences.value = await fetchNameIndexReferences()
}

async function loadReferences() {
  const [agentsResponse, statusesResponse, stagesResponse, tsrResponse, nameIndexResponse] = await Promise.allSettled([
    fetchAgents({ limit: 500 }),
    fetchStatuses(),
    fetchStages(),
    fetchTsrReferences(),
    fetchNameIndexReferences(),
  ])

  agents.value = agentsResponse.status === 'fulfilled' ? agentsResponse.value : []
  statuses.value = statusesResponse.status === 'fulfilled' ? statusesResponse.value : []
  stages.value = stagesResponse.status === 'fulfilled' ? stagesResponse.value : []
  tsrReferences.value = tsrResponse.status === 'fulfilled' ? tsrResponse.value : []
  nameIndexReferences.value = nameIndexResponse.status === 'fulfilled' ? nameIndexResponse.value : []
}

async function loadClientTabData(tab: DetailTab, force = false) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''

  if (!clientId || (!force && loadedDetailTabs[tab])) {
    return
  }

  detailLoadingTab.value = tab

  try {
    if (tab === 'identity') {
      await refreshSelectedClient(clientId, false)
    } else if (tab === 'phones') {
      phones.value = await fetchClientPhones(clientId)
    } else if (tab === 'modules') {
      const archived = Boolean(selectedClient.value?.is_archived)
      const [clientModuleResponse, workingWarehouseResponse, stockWarehouseResponse] = await Promise.all([
        fetchModules({ limit: 1000, client_id: clientId, archived }),
        archived
          ? Promise.resolve([])
          : fetchModules({ limit: 1000, unassigned: true, archived: false, in_stock: false }),
        archived
          ? Promise.resolve([])
          : fetchModules({ limit: 1000, unassigned: true, archived: false, in_stock: true }),
      ])
      clientModules.value = clientModuleResponse
      workingWarehouseModules.value = workingWarehouseResponse
      stockWarehouseModules.value = stockWarehouseResponse
      Object.keys(moduleOperationQuantities).forEach((key) => delete moduleOperationQuantities[key])
    } else if (tab === 'documents') {
      const [documentResponse, moduleResponse, nextNumber] = await Promise.all([
        fetchClientDocuments(clientId),
        fetchModules({
          limit: 1000,
          client_id: clientId,
          archived: Boolean(selectedClient.value?.is_archived),
        }),
        fetchNextContractNumber(),
      ])
      documents.value = documentResponse
      contractNumberSuffix.value = nextNumber
      clientModules.value = moduleResponse
      const available = new Set(moduleResponse.map((item) => String(item.module_id)))
      const availableTsr = new Set((selectedClient.value?.tsr_items ?? []).map((item) => String(item.client_tsr_id)))
      selectedContractClientTsrIds.value = selectedContractClientTsrIds.value.filter((id) => availableTsr.has(id))
      selectedContractModuleIds.value = selectedContractModuleIds.value.filter((id) => available.has(id))
    } else if (tab === 'history') {
      auditItems.value = await fetchEntityAudit('client', clientId)
    }

    rememberDetailTabState(tab)
    loadedDetailTabs[tab] = true
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    if (detailLoadingTab.value === tab) {
      detailLoadingTab.value = ''
    }
  }
}

async function reloadActiveDetailTab() {
  if (activeTab.value !== 'main') {
    await loadClientTabData(activeTab.value, true)
  }
}

async function refreshSelectedClient(clientId: string, syncForm = true) {
  const freshClient = await fetchClient(clientId)
  selectedClient.value = freshClient
  emailDraft.value = String(freshClient.email ?? '')

  if (syncForm) {
    fillForm(freshClient)
  }
}

async function selectClient(client: Client) {
  const nextClientId = getClientId(client)
  const currentClientId = selectedClient.value ? getClientId(selectedClient.value) : ''

  if (isClientCardOpen.value && currentClientId !== nextClientId && hasUnsavedClientChanges.value) {
    const shouldSwitch = await confirmAction({
      header: 'Есть несохранённые изменения',
      message: 'Открыть другую карточку без сохранения изменений в текущей?',
      acceptLabel: 'Открыть другую карточку',
    })

    if (!shouldSwitch) {
      return
    }
  }

  resetForm()
  selectedClient.value = client
  isClientCardOpen.value = true
  fillForm(client)
  rememberDetailTabState('identity')
  rememberDetailTabState('phones')

  const clientId = nextClientId

  if (!clientId) {
    return
  }

  void refreshSelectedClient(clientId).catch(() => {
    selectedClient.value = client
  })
}

async function openClientFromRoute(rawClientId: unknown) {
  const queryValue = Array.isArray(rawClientId) ? rawClientId[0] : rawClientId
  const clientId = String(queryValue ?? '').trim()

  if (!clientId) {
    return
  }

  try {
    const client = await fetchClient(clientId)
    const targetMode: ClientListMode = client.is_archived ? 'archive' : 'active'

    if (activeClientListMode.value !== targetMode) {
      activeClientListMode.value = targetMode
      currentPage.value = 1
      await loadClients()
    }

    await selectClient(client)
  } catch (caughtError) {
    error.value = `Не удалось открыть карточку пациента: ${getApiErrorMessage(caughtError)}`
  }
}

async function finishAutomaticArchive(client: Client) {
  const clientName = getClientName(client)
  activeClientListMode.value = 'archive'
  currentPage.value = 1
  isClientCardOpen.value = false
  resetForm()
  successMessage.value = `Пациент «${clientName}» и все его комплектующие автоматически перемещены в Выполненные: статус «Успешно завершен», этап «Выполнено».`
  await loadClients()
}

async function saveClient() {
  resetMessages()

  if (!validateClientForm()) {
    return
  }

  isSaving.value = true

  try {
    if (isEditing.value && selectedClient.value) {
      const clientId = getClientId(selectedClient.value)
      const wasArchived = Boolean(selectedClient.value.is_archived)
      const updatedClient = await updateClient(clientId, buildUpdatePayload())

      if (!wasArchived && updatedClient.is_archived) {
        await finishAutomaticArchive(updatedClient)
        return
      }

      selectedClient.value = updatedClient
      fillForm(updatedClient)
      await refreshSelectedClient(clientId)
      await reloadActiveDetailTab()
      successMessage.value = 'Пациент обновлен'
    } else {
      const createdClient = await createClient(buildCreatePayload())

      if (createdClient.is_archived) {
        await finishAutomaticArchive(createdClient)
        return
      }

      const clientId = getClientId(createdClient)
      selectedClient.value = createdClient
      fillForm(createdClient)
      await refreshSelectedClient(clientId)
      await reloadActiveDetailTab()
      successMessage.value = 'Пациент создан'
    }

    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeClient(client: Client) {
  const clientId = getClientId(client)

  if (!clientId) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить пациента «${getClientName(client)}»? Это действие нельзя отменить.`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteClient(clientId)
    successMessage.value = 'Пациент удален'

    if (selectedClient.value && getClientId(selectedClient.value) === clientId) {
      resetForm()
    }

    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function changeClientArchiveState(client: Client, archive: boolean) {
  const clientId = getClientId(client)
  const action = archive ? 'переместить в Выполненные' : 'восстановить'
  const componentNote = archive
    ? ' Все привязанные комплектующие также будут перемещены в Выполненные.'
    : ' Все привязанные комплектующие также будут восстановлены.'

  if (!clientId) {
    return
  }

  if (!(await confirmAction({
    header: archive ? 'Перемещение в Выполненные' : 'Восстановление пациента',
    message: `${action[0].toUpperCase()}${action.slice(1)} пациента «${getClientName(client)}»?${componentNote}`,
    acceptLabel: archive ? 'В Выполненные' : 'Восстановить',
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    if (archive) {
      await archiveClient(clientId)
    } else {
      await restoreClient(clientId)
    }

    if (selectedClient.value && getClientId(selectedClient.value) === clientId) {
      isClientCardOpen.value = false
      resetForm()
    }

    successMessage.value = archive
      ? 'Пациент и его комплектующие перемещены в Выполненные'
      : 'Пациент и его комплектующие восстановлены'
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

function startEditPhone(phone: ClientPhone) {
  if (!phone.phone_id) {
    return
  }

  editingPhoneId.value = phone.phone_id
  newPhone.phone = getPhoneValue(phone)
  newPhone.comment = ''
  resetMessages()
  rememberPhoneDraftState()
}

function cancelPhoneEdit() {
  editingPhoneId.value = null
  newPhone.phone = ''
  newPhone.comment = ''
  rememberPhoneDraftState()
}

async function addPhone() {
  if (!newPhone.phone.trim()) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    if (editingPhoneId.value) {
      await updateClientPhone(editingPhoneId.value, { number: newPhone.phone.trim() })
      successMessage.value = 'Телефон обновлен'
    } else {
      await createClientPhone(clientId, { number: newPhone.phone.trim() })
      successMessage.value = 'Телефон добавлен'
    }

    cancelPhoneEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('phones', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removePhone(phone: ClientPhone) {
  if (!selectedClient.value || !phone.phone_id) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить телефон «${getPhoneValue(phone)}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = getClientId(selectedClient.value)
    await deleteClientPhone(phone.phone_id)
    successMessage.value = 'Телефон удален'
    cancelPhoneEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('phones', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function saveEmail() {
  const value = emailDraft.value.trim()
  if (value.length > 64) {
    error.value = 'Адрес электронной почты не должен превышать 64 символа.'
    return
  }
  if (value && !/^\S+@\S+\.\S+$/.test(value)) {
    error.value = 'Укажите корректный адрес электронной почты.'
    return
  }
  isSaving.value = true
  resetMessages()
  try {
    const clientId = await ensureClientExists()
    if (!clientId) return
    await updateClient(clientId, { email: value || null })
    await refreshSelectedClient(clientId, false)
    await loadClients()
    rememberEmailDraftState()
    successMessage.value = value ? 'Электронная почта сохранена' : 'Электронная почта удалена'
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeEmail() {
  if (!selectedClient.value?.email) return
  if (!(await confirmAction({ message: `Удалить электронную почту «${selectedClient.value.email}»?`, danger: true }))) return
  emailDraft.value = ''
  await saveEmail()
}


function startEditPassport(passport: ClientPassport) {
  if (!passport.passport_id) {
    return
  }

  const passportRaw = String(passport.series_number ?? '');
  const parts = passportRaw.split(/\s+/);
  if (parts.length > 1) {
    passportForm.number = parts.pop() ?? '';
    passportForm.series = parts.join(' ');
  } else {
    passportForm.series = parts[0] ?? '';
    passportForm.number = '';
  }

  editingPassportId.value = passport.passport_id
  passportForm.birth_date = String(passport.birth_date ?? '').slice(0, 10)
  passportForm.birth_place = passport.birth_place ?? ''
  passportForm.issued_by = passport.issued_by ?? ''
  passportForm.issue_date = String(passport.issue_date ?? '').slice(0, 10)
  passportForm.department_code = passport.department_code ?? ''
  passportForm.registration_address = passport.registration_address ?? ''
  passportFormExpanded.value = true
  resetMessages()
  rememberPassportDraftState()
}

function cancelPassportEdit() {
  editingPassportId.value = null
  Object.assign(passportForm, {
    series: '',
    number: '',
    birth_date: '',
    birth_place: '',
    issued_by: '',
    issue_date: '',
    department_code: '',
    registration_address: '',
  })
  rememberPassportDraftState()
}

async function savePassport() {
  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }
    if (!editingPassportId.value && passportItems.value.length > 0) {
      error.value = 'У пациента уже есть паспорт. Измените существующий документ.'
      return
    }

    const seriesNumber = [passportForm.series.trim(), passportForm.number.trim()].filter(Boolean).join(' ')
    const issuedBy = passportForm.issued_by.trim()
    const issueDate = passportForm.issue_date
    const departmentCode = passportForm.department_code.trim()
    const registrationAddress = passportForm.registration_address.trim()
    const fullName = selectedClient.value ? getClientName(selectedClient.value) : getClientName({
      last_name: form.last_name,
      first_name: form.first_name,
      middle_name: form.middle_name,
    } as Client)

    if (!seriesNumber || !issuedBy || !issueDate || !passportForm.birth_place.trim() || !registrationAddress) {
      error.value = 'Для паспорта обязательны: серия/номер, место рождения, кем выдан, дата выдачи и адрес регистрации.'
      return
    }

    const payload: ClientPassportCreate = {
      full_name: fullName,
      birth_date: passportForm.birth_date || null,
      birth_place: passportForm.birth_place.trim(),
      series_number: seriesNumber,
      issued_by: issuedBy,
      issue_date: issueDate,
      department_code: departmentCode || null,
      registration_address: registrationAddress,
    }

    if (editingPassportId.value) {
      await updateClientPassport(editingPassportId.value, payload as ClientPassportUpdate)
      successMessage.value = 'Паспорт обновлен'
    } else {
      await createClientPassport(clientId, payload)
      successMessage.value = 'Паспорт сохранен'
    }

    cancelPassportEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('identity', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removePassport(passport: ClientPassport) {
  if (!selectedClient.value || !passport.passport_id) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить паспорт «${passport.series_number}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = getClientId(selectedClient.value)
    await deleteClientPassport(passport.passport_id)
    successMessage.value = 'Паспорт удален'
    cancelPassportEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('identity', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

function startEditSnils(snils: ClientSnils) {
  if (!snils.snils_id) {
    return
  }

  editingSnilsId.value = snils.snils_id
  snilsForm.number = formatSnils(snils.number ?? '');
  snilsForm.ipra_number = formatIpraNumber(selectedClient.value?.ipra_code ?? '');
  snilsForm.ipra_date = String(snils.issued_date ?? '').slice(0, 10)
  snilsFormExpanded.value = true
  resetMessages()
  rememberSnilsDraftState()
}

function cancelSnilsEdit() {
  editingSnilsId.value = null
  Object.assign(snilsForm, {
    number: '',
    ipra_number: '',
    ipra_date: '',
  })
  rememberSnilsDraftState()
}

async function saveSnils() {
  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }
    if (!editingSnilsId.value && snilsItems.value.length > 0) {
      error.value = 'У пациента уже есть СНИЛС / ИПРА. Измените существующий документ.'
      return
    }

    const snilsNumber = snilsForm.number.trim()
    const ipraNumber = snilsForm.ipra_number.trim()

    if (!snilsNumber) {
      error.value = 'Для СНИЛС обязателен номер.'
      return
    }

    const payload: ClientSnilsCreate = {
      number: snilsNumber,
      issued_date: snilsForm.ipra_date || null,
    }

    if (editingSnilsId.value) {
      await updateClientSnils(editingSnilsId.value, payload as ClientSnilsUpdate)
      successMessage.value = 'СНИЛС обновлен'
    } else {
      await createClientSnils(clientId, payload)
      successMessage.value = 'СНИЛС сохранен'
    }

    await updateClient(clientId, { ipra_code: ipraNumber || null })

    cancelSnilsEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('identity', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeSnils(snils: ClientSnils) {
  if (!selectedClient.value || !snils.snils_id) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить СНИЛС «${snils.number}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = getClientId(selectedClient.value)
    await deleteClientSnils(snils.snils_id)
    successMessage.value = 'СНИЛС / ИПРА удалены'
    cancelSnilsEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('identity', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function attachManagedReference(item: ReferenceItem) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''
  const tsrId = String(getReferenceId(item) || '')
  if (!clientId) {
    referenceError.value = 'Сначала сохрани карточку пациента.'
    return
  }
  if (!tsrId) return

  isReferenceSaving.value = true
  resetReferenceManagerMessages()
  try {
    await attachClientTsr(clientId, { tsr_id: tsrId })
    referenceSuccess.value = attachedTsrCounts.value.has(tsrId)
      ? 'Такой ТСР добавлен пациенту ещё раз.'
      : 'ТСР прикреплён к пациенту.'
    await refreshSelectedClient(clientId, false)
    if (loadedDetailTabs.modules) await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    referenceError.value = getApiErrorMessage(caughtError)
  } finally {
    isReferenceSaving.value = false
  }
}

async function saveClientTsrDetails(group: ClientTsrGroup) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''
  if (!clientId || !group.clientTsrId) return
  const draft = getClientTsrDraft(group)
  isSaving.value = true
  resetMessages()
  try {
    await updateClientTsr(clientId, group.clientTsrId, {
      check_date: draft.checkDate || null,
      certificate_price: draft.certificatePrice.trim() || null,
      prosthetist: draft.prosthetist || null,
    })
    delete clientTsrDrafts[group.clientTsrId]
    successMessage.value = 'Данные ТСР сохранены.'
    await refreshSelectedClient(clientId, false)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeClientTsrLink(group: ClientTsrGroup) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''
  if (!clientId || !group.clientTsrId) return
  if (!(await confirmAction({
    header: 'Открепить ТСР',
    message: `Открепить «${group.tsr}» от пациента? ТСР с закреплёнными комплектующими удалить нельзя.`,
    acceptLabel: 'Открепить',
    danger: true,
  }))) return

  isSaving.value = true
  resetMessages()
  try {
    await detachClientTsr(clientId, group.clientTsrId)
    delete clientTsrDrafts[group.clientTsrId]
    selectedContractClientTsrIds.value = selectedContractClientTsrIds.value.filter((id) => id !== group.clientTsrId)
    successMessage.value = 'ТСР откреплён от пациента.'
    await refreshSelectedClient(clientId, false)
    if (loadedDetailTabs.modules) await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function assignModule() {
  if (!selectedModuleId.value) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    const warehouseModule = selectedWarehouseModule.value
    const targetGroup = selectedComponentTsrGroup.value
    const tsrId = String(warehouseModule?.tsr_id ?? warehouseModule?.tsr?.id ?? '')
    if (!targetGroup) {
      throw new Error('Сначала выберите ТСР пациента.')
    }
    if (!warehouseModule) {
      throw new Error('Складская комплектующая не найдена.')
    }
    if (tsrId && tsrId !== targetGroup.tsrId) {
      throw new Error('Выбранная складская комплектующая относится к другому ТСР.')
    }
    const operationQuantity = parseModuleOperationQuantity(warehouseModule, warehouseAssignQuantity.value)
    await updateModule(selectedModuleId.value, {
      client_id: clientId,
      tsr_id: targetGroup.tsrId,
      client_tsr_id: targetGroup.clientTsrId,
    }, operationQuantity)
    selectedModuleId.value = ''
    warehouseAssignQuantity.value = '1'
    successMessage.value = `К пациенту привязано: ${operationQuantity} шт.`
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function unassignModule(moduleItem: ModuleItem) {
  if (!selectedClient.value || !moduleItem.module_id) {
    return
  }

  let operationQuantity: number
  try {
    operationQuantity = parseModuleOperationQuantity(moduleItem, getModuleOperationQuantity(moduleItem))
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : 'Проверьте количество.'
    return
  }

  if (!(await confirmAction({
    header: 'Вернуть на склад',
    message: `Отвязать ${operationQuantity} шт. «${getModuleName(moduleItem)}» от пациента и вернуть на склад?`,
    acceptLabel: 'Вернуть на склад',
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await updateModule(moduleItem.module_id, { client_id: null }, operationQuantity)
    successMessage.value = `На склад возвращено: ${operationQuantity} шт.`
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function changeClientModulesProsthetistState(
  group: ClientTsrGroup,
  componentIds: string[],
  atProsthetist: boolean,
) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''
  if (!clientId || !group.clientTsrId || componentIds.length === 0 || isSaving.value) return

  isSaving.value = true
  resetMessages()

  try {
    await setClientComponentsProsthetistState(clientId, {
      client_tsr_id: group.clientTsrId,
      component_ids: componentIds,
      at_prosthetist: atProsthetist,
    })
    successMessage.value = atProsthetist
      ? `Передано протезисту: ${componentIds.length} поз.`
      : `Возвращено от протезиста: ${componentIds.length} поз.`
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
    await loadClientTabData('modules', true)
  } finally {
    isSaving.value = false
  }
}

function handleGroupProsthetistStateChange(group: ClientTsrGroup, event: Event) {
  void changeClientModulesProsthetistState(
    group,
    getGroupComponentIds(group),
    (event.target as HTMLInputElement).checked,
  )
}

function handleModuleProsthetistStateChange(group: ClientTsrGroup, moduleItem: ModuleItem, event: Event) {
  const componentId = String(moduleItem.module_id ?? '')
  if (!componentId) return
  void changeClientModulesProsthetistState(
    group,
    [componentId],
    (event.target as HTMLInputElement).checked,
  )
}

async function saveClientModule() {
  resetMessages()

  if (!validateModuleForm()) {
    return
  }

  isSaving.value = true

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    const payload = buildModulePayload(clientId)

    if (editingModuleId.value) {
      await updateModule(editingModuleId.value, payload as ModuleUpdatePayload)
      successMessage.value = 'Комплектующая обновлена'
    } else {
      await createModule(payload)
      successMessage.value = 'Комплектующая создана и привязана к пациенту'
    }

    resetModuleForm()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function openComponentFromMain(moduleItem: ModuleItem) {
  if (!(await openClientTab('modules'))) {
    return
  }
  const current = clientModules.value.find((item) => String(item.module_id) === String(moduleItem.module_id)) ?? moduleItem
  fillModuleForm(current)
  requestAnimationFrame(() => {
    document.getElementById('client-component-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function openNewComponentFromTsr(group: ClientTsrGroup) {
  if (!(await openClientTab('modules'))) {
    return
  }
  const refreshedGroup = clientTsrGroups.value.find((item) => item.clientTsrId === group.clientTsrId) ?? group
  prepareNewComponentForTsr(refreshedGroup)
  requestAnimationFrame(() => {
    document.getElementById('client-component-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function removeClientModule(moduleItem: ModuleItem) {
  if (!selectedClient.value || !moduleItem.module_id) {
    return
  }

  let operationQuantity: number
  try {
    operationQuantity = parseModuleOperationQuantity(moduleItem, getModuleOperationQuantity(moduleItem))
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : 'Проверьте количество.'
    return
  }

  if (!(await confirmAction({
    message: `Удалить ${operationQuantity} шт. комплектующей «${getModuleName(moduleItem)}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = getClientId(selectedClient.value)
    await deleteModule(moduleItem.module_id, operationQuantity)
    successMessage.value = `Удалено комплектующих: ${operationQuantity} шт.`
    resetModuleForm()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null

  selectedFile.value = null
  resetMessages()

  if (!file) {
    return
  }

  if (!ALLOWED_UPLOAD_TYPES.has(file.type)) {
    input.value = ''
    error.value = 'Можно загрузить только PDF, PNG, JPG/JPEG или DOCX.'
    return
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    input.value = ''
    error.value = 'Файл слишком большой. Максимальный размер — 25 МБ.'
    return
  }

  selectedFile.value = file
}

async function uploadDocument() {
  if (!selectedFile.value) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    await uploadClientDocument(clientId, selectedFile.value)
    selectedFile.value = null
    successMessage.value = 'Документ загружен'
    await loadClientTabData('documents', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function generateContract() {
  resetMessages()

  const prefix = contractNumberPrefix.value.trim().toUpperCase()
  const suffix = contractNumberSuffix.value.trim()

  if (!contractType.value.trim() || !prefix || !suffix || !contractDate.value.trim()) {
    error.value = 'Для формирования договора выбери тип, буквенную часть номера и дату.'
    return
  }

  if (!/^\d+$/.test(suffix)) {
    error.value = 'Числовая часть номера договора должна содержать только цифры.'
    return
  }

  if (showExtendedContractDates.value && selectedContractClientTsrIds.value.length === 0) {
    error.value = 'Для договора ООО выберите хотя бы один ТСР пациента.'
    return
  }

  isSaving.value = true

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    if (showExtendedContractDates.value) {
      // Стоимость сертификата редактируется в карточке ТСР как черновик.
      // Перед генерацией сохраняем выбранные черновики автоматически, чтобы
      // договор всегда использовал именно те значения, которые видит пользователь.
      await persistSelectedContractTsrDrafts(clientId)
      await refreshSelectedClient(clientId, false)
    }

    const payload: ContractGenerationPayload = {
      template_type: contractType.value.trim(),
      document_number: `${prefix}/${suffix}`,
      document_number_prefix: prefix,
      document_number_suffix: suffix,
      document_date: formatContractDate(contractDate.value.trim()),
      plan_date: showExtendedContractDates.value && contractPlanDate.value.trim()
        ? formatContractDate(contractPlanDate.value.trim())
        : formatContractDate(contractDate.value.trim()),
      appendix_number: '1',
      appendix_date: showExtendedContractDates.value && contractAppendixDate.value.trim()
        ? formatContractDate(contractAppendixDate.value.trim())
        : formatContractDate(contractDate.value.trim()),
      selected_client_tsr_ids: showExtendedContractDates.value ? selectedContractClientTsrIds.value : [],
      selected_tsr_ids: showExtendedContractDates.value
        ? [...new Set(contractTsrGroups.value
          .filter((group) => selectedContractClientTsrIds.value.includes(group.clientTsrId))
          .map((group) => group.tsrId))]
        : [],
      selected_module_ids: showExtendedContractDates.value ? selectedContractModuleIds.value : [],
    }

    await generateClientContract(clientId, payload)
    successMessage.value = 'Договор сформирован'
    await loadClientTabData('documents', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function generateMtzFromClientCard() {
  resetMessages()

  const requiredValues = [
    mtzType.value,
    mtzNumber.value,
    mtzDate.value,
    mtzDisabilityGroupReason.value,
    mtzCertificateReference.value,
    mtzDiagnosis.value,
    mtzAmputationLevel.value,
    mtzWeightKg.value,
  ]
  if (requiredValues.some((value) => !String(value).trim())) {
    error.value = 'Для МТЗ заполните номер, дату, группу/причину инвалидности, справку, диагноз, уровень ампутации и вес.'
    return
  }

  isSaving.value = true
  try {
    const clientId = await ensureClientExists()
    if (!clientId) return

    await generateClientMtz(clientId, {
      template_type: mtzType.value,
      mtz_number: mtzNumber.value.trim(),
      document_date: mtzDate.value,
      disability_group_reason: mtzDisabilityGroupReason.value.trim(),
      certificate_reference: mtzCertificateReference.value.trim(),
      diagnosis: mtzDiagnosis.value.trim(),
      amputation_level: mtzAmputationLevel.value.trim(),
      weight_kg: mtzWeightKg.value.trim(),
    })

    await loadClientTabData('documents', true)
    successMessage.value = 'МТЗ сформировано. Скачать его можно в списке документов ниже.'
    rememberDetailTabState('documents')
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeDocument(document: ClientDocument) {
  if (!selectedClient.value || !document.document_id) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить документ «${getDocumentName(document)}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteDocument(document.document_id)
    successMessage.value = 'Документ удален'
    await loadClientTabData('documents', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function downloadDocument(document: ClientDocument) {
  if (!document.document_id) {
    return
  }

  resetMessages()

  try {
    const { blob, contentDisposition } = await downloadDocumentBlob(document.document_id)
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = getFilenameFromDisposition(contentDisposition) || getDocumentName(document)
    link.click()
    URL.revokeObjectURL(url)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  }
}

watch(isClientCardOpen, (isOpen) => {
  setBodyModalLock(isOpen)
})

watch([query, pageLimit, clientColumnFilters], () => { currentPage.value = 1 }, { deep: true })

watch(
  () => route.query.client_id,
  (clientId) => {
    void openClientFromRoute(clientId)
  },
)

async function loadContractTemplates() {
  try {
    const templates = await fetchContractTemplates()
    if (templates.length > 0) {
      contractTemplateOptions.value = templates
    }
  } catch {
    return
  }
}

async function loadMtzTemplateOptions() {
  try {
    const templates = await fetchMtzTemplates()
    mtzTemplateOptions.value = templates
    if (templates.length > 0 && !templates.some((item) => item.value === mtzType.value)) {
      mtzType.value = templates[0].value
    }
  } catch {
    mtzTemplateOptions.value = []
  }
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasUnsavedClientChanges.value) {
    return
  }

  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(async () => {
  if (!hasUnsavedClientChanges.value) {
    return true
  }

  return confirmAction({
    header: 'Есть несохранённые изменения',
    message: `Покинуть страницу без сохранения изменений в разделах: ${dirtyClientTabs.value.map((tab) => CLIENT_TAB_LABELS[tab]).join(', ')}?`,
    acceptLabel: 'Покинуть без сохранения',
  })
})

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  await Promise.all([loadClients(), loadReferences(), loadContractTemplates(), loadMtzTemplateOptions()])
  await openClientFromRoute(route.query.client_id)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  setBodyModalLock(false)
})
</script>

<template>
  <section class="page-section entity-workspace-page clients-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">база пациентов</p>
        <h1>Пациенты</h1>
        <p class="muted page-subtitle">
          Контролируйте текущий этап, документы, сроки и комплектующие в одной карточке.
        </p>
      </div>
      <button
        v-if="activeClientListMode === 'active'"
        class="primary-button"
        type="button"
        @click="openNewClient"
      >
        <Plus :size="16" aria-hidden="true" />
        Создать пациента
      </button>
    </div>

    <div class="tabs" role="tablist" aria-label="Разделы пациентов">
      <button :class="{ active: activeClientListMode === 'active' }" type="button" @click="switchClientListMode('active')">
        В работе
      </button>
      <button :class="{ active: activeClientListMode === 'archive' }" type="button" @click="switchClientListMode('archive')">
        Выполненные
      </button>
    </div>

    <form class="toolbar-form clients-toolbar" @submit.prevent="applyClientFilters">
      <div class="toolbar-search-wrap">
        <Search :size="17" aria-hidden="true" />
        <input v-model="query" aria-label="Поиск пациента" placeholder="ФИО, телефон, паспорт, СНИЛС, ТСР или данные пациента" />
      </div>
      <label class="filter-label">
        <span>На странице</span>
        <select v-model.number="pageLimit" @change="applyClientFilters">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
        </select>
      </label>
      <div class="filter-actions">
        <button class="secondary-button" type="submit" :disabled="isLoading">
          <Search :size="15" aria-hidden="true" />
          Применить
        </button>
        <button v-if="activeClientFilterCount" class="ghost-button" type="button" @click="resetClientFilters">
          <X :size="15" aria-hidden="true" />
          Сбросить
        </button>
        <span v-if="activeClientFilterCount" class="filter-count">{{ activeClientFilterCount }}</span>
      </div>
    </form>

    <p v-if="error && !isClientCardOpen" class="form-error">{{ error }}</p>
    <p v-if="successMessage && !isClientCardOpen" class="form-success">{{ successMessage }}</p>

    <div v-if="selectedClientIds.length" class="bulk-action-bar">
      <strong>Выбрано пациентов: {{ selectedClientIds.length }}</strong>
      <div class="row-actions">
        <button
          v-if="activeClientListMode === 'active'"
          class="secondary-button"
          type="button"
          :disabled="isSaving"
          @click="runBulkClientAction('archive')"
        >
          В Выполненные
        </button>
        <button
          v-else
          class="secondary-button"
          type="button"
          :disabled="isSaving"
          @click="runBulkClientAction('restore')"
        >
          Восстановить
        </button>
        <button class="ghost-button danger-button" type="button" :disabled="isSaving" @click="runBulkClientAction('delete')">Удалить</button>
        <button class="ghost-button" type="button" :disabled="isSaving" @click="selectedClientIds = []">Снять выбор</button>
      </div>
    </div>

    <div class="table-wrap desktop-entity-table">
      <table>
        <thead>
          <tr>
            <th class="selection-cell">
              <input
                type="checkbox"
                aria-label="Выбрать всех пациентов на странице"
                :checked="allPagedClientsSelected"
                @change="handleToggleAllClients"
              />
            </th>
            <SortableFilterHeader label="№" column-key="number" :filterable="false" :sort-key="clientSortKey" :sort-direction="clientSortDirection" @sort="sortClients" />
            <SortableFilterHeader label="Пациент" column-key="patient" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.patient" @sort="sortClients" @update:filter-value="clientColumnFilters.patient = $event" />
            <SortableFilterHeader class="client-col-prosthetist" label="Протезист" column-key="prosthetist" placeholder="Имя протезиста" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.prosthetist" @sort="sortClients" @update:filter-value="clientColumnFilters.prosthetist = $event" />
            <SortableFilterHeader label="ТСР" column-key="tsr" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.tsr" @sort="sortClients" @update:filter-value="clientColumnFilters.tsr = $event" />
            <SortableFilterHeader class="client-col-check-date" label="Дата пробития" column-key="check_date" filter-kind="date" placeholder="дд.мм.гггг или от..до" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.check_date" @sort="sortClients" @update:filter-value="clientColumnFilters.check_date = $event" />
            <SortableFilterHeader label="Сертификат" column-key="certificate" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.certificate" @sort="sortClients" @update:filter-value="clientColumnFilters.certificate = $event" />
            <SortableFilterHeader label="Статус" column-key="status" filter-kind="select" :options="clientStatusFilterOptions" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.status" @sort="sortClients" @update:filter-value="clientColumnFilters.status = $event" />
            <SortableFilterHeader label="Этап" column-key="stage" filter-kind="select" :options="clientStageFilterOptions" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.stage" @sort="sortClients" @update:filter-value="clientColumnFilters.stage = $event" />
            <SortableFilterHeader class="client-col-document-status" label="Статус договоров" column-key="contract_status" filter-kind="select" :options="DOCUMENT_STATUS_OPTIONS" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.contract_status" @sort="sortClients" @update:filter-value="clientColumnFilters.contract_status = $event" />
            <SortableFilterHeader class="client-col-document-status" label="Статус актов" column-key="act_status" filter-kind="select" :options="DOCUMENT_STATUS_OPTIONS" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.act_status" @sort="sortClients" @update:filter-value="clientColumnFilters.act_status = $event" />
            <SortableFilterHeader label="Агент" column-key="agent" filter-kind="select" :options="clientAgentFilterOptions" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.agent" @sort="sortClients" @update:filter-value="clientColumnFilters.agent = $event" />
            <SortableFilterHeader label="Повторное протезирование" column-key="repeat_visit" filter-kind="date" placeholder="дд.мм.гггг или от..до" :sort-key="clientSortKey" :sort-direction="clientSortDirection" :filter-value="clientColumnFilters.repeat_visit" @sort="sortClients" @update:filter-value="clientColumnFilters.repeat_visit = $event" />
            <th aria-label="Действия"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading" class="no-row-action">
            <td colspan="14">Загружаем пациентов...</td>
          </tr>
          <tr
            v-for="(client, index) in pagedClients"
            v-else
            :key="String(client.client_id ?? client.external_id)"
            :class="{ selected: isClientSelected(client) || (selectedClient && getClientId(selectedClient) === getClientId(client)) }"
            tabindex="0"
            @click="selectClient(client)"
            @keydown.enter="selectClient(client)"
          >
            <td class="selection-cell" @click.stop>
              <input
                type="checkbox"
                :aria-label="`Выбрать пациента: ${getClientName(client)}`"
                :checked="isClientSelected(client)"
                @change="handleToggleClient(client, $event)"
              />
            </td>
            <td>{{ currentSkip + index + 1 }}</td>
            <td class="entity-cell">
              <div class="entity-primary">
                <span class="entity-avatar">{{ getClientInitials(client) }}</span>
                <span class="entity-copy">
                  <strong>{{ getClientName(client) }}</strong>
                  <span>{{ getClientPrimaryPhone(client) }}</span>
                </span>
              </div>
            </td>
            <td class="client-col-prosthetist">{{ getClientProsthetistLabel(client) }}</td>
            <td class="table-tsr">{{ getClientTsrLabel(client) }}</td>
            <td class="client-col-check-date">{{ getClientDate(client) }}</td>
            <td class="table-money">{{ formatMoney(getClientCertificateTotal(client)) }}</td>
            <td><StatusPill :label="getClientStatusLabel(client)" kind="status" /></td>
            <td><StatusPill :label="getClientStageLabel(client)" kind="stage" /></td>
            <td class="client-col-document-status" @click.stop>
              <select
                class="client-document-status-select"
                :value="client.contract_status ?? ''"
                :disabled="isSaving || isInlineDocumentStatusSaving(client)"
                :aria-label="`Статус договоров: ${getClientName(client)}`"
                @click.stop
                @keydown.stop
                @change="updateClientDocumentStatus(client, 'contract_status', $event)"
              >
                <option value="" disabled>Не выбран</option>
                <option v-for="option in DOCUMENT_STATUS_OPTIONS" :key="`contract-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </td>
            <td class="client-col-document-status" @click.stop>
              <select
                class="client-document-status-select"
                :value="client.act_status ?? ''"
                :disabled="isSaving || isInlineDocumentStatusSaving(client)"
                :aria-label="`Статус актов: ${getClientName(client)}`"
                @click.stop
                @keydown.stop
                @change="updateClientDocumentStatus(client, 'act_status', $event)"
              >
                <option value="" disabled>Не выбран</option>
                <option v-for="option in DOCUMENT_STATUS_OPTIONS" :key="`act-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </td>
            <td>{{ getAgentLabel(client.agent_id) }}</td>
            <td>{{ getClientDeadline(client) }}</td>
            <td class="table-actions-cell">
              <ActionMenu :items="getClientActions(client)" :label="`Действия: ${getClientName(client)}`" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!isLoading" class="mobile-entity-list">
      <article
        v-for="client in pagedClients"
        :key="String(client.client_id ?? client.external_id)"
        class="mobile-entity-card"
        @click="selectClient(client)"
      >
        <div class="mobile-entity-card-header">
          <div class="entity-primary">
            <span class="entity-avatar">{{ getClientInitials(client) }}</span>
            <span class="entity-copy">
              <strong>{{ getClientName(client) }}</strong>
              <span>{{ getClientPrimaryPhone(client) }}</span>
            </span>
          </div>
          <ActionMenu :items="getClientActions(client)" :label="`Действия: ${getClientName(client)}`" />
        </div>
        <div class="mobile-entity-card-details">
          <span>Дата пробития <strong>{{ getClientDate(client) }}</strong></span>
          <span>Статус <strong><StatusPill :label="getClientStatusLabel(client)" kind="status" /></strong></span>
          <span>Этап <strong><StatusPill :label="getClientStageLabel(client)" kind="stage" /></strong></span>
          <span>Статус договоров <strong>{{ getClientDocumentStatusLabel(client.contract_status) }}</strong></span>
          <span>Статус актов <strong>{{ getClientDocumentStatusLabel(client.act_status) }}</strong></span>
          <span>Агент <strong>{{ getAgentLabel(client.agent_id) }}</strong></span>
          <span>Повторное протезирование<strong>{{ getClientDeadline(client) }}</strong></span>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!isLoading && filteredClients.length === 0"
      title="Пациенты не найдены"
      :description="activeClientFilterCount ? 'Измените или сбросьте фильтры.' : 'Создайте первую карточку пациента.'"
    >
      <button v-if="activeClientFilterCount" class="secondary-button" type="button" @click="resetClientFilters">
        Сбросить фильтры
      </button>
    </EmptyState>

    <div class="pagination-bar" aria-label="Пагинация пациентов">
      <span>Страница {{ currentPage }} · показано {{ pagedClients.length }} из {{ filteredClients.length }} · записи {{ pagedClients.length ? currentSkip + 1 : 0 }}–{{ currentSkip + pagedClients.length }}</span>
      <div class="row-actions">
        <button class="secondary-button" type="button" :disabled="isLoading || !hasPreviousPage" @click="goToPreviousClientsPage">
          Назад
        </button>
        <button class="secondary-button" type="button" :disabled="isLoading || !hasNextPage" @click="goToNextClientsPage">
          Вперед
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="isClientCardOpen" class="modal-backdrop client-card-backdrop" @click.self="closeClientCard" @keydown.esc.window="handleClientModalEscape">
        <section v-focus-trap class="modal-panel client-modal client-modal-panel entity-modal client-profile-modal" role="dialog" aria-modal="true" aria-label="Карточка клиента" :aria-describedby="modalMessageId" :aria-busy="isSaving" @click.stop>
          <div class="modal-header">
            <div>
              <p class="eyebrow">{{ isEditing ? 'Карточка пациента' : 'Новый пациент' }}</p>
              <h2>{{ isEditing && selectedClient ? getClientName(selectedClient) : 'Создать пациента' }}</h2>
            </div>
            <div class="row-actions">
              <button
                v-if="selectedClient && isClientPersisted"
                class="secondary-button"
                type="button"
                :disabled="isSaving"
                @click="changeClientArchiveState(selectedClient, !selectedClient.is_archived)"
              >
                <RotateCcw v-if="selectedClient.is_archived" :size="15" aria-hidden="true" />
                <Archive v-else :size="15" aria-hidden="true" />
                {{ selectedClient.is_archived ? 'Восстановить' : 'В Выполненные' }}
              </button>
              <button
                v-if="activeClientListMode === 'active'"
                class="ghost-button"
                type="button"
                :disabled="isSaving"
                @click="openNewClient"
              >
                <Plus :size="15" aria-hidden="true" />
                Новый
              </button>
              <button
                class="icon-button"
                type="button"
                :disabled="isSaving"
                aria-label="Закрыть карточку"
                title="Закрыть"
                @click="closeClientCard"
              >
                <X :size="18" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div class="client-modal-body">
            <nav class="client-modal-nav" role="tablist" aria-label="Разделы карточки пациента">
              <button :class="{ active: activeTab === 'main' }" type="button" @click="openClientTab('main')">
                <UserRound :size="17" aria-hidden="true" />
                Основное
              </button>
              <button :class="{ active: activeTab === 'identity' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('identity')">
                <IdCard :size="17" aria-hidden="true" />
                Личные документы
              </button>
              <button :class="{ active: activeTab === 'phones' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('phones')">
                <Mail :size="17" aria-hidden="true" />
                Контакты
              </button>
              <button :class="{ active: activeTab === 'modules' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('modules')">
                <PackageOpen :size="17" aria-hidden="true" />
                Комплектующие
              </button>
              <button :class="{ active: activeTab === 'documents' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('documents')">
                <Files :size="17" aria-hidden="true" />
                Документы
              </button>
              <button :class="{ active: activeTab === 'history' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('history')">
                <History :size="17" aria-hidden="true" />
                История
              </button>
            </nav>

            <div class="client-modal-content">
              <p v-if="error" id="client-modal-error" class="form-error">{{ error }}</p>
              <p v-if="successMessage" id="client-modal-success" class="form-success">{{ successMessage }}</p>

              <p v-if="!isEditing" class="form-hint">
                Сначала сохраните основные данные. После создания станут доступны телефоны,
                документы, комплектующие и история.
              </p>

              <form id="client-main-form" v-if="activeTab === 'main'" class="side-form flat-form" @submit.prevent="saveClient">
          <div class="form-grid">
            <label>
              Фамилия
              <input v-model="form.last_name" required />
            </label>
            <label>
              Имя
              <input v-model="form.first_name" required />
            </label>
            <label>
              Отчество
              <input v-model="form.middle_name" />
            </label>
          </div>

          <div class="form-grid">
            <label>
              Статус
              <select v-model="form.status" required>
                <option value="">Выбери статус</option>
                <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Этап
              <select v-model="form.current_stage" required>
                <option value="">Выбери этап</option>
                <option v-for="option in stageOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Диагноз
              <select v-model="form.prosthesis_type">
                <option value="">Выбери диагноз</option>
                <option v-for="option in prosthesisOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>

          <div class="form-grid client-document-status-grid">
            <label>
              Статус договоров
              <select v-model="form.contract_status">
                <option value="">Не выбран</option>
                <option v-for="option in DOCUMENT_STATUS_OPTIONS" :key="`form-contract-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Статус актов
              <select v-model="form.act_status">
                <option value="">Не выбран</option>
                <option v-for="option in DOCUMENT_STATUS_OPTIONS" :key="`form-act-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>

          <div class="form-grid client-main-assignment-grid">
            <label>
              Агент
              <select v-model="form.agent_id">
                <option value="">Не выбран</option>
                <option v-for="agent in agents" :key="String(agent.agent_id)" :value="agent.agent_id">
                  {{ getAgentName(agent) }}
                </option>
              </select>
            </label>
            <label>
              Налогообложение
              <select v-model="form.taxation_system">
                <option value="УСН">6%</option>
                <option value="ОСНО">15%</option>
              </select>
            </label>
          </div>

          <div class="form-heading">
            <div>
              <h2>ТСР пациента</h2>
              <p class="muted">Один и тот же ТСР можно добавить пациенту несколько раз. Дата пробития, сертификат и комплектующие хранятся отдельно для каждой добавленной карточки.</p>
            </div>
            <button
              class="secondary-button"
              type="button"
              :disabled="!isClientPersisted"
              @click="openReferenceManager"
            >
              Справочник ТСР
            </button>
          </div>

          <div class="detail-panel tsr-module-panel">
            <div v-if="clientTsrGroups.some((group) => group.clientTsrId)" class="tsr-component-groups">
              <article
                v-for="(group, groupIndex) in clientTsrGroups.filter((item) => item.clientTsrId)"
                :key="group.key"
                class="tsr-component-group client-tsr-gradient-card"
                :style="getClientTsrCardStyle(groupIndex)"
              >
                <header class="tsr-component-header">
                  <div>
                    <button class="link-button tsr-title-link" type="button" @click="openNewComponentFromTsr(group)">
                      <strong>{{ group.tsr }}</strong>
                    </button>
                    <span>Комплектующих: {{ getGroupComponentUnitCount(group) }}</span>
                  </div>
                  <div class="row-actions">
                    <button class="ghost-button" type="button" :disabled="isSaving" @click="openNewComponentFromTsr(group)">
                      Добавить комплектующую
                    </button>
                    <button class="secondary-button" type="button" :disabled="isSaving" @click="saveClientTsrDetails(group)">Сохранить</button>
                    <button class="danger-button" type="button" :disabled="isSaving" @click="removeClientTsrLink(group)">Открепить</button>
                  </div>
                </header>
                <div class="client-tsr-editor-layout">
                  <section class="client-tsr-info-section" aria-label="Сертификат и сроки">
                    <span class="client-tsr-section-title">Сертификат и сроки</span>
                    <div class="client-tsr-field-grid client-tsr-certificate-grid">
                      <label class="client-tsr-date-field">
                        <span class="client-tsr-field-label">Дата пробития</span>
                        <DateInput
                          :model-value="getClientTsrDraft(group).checkDate"
                          :aria-label="`Дата пробития для ${group.tsr}`"
                          @update:model-value="setClientTsrDraft(group, 'checkDate', $event)"
                        />
                      </label>
                      <label class="client-tsr-certificate-field">
                        <span class="client-tsr-field-label">Стоимость сертификата</span>
                        <input
                          class="client-tsr-certificate-input"
                          :value="getClientTsrDraft(group).certificatePrice"
                          inputmode="decimal"
                          placeholder="Например: 250 000"
                          @input="setClientTsrDraftFromEvent(group, 'certificatePrice', $event)"
                        />
                      </label>
                    </div>
                  </section>

                  <section class="client-tsr-info-section client-tsr-assignment-section" aria-label="Протезист и повторное обращение">
                    <span class="client-tsr-section-title">Протезист и повторное протезирование</span>
                    <div class="client-tsr-field-grid client-tsr-assignment-fields">
                      <label class="client-tsr-prosthetist-field">
                        <span class="client-tsr-field-label">Протезист</span>
                        <select
                          :value="getClientTsrDraft(group).prosthetist"
                          @change="setClientTsrDraftFromEvent(group, 'prosthetist', $event)"
                        >
                          <option value="">Не выбран</option>
                          <option value="Дмитрий">Дмитрий</option>
                          <option value="Никита">Никита</option>
                        </select>
                      </label>
                      <div class="client-tsr-address-card">
                        <span>Адрес протезиста</span>
                        <strong>{{ getProsthetistAddress(getClientTsrDraft(group).prosthetist, group.placeOfResidence) }}</strong>
                      </div>
                      <label class="client-tsr-repeat-field">
                        <span class="client-tsr-field-label">Повторное протезирование</span>
                        <DateInput
                          :model-value="getClientTsrDraft(group).repeatVisitDate"
                          :aria-label="`Повторное протезирование для ${group.tsr}`"
                          disabled
                          @update:model-value="setClientTsrDraft(group, 'repeatVisitDate', $event)"
                        />
                        <small v-if="hasAutomaticRepeatVisitTerm(group.tsr)" class="form-hint">Рассчитывается автоматически по сроку ТСР.</small>
                        <small v-else class="form-hint">Для этого кода ТСР срок повторного протезирования отсутствует в таблице сроков. Ручной ввод отключён.</small>
                      </label>
                    </div>
                  </section>
                </div>

                <ul v-if="group.components.length" class="component-name-list">
                  <li v-for="component in group.components" :key="String(component.module_id)">
                    <button class="link-button component-name-link" type="button" @click="openComponentFromMain(component)">
                      <strong>{{ getModuleName(component) }}</strong>
                    </button>
                    <span>{{ component.supplier || 'Поставщик не указан' }}</span>
                    <span class="component-finance-line">
                      Себестоимость: {{ formatMoney(component.cost) }} ·
                      Цена: {{ formatMoney(component.price) }} ·
                      Количество: {{ component.quantity ?? 1 }}
                    </span>
                    <span class="component-characteristics-line">
                      Размер: {{ component.size || '—' }} ·
                      Жесткость: {{ component.stiffness || '—' }} ·
                      Сторона: {{ component.side || '—' }}
                    </span>
                  </li>
                </ul>
                <p v-else class="muted">Комплектующие к этому ТСР пока не добавлены.</p>
              </article>
            </div>
            <p v-else class="muted">Сохрани пациента и прикрепи нужные коды через «Справочник ТСР».</p>
          </div>

          <label>
            Заметки
            <textarea v-model="form.notes" rows="4" />
          </label>
        </form>

        <div v-else-if="activeTab === 'identity'" class="detail-panel identity-section">
          <form class="side-form flat-form collapsible-form" @submit.prevent="savePassport">
            <div class="form-heading collapsible-form-heading">
              <div>
                <h2>Паспорт</h2>
              </div>
              <button
                class="ghost-button"
                type="button"
                :disabled="passportItems.length > 0 && !editingPassportId"
                @click="passportFormExpanded = !passportFormExpanded"
              >
                {{ passportItems.length > 0 && !editingPassportId ? 'Паспорт уже сохранён' : passportFormExpanded ? 'Свернуть' : 'Развернуть форму' }}
              </button>
            </div>
            <div v-show="passportFormExpanded" class="collapsible-form-body">
              <div class="form-grid">
                <label>
                Серия
                <input
                  :value="passportForm.series"
                  @input="(e) => { passportForm.series = sanitizeSeries((e.target as HTMLInputElement).value) }"
                  @blur="passportForm.series = formatSeries(passportForm.series)"
                />
                </label>
                <label>
                Номер
                <input
                  :value="passportForm.number"
                  @input="(e) => { passportForm.number = sanitizeDigits((e.target as HTMLInputElement).value, 6) }"
                  @blur="passportForm.number = passportForm.number.trim()"
                />
              </label>
                <label>Место рождения<input v-model="passportForm.birth_place" /></label>
              </div>
              <div class="form-grid">
                <label>Дата рождения<DateInput v-model="passportForm.birth_date" aria-label="Дата рождения" /></label>
                <label>
                Код подразделения
                <input
                  :value="passportForm.department_code"
                  @input="(e) => { passportForm.department_code = sanitizeDigits((e.target as HTMLInputElement).value, 6) }"
                  @blur="passportForm.department_code = formatDepartmentCode(passportForm.department_code)"
                />
              </label>
                <label>Дата выдачи<DateInput v-model="passportForm.issue_date" aria-label="Дата выдачи паспорта" /></label>
              </div>
              <div class="form-grid">
                <label>Кем выдан<input v-model="passportForm.issued_by" /></label>
                <label>Адрес регистрации<input v-model="passportForm.registration_address" /></label>
              </div>
              <div class="row-actions">
                <button class="secondary-button" :disabled="isSaving" type="submit">{{ editingPassportId ? 'Обновить паспорт' : 'Сохранить паспорт' }}</button>
                <button v-if="editingPassportId" class="ghost-button" type="button" @click="cancelPassportEdit">Отмена</button>
              </div>
            </div>
          </form>

          <div class="identity-card-list">
            <article v-for="passport in passportItems" :key="String(passport.passport_id)" class="identity-document-card">
              <header>
                <div>
                  <span class="identity-card-label">Паспорт</span>
                  <strong>{{ passport.series_number }}</strong>
                </div>
                <div class="row-actions">
                  <button class="ghost-button" type="button" @click="startEditPassport(passport)">Изм.</button>
                  <button class="danger-button" :disabled="isSaving" type="button" @click="removePassport(passport)">Удалить</button>
                </div>
              </header>
              <dl class="identity-details-grid">
                <div><dt>Владелец</dt><dd>{{ passport.full_name }}</dd></div>
                <div><dt>Дата рождения</dt><dd>{{ formatShortDate(passport.birth_date) }}</dd></div>
                <div><dt>Дата выдачи</dt><dd>{{ formatShortDate(passport.issue_date) }}</dd></div>
                <div><dt>Кем выдан</dt><dd>{{ passport.issued_by }}</dd></div>
                <div><dt>Код подразделения</dt><dd>{{ passport.department_code || '—' }}</dd></div>
                <div><dt>Адрес регистрации</dt><dd>{{ passport.registration_address }}</dd></div>
              </dl>
            </article>
            <p v-if="passportItems.length === 0" class="muted">Паспорта пока не сохранены.</p>
          </div>

          <form class="side-form flat-form collapsible-form" @submit.prevent="saveSnils">
            <div class="form-heading collapsible-form-heading">
              <div>
                <h2>СНИЛС / ИПРА</h2>
              </div>
              <button
                class="ghost-button"
                type="button"
                :disabled="snilsItems.length > 0 && !editingSnilsId"
                @click="snilsFormExpanded = !snilsFormExpanded"
              >
                {{ snilsItems.length > 0 && !editingSnilsId ? 'СНИЛС / ИПРА уже сохранены' : snilsFormExpanded ? 'Свернуть' : 'Развернуть форму' }}
              </button>
            </div>
            <div v-show="snilsFormExpanded" class="collapsible-form-body">
              <div class="form-grid">
                <label>
                СНИЛС
                <input
                  :value="snilsForm.number"
                  @input="(e) => { snilsForm.number = sanitizeDigits((e.target as HTMLInputElement).value, 11) }"
                  @blur="snilsForm.number = formatSnils(snilsForm.number)"
                />
                </label>
                <label>
                  Номер ИПРА
                  <input
                    :value="snilsForm.ipra_number"
                    @input="(e) => { 
                      // Удаляем всё, кроме цифр (префикс добавится при blur)
                      snilsForm.ipra_number = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 12);
                    }"
                    @blur="snilsForm.ipra_number = formatIpraNumber(snilsForm.ipra_number)"
                  />
                </label>
                <label>Дата ИПРА<DateInput v-model="snilsForm.ipra_date" aria-label="Дата ИПРА" /></label>
              </div>
              <div class="row-actions">
                <button class="secondary-button" :disabled="isSaving" type="submit">{{ editingSnilsId ? 'Обновить СНИЛС / ИПРА' : 'Сохранить СНИЛС / ИПРА' }}</button>
                <button v-if="editingSnilsId" class="ghost-button" type="button" @click="cancelSnilsEdit">Отмена</button>
              </div>
            </div>
          </form>

          <div class="identity-card-list">
            <article v-for="snils in snilsItems" :key="String(snils.snils_id)" class="identity-document-card">
              <header>
                <div>
                  <span class="identity-card-label">СНИЛС</span>
                  <strong>{{ snils.number }}</strong>
                </div>
                <div class="row-actions">
                  <button class="ghost-button" type="button" @click="startEditSnils(snils)">Изм.</button>
                  <button class="danger-button" :disabled="isSaving" type="button" @click="removeSnils(snils)">Удалить</button>
                </div>
              </header>
              <dl class="identity-details-grid">
                <div><dt>Номер ИПРА</dt><dd>{{ selectedClient?.ipra_code || '—' }}</dd></div>
                <div><dt>Дата ИПРА</dt><dd>{{ formatShortDate(snils.issued_date) }}</dd></div>
              </dl>
            </article>
            <p v-if="snilsItems.length === 0" class="muted">СНИЛС / ИПРА пока не сохранены.</p>
          </div>
        </div>

        <div v-else-if="activeTab === 'phones'" class="detail-panel">
          <p v-if="isTabLoading('phones')" class="muted">Загружаем контакты...</p>
          <div class="form-heading">
            <div>
              <h2>Электронная почта</h2>
              <p class="muted">У пациента хранится один актуальный адрес с возможностью изменения или удаления.</p>
            </div>
          </div>
          <form class="toolbar-form compact-toolbar" @submit.prevent="saveEmail">
            <input v-model="emailDraft" type="email" maxlength="64" placeholder="Электронная почта" />
            <button class="secondary-button" :disabled="isSaving || !emailDraft.trim()" type="submit">
              {{ selectedClient?.email ? 'Обновить' : 'Добавить' }}
            </button>
            <button v-if="selectedClient?.email" class="danger-button" :disabled="isSaving" type="button" @click="removeEmail">
              Удалить
            </button>
          </form>
          <div class="form-heading"><h2>Телефоны</h2></div>
          <form class="toolbar-form compact-toolbar" @submit.prevent="addPhone">
            <input v-model="newPhone.phone" placeholder="Телефон" />
            <button class="secondary-button" :disabled="isSaving || !newPhone.phone.trim()" type="submit">
              {{ editingPhoneId ? 'Обновить' : 'Добавить' }}
            </button>
            <button v-if="editingPhoneId" class="ghost-button" type="button" @click="cancelPhoneEdit">Отмена</button>
          </form>
          <div class="list-stack">
            <div v-for="phone in phones" :key="String(phone.phone_id ?? getPhoneValue(phone))" class="list-row">
              <strong>{{ getPhoneValue(phone) }}</strong>
              <div class="row-actions">
                <button class="ghost-button" type="button" @click="startEditPhone(phone)">Изм.</button>
                <button class="danger-button" :disabled="isSaving" type="button" @click="removePhone(phone)">Удалить</button>
              </div>
            </div>
            <p v-if="phones.length === 0" class="muted">Телефонов пока нет.</p>
          </div>
        </div>

        <div v-else-if="activeTab === 'modules'" class="detail-panel components-detail-panel">
          <p v-if="isTabLoading('modules')" class="muted">Загружаем комплектующие...</p>

          <section v-if="!selectedClient?.is_archived" class="component-workbench">
            <button
              class="component-drawer-trigger"
              type="button"
              :aria-expanded="componentFormExpanded"
              aria-controls="client-component-form"
              @click="componentFormExpanded = !componentFormExpanded"
            >
              <span class="component-drawer-icon" aria-hidden="true">
                <PackageOpen :size="20" />
              </span>
              <span class="component-drawer-copy">
                <strong>{{ editingModuleId ? 'Редактировать комплектующую' : 'Добавить комплектующую' }}</strong>
                <span>Создать новую позицию или выбрать готовую со склада и назначить код ТСР</span>
              </span>
              <span class="component-drawer-action">
                {{ componentFormExpanded ? 'Свернуть' : 'Открыть форму' }}
                <span class="component-drawer-chevron" :class="{ expanded: componentFormExpanded }" aria-hidden="true">⌄</span>
              </span>
            </button>

            <form
              id="client-component-form"
              v-show="componentFormExpanded"
              class="component-workbench-body"
              @submit.prevent="submitComponentForm"
            >
              <template v-if="clientTsrGroups.some((group) => group.clientTsrId)">
                <div class="component-target-row">
                  <label class="component-target-field">
                    <span>Код ТСР *</span>
                    <select v-model="moduleForm.client_tsr_id" required @change="handleComponentTargetChange">
                      <option value="">Выберите ТСР пациента</option>
                      <option
                        v-for="group in clientTsrGroups.filter((item) => item.clientTsrId)"
                        :key="`component-target-${group.clientTsrId}`"
                        :value="group.clientTsrId"
                      >
                        {{ getComponentTsrOptionLabel(group) }}
                      </option>
                    </select>
                    <small>При одинаковых кодах ориентируйтесь на дату пробития и стоимость сертификата.</small>
                  </label>

                  <div v-if="selectedComponentTsrGroup" class="component-target-context" aria-live="polite">
                    <span>Выбранный ТСР</span>
                    <strong>{{ selectedComponentTsrGroup.tsr }}</strong>
                    <div>
                      <span>{{ formatShortDate(selectedComponentTsrGroup.checkDate) }}</span>
                      <span>{{ formatMoney(getGroupCertificatePrice(selectedComponentTsrGroup)) }}</span>
                      <span>{{ getGroupComponentUnitCount(selectedComponentTsrGroup) }} компл.</span>
                    </div>
                  </div>
                </div>

                <div v-if="!editingModuleId" class="component-mode-switch" role="tablist" aria-label="Способ добавления комплектующей">
                  <button
                    class="component-mode-button"
                    :class="{ active: componentEntryMode === 'new' }"
                    type="button"
                    role="tab"
                    :aria-selected="componentEntryMode === 'new'"
                    @click="setComponentEntryMode('new')"
                  >
                    <Plus :size="16" aria-hidden="true" />
                    Создать новую
                  </button> 
                  <button
                    class="component-mode-button"
                    :class="{ active: componentEntryMode === 'catalog' }"
                    type="button"
                    role="tab"
                    :aria-selected="componentEntryMode === 'catalog'"
                    @click="setComponentEntryMode('catalog')"
                  >
                    <Search :size="16" aria-hidden="true" />
                    Выбрать из списка
                    <span class="component-mode-count">{{ nameIndexOptions.length }} записей</span>
                  </button>
                  <button
                    class="component-mode-button"
                    :class="{ active: componentEntryMode === 'warehouse' }"
                    type="button"
                    role="tab"
                    :aria-selected="componentEntryMode === 'warehouse'"
                    @click="setComponentEntryMode('warehouse')"
                  >
                    <PackageOpen :size="16" aria-hidden="true" />
                    Выбрать со склада
                    <span class="component-mode-count">{{ workingWarehouseUnitCount + stockWarehouseUnitCount }}</span>
                  </button>
                </div>

                <div v-if="componentEntryMode === 'warehouse' && !editingModuleId" class="component-stock-panel">
                  <div class="component-stock-source-switch" role="tablist" aria-label="Источник комплектующей">
                    <button
                      class="secondary-button"
                      :class="{ active: componentWarehouseSource === 'working' }"
                      type="button"
                      role="tab"
                      :aria-selected="componentWarehouseSource === 'working'"
                      @click="setComponentWarehouseSource('working')"
                    >
                      Рабочий склад · {{ workingWarehouseUnitCount }}
                    </button>
                    <button
                      class="secondary-button"
                      :class="{ active: componentWarehouseSource === 'stock' }"
                      type="button"
                      role="tab"
                      :aria-selected="componentWarehouseSource === 'stock'"
                      @click="setComponentWarehouseSource('stock')"
                    >
                      Склад · {{ stockWarehouseUnitCount }}
                    </button>
                  </div>
                  <label>
                    Комплектующая · {{ componentWarehouseSource === 'stock' ? 'Склад' : 'Рабочий склад' }} *
                    <select v-model="selectedModuleId" required @change="handleWarehouseModuleChange">
                      <option value="">Выберите свободную комплектующую</option>
                      <option
                        v-for="moduleItem in warehouseModules"
                        :key="String(moduleItem.module_id)"
                        :value="moduleItem.module_id"
                      >
                        {{ moduleItem.tsr?.full_tsr_code || 'ТСР не выбран' }} — {{ getModuleName(moduleItem) }} — {{ getModuleWarehouseAttributes(moduleItem) }} — Количество: {{ getModuleUnitCount(moduleItem) }} шт. — {{ moduleItem.supplier || 'поставщик не указан' }}
                      </option>
                    </select>
                  </label>
                  <label v-if="selectedWarehouseModule" class="warehouse-assign-quantity-field">
                    Количество для назначения *
                    <div class="inline-quantity-picker">
                      <input
                        v-model="warehouseAssignQuantity"
                        type="number"
                        min="1"
                        :max="selectedWarehouseAvailableQuantity"
                        step="1"
                      />
                      <button class="ghost-button" type="button" @click="warehouseAssignQuantity = '1'">1</button>
                      <button class="ghost-button" type="button" @click="warehouseAssignQuantity = String(selectedWarehouseAvailableQuantity)">Все</button>
                      <span class="muted">из {{ selectedWarehouseAvailableQuantity }} шт.</span>
                    </div>
                  </label>
                  <p v-if="warehouseModules.length === 0" class="form-hint compact-hint">
                    В выбранном разделе нет свободных комплектующих. Выберите другой раздел или «Создать новую».
                  </p>
                  <p v-else-if="selectedWarehouseTargetMismatch" class="component-inline-note component-inline-error">
                    Код выбранной складской комплектующей не совпадает с выбранным ТСР пациента. Выберите подходящий ТСР или другую позицию.
                  </p>
                  <p v-else class="component-inline-note">
                    Если у позиции уже указан ТСР, он должен совпадать с ТСР пациента. Позиции без ТСР можно назначить на выбранный ТСР пациента.
                  </p>
                  <div class="component-form-actions">
                    <button class="primary-button" :disabled="isSaving || !selectedModuleId || !moduleForm.client_tsr_id || selectedWarehouseTargetMismatch" type="submit">
                      {{ isSaving ? 'Привязываем...' : `Привязать со склада · ${warehouseAssignQuantity || 1} шт.` }}
                    </button>
                  </div>
                </div>

                <template v-else>
                  <div v-if="componentEntryMode === 'catalog' && !editingModuleId" class="component-catalog-hint">
                    <div>
                      <strong>Справочник комплектующих</strong>
                      <span>Выберите существующее название/индекс ниже. Остальные поля заполняются вручную.</span>
                    </div>
                    <button v-if="canManageReferences" class="ghost-button" type="button" @click="isNameIndexManagerOpen = true">Управление справочником</button>
                  </div>
                  <div class="component-form-section">
                    <div class="component-section-heading">
                      <strong>Основные данные</strong>
                      <span>Название, поставщик, количество и цены</span>
                    </div>
                    <div class="form-grid component-primary-grid">
                      <label>
                        Название и индекс *
                        <NameIndexAutocomplete
                          v-model="moduleForm.module_name_index"
                          :options="nameIndexOptions"
                          :required="true"
                          :show-all-on-focus="componentEntryMode === 'catalog'"
                          :placeholder="componentEntryMode === 'catalog' ? 'Выберите из справочника' : 'Введите название или индекс'"
                        />
                      </label>
                      <label>
                        Поставщик *
                        <input v-model="moduleForm.supplier" list="client-component-suppliers" required />
                        <datalist id="client-component-suppliers">
                          <option v-for="supplier in COMPONENT_SUPPLIERS" :key="supplier" :value="supplier" />
                        </datalist>
                      </label>
                      <label class="component-quantity-field">
                        Количество
                        <input v-model="moduleForm.quantity" inputmode="numeric" />
                      </label>
                      <label>
                        Себестоимость за ед.
                        <input v-model="moduleForm.unit_cost" inputmode="decimal" @blur="formatModuleMoneyField('unit_cost')" />
                      </label>
                      <label>
                        Цена за ед.
                        <input v-model="moduleForm.unit_price" inputmode="decimal" @blur="formatModuleMoneyField('unit_price')" />
                      </label>
                    </div>
                  </div>

                  <div class="component-form-section">
                    <div class="component-section-heading">
                      <strong>Характеристики и движение</strong>
                      <span>Параметры изделия и состояние заказа</span>
                    </div>
                    <div class="form-grid component-characteristics-grid">
                      <label>
                        Номер счета и дата заказа
                        <input v-model="moduleForm.order_date_acc_num" />
                      </label>
                      <label>
                        Размер
                        <input v-model="moduleForm.size" />
                      </label>
                      <label>
                        Жесткость
                        <input v-model="moduleForm.stiffness" />
                      </label>
                      <label>
                        Сторона
                        <input v-model="moduleForm.side" />
                      </label>
                      <label>
                        Заказано
                        <input v-model="moduleForm.ordered" type="number" min="0" step="1" />
                      </label>
                      <label>
                        Получено
                        <input v-model="moduleForm.recd" type="number" min="0" step="1" />
                      </label>
                      <label>
                        У протезиста
                        <input v-model="moduleForm.prosthetist_keep" type="number" min="0" step="1" />
                      </label>
                    </div>
                  </div>

                  <div class="component-form-section component-notes-section">
                    <label>
                      Доп. свойства
                      <input v-model="moduleForm.properties" />
                    </label>
                    <label>
                      Заметки
                      <textarea v-model="moduleForm.notes" rows="3" />
                    </label>
                  </div>

                  <div class="component-form-actions">
                    <button class="primary-button" :disabled="isSaving || !moduleForm.client_tsr_id" type="submit">
                      {{ isSaving ? 'Сохраняем...' : editingModuleId ? 'Сохранить изменения' : 'Создать комплектующую' }}
                    </button>
                    <button v-if="editingModuleId" class="ghost-button" type="button" @click="resetModuleForm()">
                      Отмена
                    </button>
                  </div>
                </template>
              </template>

              <div v-else class="component-empty-target">
                <strong>Сначала добавьте пациенту ТСР</strong>
                <span>После добавления кода в разделе «Основное» здесь сразу станет доступно создание комплектующей.</span>
              </div>
            </form>
          </section>

          <p v-else class="form-hint">
            Комплектующие архивного пациента доступны для просмотра. Чтобы изменять их или назначать ТСР, сначала восстановите пациента.
          </p>

          <div class="component-list-heading">
            <div>
              <h2>Комплектующие пациента</h2>
              <p class="muted">Позиции сгруппированы по назначенному ТСР.</p>
            </div>
            <span class="component-total-badge">{{ clientModuleUnitCount }} шт.</span>
          </div>

          <div v-if="clientTsrGroups.length" class="tsr-component-groups component-groups-modern">
            <article
              v-for="group in clientTsrGroups"
              :key="group.key"
              class="tsr-component-group"
              :class="{ 'client-tsr-gradient-card': Boolean(group.clientTsrId) }"
              :style="getClientTsrGroupStyle(group)"
            >
              <header class="tsr-component-header">
                <div>
                  <strong>{{ group.tsr }}</strong>
                  <span>
                    {{ formatShortDate(group.checkDate) }} · {{ formatMoney(getGroupCertificatePrice(group)) }} ·
                    {{ getGroupComponentUnitCount(group) }} компл.
                  </span>
                </div>
                <div class="row-actions">
                  <label
                    v-if="group.clientTsrId && group.components.length && !selectedClient?.is_archived"
                    class="component-prosthetist-toggle component-prosthetist-toggle--group"
                    @click.stop
                  >
                    <input
                      type="checkbox"
                      :checked="isGroupFullyAtProsthetist(group)"
                      :indeterminate="isGroupPartiallyAtProsthetist(group)"
                      :disabled="isSaving"
                      @change="handleGroupProsthetistStateChange(group, $event)"
                    />
                    <span>Все у протезиста</span>
                  </label>
                  <strong title="Суммарная себестоимость комплектующих ТСР">{{ formatMoney(getGroupTotalCost(group)) }}</strong>
                  <button
                    v-if="group.clientTsrId && !selectedClient?.is_archived"
                    class="ghost-button"
                    type="button"
                    @click="openNewComponentFromTsr(group)"
                  >
                    <Plus :size="15" aria-hidden="true" />
                    Добавить
                  </button>
                </div>
              </header>
              <div v-if="group.components.length" class="list-stack">
                <div v-for="moduleItem in group.components" :key="String(moduleItem.module_id)" class="list-row component-list-row">
                  <div class="component-main-copy">
                    <button class="link-button component-name-link" type="button" @click="openComponentFromMain(moduleItem)">
                      {{ getModuleName(moduleItem) }}
                    </button>
                    <span>
                      {{ moduleItem.supplier || moduleItem.properties || 'Комплектующая пациента' }} ·
                      {{ moduleItem.quantity ?? 1 }} шт. ·
                      себестоимость {{ formatMoney(moduleItem.cost) }} ·
                      цена {{ formatMoney(moduleItem.price) }}
                    </span>
                    <div class="component-detail-status-row">
                      <span class="component-characteristics-line">
                        Размер: {{ moduleItem.size || '—' }} ·
                        Жесткость: {{ moduleItem.stiffness || '—' }} ·
                        Сторона: {{ moduleItem.side || '—' }}
                      </span>
                      <span class="component-status-summary">
                        <span :class="{ 'component-count-status--ordered': Number(moduleItem.ordered || 0) > 0 }">
                          Заказано <strong>{{ moduleItem.ordered || 0 }}</strong>
                        </span>
                        <span :class="{ 'component-count-status--shortfall': hasModuleDeliveryShortfall(moduleItem) }">
                          Получено <strong>{{ moduleItem.recd || 0 }}</strong>
                        </span>
                        <span :class="{ 'component-count-status--prosthetist': isModuleAtProsthetist(moduleItem) }">
                          У протезиста <strong>{{ moduleItem.prosthetist_keep || 0 }}</strong>
                        </span>
                      </span>
                    </div>
                  </div>
                  <div v-if="!selectedClient?.is_archived" class="row-actions component-actions">
                    <div class="component-action-buttons">
                      <label class="component-prosthetist-toggle" @click.stop>
                        <input
                          type="checkbox"
                          :checked="isModuleAtProsthetist(moduleItem)"
                          :disabled="isSaving || !group.clientTsrId"
                          @change="handleModuleProsthetistStateChange(group, moduleItem, $event)"
                        />
                        <span>У протезиста</span>
                      </label>
                      <button
                        class="ghost-button"
                        type="button"
                        title="Изменить комплектующую"
                        @click="fillModuleForm(moduleItem)"
                      >
                        Изменить
                      </button>
                      <button class="ghost-button" :disabled="isSaving" type="button" @click="unassignModule(moduleItem)">
                        На склад
                      </button>
                      <button class="danger-button" :disabled="isSaving" type="button" @click="removeClientModule(moduleItem)">
                        Удалить
                      </button>
                    </div>
                    <label v-if="getModuleUnitCount(moduleItem) > 1" class="component-row-quantity-picker" @click.stop>
                      <span class="component-row-quantity-label">Количество для «На склад» / «Удалить»</span>
                      <input
                        :value="getModuleOperationQuantity(moduleItem)"
                        type="number"
                        min="1"
                        :max="getModuleUnitCount(moduleItem)"
                        step="1"
                        @input="handleModuleOperationQuantityInput(moduleItem, $event)"
                      />
                      <button class="ghost-button compact-quantity-button" type="button" @click.stop="setModuleOperationQuantity(moduleItem, 1)">1</button>
                      <button class="ghost-button compact-quantity-button" type="button" @click.stop="setModuleOperationQuantity(moduleItem, getModuleUnitCount(moduleItem))">Все</button>
                      <span>из {{ getModuleUnitCount(moduleItem) }}</span>
                    </label>
                  </div>
                </div>
              </div>
              <div v-else class="component-group-empty">
                <span>Комплектующих пока нет.</span>
                <button
                  v-if="group.clientTsrId && !selectedClient?.is_archived"
                  class="link-button"
                  type="button"
                  @click="openNewComponentFromTsr(group)"
                >
                  Создать первую
                </button>
              </div>
            </article>
          </div>
          <p v-else class="muted">К пациенту пока не прикреплены ТСР и комплектующие.</p>
        </div>

        <div v-else-if="activeTab === 'documents'" class="detail-panel">
          <p v-if="isTabLoading('documents')" class="muted">Загружаем документы...</p>
          <div class="tabs client-documents-tabs" role="tablist" aria-label="Автозаполнение документов">
            <button :class="{ active: documentGeneratorTab === 'contracts' }" type="button" @click="documentGeneratorTab = 'contracts'">Договоры</button>
            <button :class="{ active: documentGeneratorTab === 'mtz' }" type="button" @click="documentGeneratorTab = 'mtz'">МТЗ</button>
          </div>
          <form v-if="documentGeneratorTab === 'contracts'" class="toolbar-form contract-toolbar" @submit.prevent="generateContract">
            <label class="contract-template-field">
              Шаблон
              <select v-model="contractType">
                <option v-for="option in contractTemplateOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label class="contract-prefix-field">
              Буквы номера
              <input v-model="contractNumberPrefix" class="contract-prefix-input" placeholder="СД" maxlength="8" />
            </label>
            <label class="contract-number-field">
              Номер
              <input v-model="contractNumberSuffix" class="contract-number-input" inputmode="numeric" readonly aria-readonly="true" />
            </label>
            <label class="contract-date-field">
              Дата документа
              <DateInput v-model="contractDate" aria-label="Дата документа" />
            </label>
            <label v-if="showExtendedContractDates" class="contract-date-field">
              Дата плана / ТЗ
              <DateInput v-model="contractPlanDate" :max-year="new Date().getFullYear() + 30" aria-label="Дата плана или технического задания" />
            </label>
            <label v-if="showExtendedContractDates" class="contract-date-field">
              Дата приложений / акта
              <DateInput v-model="contractAppendixDate" :max-year="new Date().getFullYear() + 30" aria-label="Дата приложений или акта" />
            </label>
            <button class="secondary-button contract-submit-button" :disabled="isSaving" type="submit">
              Сформировать
            </button>
          </form>
          <div v-if="documentGeneratorTab === 'contracts' && showExtendedContractDates" class="contract-module-selector">
            <div class="contract-selector-heading">
              <div>
                <p class="eyebrow">ТСР и комплектующие для договора</p>
                <span class="muted">Выбрано ТСР: {{ selectedContractClientTsrIds.length }} из {{ contractTsrGroups.length }}</span>
              </div>
              <div v-if="contractTsrGroups.length" class="row-actions">
                <button class="ghost-button" type="button" @click="selectAllContractTsrGroups">Выбрать все</button>
                <button class="ghost-button" type="button" @click="clearContractTsrSelection">Снять выбор</button>
              </div>
            </div>
            <article v-for="group in contractTsrGroups" :key="group.key" class="contract-tsr-group">
              <label class="checkbox-label contract-tsr-heading">
                <input
                  type="checkbox"
                  :checked="isContractGroupSelected(group)"
                  :indeterminate="isContractGroupPartiallySelected(group)"
                  @change="toggleContractGroup(group, $event)"
                />
                <span>
                  <strong>{{ group.tsr }}</strong>
                  · {{ getGroupComponentUnitCount(group) }} комплектующих
                  · сертификат: {{ formatMoney(getGroupCertificatePrice(group)) }}
                </span>
              </label>
              <div class="contract-component-list">
                <label
                  v-for="component in group.components"
                  :key="String(component.module_id)"
                  class="checkbox-label"
                >
                  <input
                    type="checkbox"
                    :checked="selectedContractModuleIds.includes(String(component.module_id))"
                    @change="toggleContractComponent(group, String(component.module_id), $event)"
                  />
                  <span>
                    <strong>{{ getModuleName(component) }}</strong>
                    · {{ component.quantity ?? 1 }} шт.
                  </span>
                </label>
              </div>
            </article>
            <p v-if="contractTsrGroups.length === 0" class="muted">
              Сначала прикрепите ТСР к пациенту в разделе «Основное».
            </p>
          </div>
          <section v-if="documentGeneratorTab === 'mtz'" class="client-mtz-panel">
            <div class="client-mtz-layout">
              <form class="toolbar-form client-mtz-form" @submit.prevent="generateMtzFromClientCard">
                <div class="form-heading">
                  <div>
                    <p class="eyebrow">Автозаполнение МТЗ</p>
                    <h2>Медико-техническое заключение</h2>
                    <p class="muted">ФИО, дата рождения и телефон подтягиваются из карточки пациента. Остальные поля ниже заполняются только для этого документа и в карточку пациента не сохраняются.</p>
                  </div>
                </div>
                <div class="client-mtz-form-grid">
                  <label class="wide-field">
                    Шаблон / ТСР
                    <select v-model="mtzType">
                      <option v-for="option in mtzTemplateOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                  </label>
                  <label>
                    Номер МТЗ
                    <input v-model="mtzNumber" placeholder="Например: 124/26" />
                  </label>
                  <label class="mtz-date-field">
                    Дата МТЗ
                    <DateInput v-model="mtzDate" aria-label="Дата МТЗ" />
                  </label>
                  <label class="wide-field">
                    Группа и причина инвалидности
                    <input v-model="mtzDisabilityGroupReason" placeholder="Заполняется вручную" />
                  </label>
                  <label class="wide-field">
                    Справка
                    <input v-model="mtzCertificateReference" placeholder="Заполняется вручную" />
                  </label>
                  <label class="wide-field">
                    Диагноз
                    <textarea v-model="mtzDiagnosis" rows="3" placeholder="Заполняется вручную" />
                  </label>
                  <label>
                    Уровень ампутации
                    <input v-model="mtzAmputationLevel" placeholder="Заполняется вручную" />
                  </label>
                  <label>
                    Вес пациента (кг)
                    <input v-model="mtzWeightKg" inputmode="decimal" placeholder="Например: 82" />
                  </label>
                </div>
                <button class="primary-button" :disabled="isSaving || mtzTemplateOptions.length === 0" type="submit">
                  {{ isSaving ? 'Формируем…' : 'Сформировать МТЗ' }}
                </button>
                <p v-if="mtzTemplateOptions.length === 0" class="form-hint">Шаблон МТЗ не загрузился. Обновите страницу или проверьте API документов.</p>
              </form>

              <aside class="surface-panel client-mtz-preview">
                <div>
                  <p class="eyebrow">Автозаполнение</p>
                  <h3>Из карточки пациента</h3>
                </div>
                <dl>
                  <div><dt>ФИО</dt><dd>{{ mtzAutofillData.fullName }}</dd></div>
                  <div><dt>Дата рождения</dt><dd>{{ mtzAutofillData.birthDate }}</dd></div>
                  <div><dt>Телефон</dt><dd>{{ mtzAutofillData.phone }}</dd></div>
                  <div><dt>Текущий шаблон</dt><dd>{{ selectedMtzTemplate?.label || '—' }}</dd></div>
                </dl>
              </aside>
            </div>
          </section>

          <form class="upload-form" @submit.prevent="uploadDocument">
            <label>
              Файл
              <input type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" @change="handleFileChange" />
            </label>
            <p class="form-hint">
              PDF, PNG, JPG/JPEG или DOCX до 25 МБ.
              <template v-if="selectedFile"> Выбран: {{ selectedFile.name }} · {{ formatFileSize(selectedFile.size) }}</template>
            </p>
            <button class="secondary-button" :disabled="isSaving || !selectedFile" type="submit">
              Загрузить
            </button>
          </form>
          <div class="list-stack">
            <div v-for="document in documents" :key="String(document.document_id)" class="list-row">
              <div>
                <strong class="document-title">
                  <component :is="getDocumentIcon(document)" :size="17" aria-hidden="true" />
                  {{ getDocumentName(document) }}
                </strong>
                <span>{{ document.content_type || 'тип не указан' }} · {{ formatFileSize(document.size) }} · {{ formatDate(document.created_at) }}</span>
              </div>
              <div class="row-actions">
                <button v-if="document.document_id" class="ghost-button" type="button" @click="downloadDocument(document)">
                  Скачать
                </button>
                <button class="danger-button" :disabled="isSaving" type="button" @click="removeDocument(document)">
                  Удалить
                </button>
              </div>
            </div>
            <p v-if="documents.length === 0" class="muted">Документов пока нет.</p>
          </div>
        </div>

        <div v-else class="detail-panel">
          <p v-if="isTabLoading('history')" class="muted">Загружаем историю...</p>
          <div v-else-if="auditItems.length" class="audit-timeline">
            <article v-for="item in auditItems" :key="String(item.log_id ?? item.timestamp)" class="audit-item">
              <div>
                <strong>{{ formatAuditAction(item) }}</strong>
                <span>{{ formatAuditActor(item) }} · {{ formatAuditTime(item.timestamp ?? undefined) }}</span>
              </div>
              <p>{{ summarizeAuditDetails(item) }}</p>
            </article>
          </div>
          <p v-else class="muted">История пока пустая.</p>
        </div>
            </div>
          </div>

          <div v-if="activeTab === 'main'" class="client-save-bar">
            <span>
              {{ hasUnsavedClientChanges ? 'Есть несохранённые изменения' : 'Все изменения сохранены' }}
            </span>
            <button
              class="primary-button"
              type="submit"
              form="client-main-form"
              :disabled="isSaving || !hasUnsavedClientChanges"
            >
              <Save :size="16" aria-hidden="true" />
              {{ isSaving ? 'Сохраняем...' : isEditing ? 'Сохранить изменения' : 'Создать пациента' }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>

    <NameIndexManagerModal
      :open="isNameIndexManagerOpen"
      :items="nameIndexReferences"
      :can-manage="canManageReferences"
      @close="isNameIndexManagerOpen = false"
      @refresh="reloadNameIndexReferences"
    />

    <Teleport to="body">
      <div
        v-if="isReferenceManagerOpen"
        class="modal-backdrop reference-manager-backdrop"
        @click.self="closeReferenceManager"
        @keydown.esc.window="closeReferenceManager"
      >
        <section v-focus-trap class="modal-panel reference-manager-modal" role="dialog" aria-modal="true" aria-label="Справочник ТСР" @click.stop>
          <div class="modal-header">
            <div>
              <p class="eyebrow">Справочник</p>
              <h2>Коды ТСР</h2>
            </div>
            <button class="ghost-button" type="button" :disabled="isReferenceSaving" @click="closeReferenceManager">Закрыть</button>
          </div>

          <p v-if="referenceError" class="form-error">{{ referenceError }}</p>
          <p v-if="referenceSuccess" class="form-success">{{ referenceSuccess }}</p>

          <form v-if="canManageReferences" class="reference-editor" @submit.prevent="saveManagedReference">
            <label>
              Код ТСР
              <input v-model="referenceDraft" placeholder="Например: 8-07-01" required />
            </label>
            <div class="row-actions reference-editor-actions">
              <button class="primary-button" type="submit" :disabled="isReferenceSaving || !referenceDraft.trim()">
                {{ isReferenceSaving ? 'Сохраняем...' : isEditingReference ? 'Сохранить' : 'Добавить' }}
              </button>
              <button v-if="isEditingReference" class="ghost-button" type="button" :disabled="isReferenceSaving" @click="resetReferenceManagerForm">
                Отмена
              </button>
            </div>
          </form>

          <div class="reference-search-row">
            <input v-model="referenceSearch" placeholder="Быстрый поиск по справочнику" />
            <span class="muted">{{ filteredReferenceItems.length }} из {{ tsrReferences.length }}</span>
          </div>

          <div class="reference-list" role="list">
            <article v-for="(item, index) in filteredReferenceItems" :key="String(getReferenceId(item) || getReferenceLabel(item))" class="reference-list-item" role="listitem">
              <div>
                <strong>{{ getReferenceLabel(item) }}</strong>
                <span>№ {{ index }}</span>
              </div>
              <div class="row-actions">
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="isReferenceSaving || !isClientPersisted"
                  @click="attachManagedReference(item)"
                >
                  {{ attachedTsrCounts.has(String(getReferenceId(item) || '')) ? 'Добавить ещё' : 'Прикрепить пациенту' }}
                </button>
                <button v-if="canManageReferences" class="ghost-button" type="button" :disabled="isReferenceSaving" @click="startEditReference(item)">Изм.</button>
                <button v-if="canManageReferences" class="danger-button" type="button" :disabled="isReferenceSaving" @click="removeManagedReference(item)">Удалить</button>
              </div>
            </article>
            <p v-if="filteredReferenceItems.length === 0" class="empty-state">Записей не найдено.</p>
          </div>

          <p class="form-hint">
            Кнопка «Прикрепить пациенту» добавляет ТСР в раздел «Основное» и создаёт соответствующую группу в «Комплектующих». Редактирование самого справочника доступно администратору.
          </p>
        </section>
      </div>
    </Teleport>
  </section>
</template>
