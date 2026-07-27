<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Archive,
  Eye,
  File,
  FileImage,
  Files,
  FileText,
  History,
  IdCard,
  PackageOpen,
  Phone,
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
import ActionMenu, { type ActionMenuItem } from '@/shared/ui/ActionMenu.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'
import StatusPill from '@/shared/ui/StatusPill.vue'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import { formatMoney, formatMoneyInput, parseMoney } from '@/shared/lib/money'
import { fetchAgents } from '@/shared/api/agents'
import { fetchEntityAudit } from '@/shared/api/audit'
import {
  archiveClient,
  assignClientComponentsTsr,
  createClient,
  createClientPassport,
  createClientPhone,
  createClientSnils,
  deleteClient,
  deleteClientPassport,
  deleteClientPhone,
  deleteClientSnils,
  fetchClient,
  fetchClientPhones,
  fetchClients,
  restoreClient,
  updateClient,
  updateClientPassport,
  updateClientPhone,
  updateClientSnils,
} from '@/shared/api/clients'
import {
  deleteDocument,
  downloadDocumentBlob,
  fetchClientDocuments,
  fetchContractTemplates,
  generateClientContract,
  uploadClientDocument,
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

type ContractTemplateOption = { value: string; label: string }

const contractTemplateOptions = ref<ContractTemplateOption[]>([
  { value: 'llc_contract', label: 'ООО Смарт Движение · Договор' },
  { value: 'dmk_contract', label: 'ИП ДМК · Договор' },
  { value: 'dmk_instrument', label: 'ИП ДМК · Акт' },
])

const prosthesisOptions = [
  { value: 'Верхних конечностей', label: 'Верхних конечностей' },
  { value: 'Нижних конечностей', label: 'Нижних конечностей' },
  { value: 'Верхних и нижних конечностей', label: 'Верхних и нижних конечностей' },
] as const
const prosthesisOptionValues = new Set<string>(prosthesisOptions.map((option) => option.value))

type ClientForm = {
  last_name: string
  first_name: string
  middle_name: string
  status: string
  current_stage: string
  agent_id: string
  deadline: string
  check_date: string
  prosthesis_type: string
  certificate_price: string
  taxation_system: 'УСН' | 'ОСНО'
  place_of_residence: string
  prosthetist: string
  notes: string
}

type ClientTab = 'main' | 'identity' | 'phones' | 'modules' | 'documents' | 'history'
type DetailTab = Exclude<ClientTab, 'main'>
type ClientListMode = 'active' | 'archive'
type CountInput = string | number

type ClientModuleForm = {
  tsr_id: string
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
  pending: CountInput
  order_date_acc_num: string
  properties: string
  prosthetist_keep: CountInput
  notes: string
}

type ClientTsrGroup = {
  key: string
  tsrId: string
  tsr: string
  components: ModuleItem[]
}

const emptyForm: ClientForm = {
  last_name: '',
  first_name: '',
  middle_name: '',
  status: '',
  current_stage: '',
  agent_id: '',
  deadline: '',
  check_date: '',
  prosthesis_type: '',
  certificate_price: '',
  taxation_system: 'УСН',
  place_of_residence: '',
  prosthetist: '',
  notes: '',
}

const authStore = useAuthStore()
const route = useRoute()

const emptyModuleForm: ClientModuleForm = {
  tsr_id: '',
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
  pending: '0',
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
const warehouseModules = ref<ModuleItem[]>([])
const auditItems = ref<AuditLogItem[]>([])
const query = ref('')
const statusFilter = ref('')
const stageFilter = ref('')
const agentFilter = ref('')
const pageLimit = ref(100)
const currentPage = ref(1)
const hasMoreClients = ref(false)
const activeClientListMode = ref<ClientListMode>('active')
const selectedClient = ref<Client | null>(null)
const isClientCardOpen = ref(false)
const activeTab = ref<ClientTab>('main')
const form = reactive<ClientForm>({ ...emptyForm })
const moduleForm = reactive<ClientModuleForm>({ ...emptyModuleForm })
const newPhone = reactive({ phone: '', comment: '' })
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
  expiry_date: '',
  registration_address: '',
})
const snilsForm = reactive({
  number: '',
  ipra_number: '',
  ipra_date: '',
})
const selectedModuleId = ref('')
const selectedContractModuleIds = ref<string[]>([])
const editingModuleId = ref<string | null>(null)
const contractType = ref('llc_contract')
const defaultContractSuffix = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: '2-digit',
}).format(new Date()).replace(/\D/g, '')
const contractNumberPrefix = ref('СД')
const contractNumberSuffix = ref(defaultContractSuffix)
const contractDate = ref(new Date().toISOString().slice(0, 10))
const contractPlanDate = ref(new Date().toISOString().slice(0, 10))
const contractAppendixDate = ref(new Date().toISOString().slice(0, 10))
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
const error = ref('')
const successMessage = ref('')
const lastSavedClientState = ref('')
const isReferenceManagerOpen = ref(false)
const referenceSearch = ref('')
const referenceDraft = ref('')
const referenceEditingId = ref<string | number | null>(null)
const referenceError = ref('')
const referenceSuccess = ref('')
const isReferenceSaving = ref(false)
const groupTsrDrafts = reactive<Record<string, string>>({})
let clientFilterTimer: ReturnType<typeof setTimeout> | undefined

const isEditing = computed(() => Boolean(selectedClient.value?.client_id))
const isClientPersisted = computed(() => Boolean(selectedClient.value && getClientId(selectedClient.value)))
const modalMessageId = computed(() => (error.value ? 'client-modal-error' : successMessage.value ? 'client-modal-success' : undefined))
const activeClientFilterCount = computed(() => [
  query.value.trim(),
  statusFilter.value,
  stageFilter.value,
  agentFilter.value,
].filter(Boolean).length)
const hasUnsavedClientChanges = computed(() => (
  isClientCardOpen.value
  && activeTab.value === 'main'
  && JSON.stringify(form) !== lastSavedClientState.value
))
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Клиенты')
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
const tsrOptions = computed(() => tsrReferences.value.map((item) => ({
  value: String(getReferenceId(item)),
  label: getReferenceLabel(item),
})))
const nameIndexOptions = computed(() => nameIndexReferences.value.map(normalizeReferenceOption))
const passportItems = computed(() => selectedClient.value?.passports ?? [])
const snilsItems = computed(() => selectedClient.value?.snils ?? [])
const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => hasMoreClients.value)
const currentSkip = computed(() => (currentPage.value - 1) * pageLimit.value)
const clientTsrGroups = computed<ClientTsrGroup[]>(() => {
  const source = clientModules.value.length ? clientModules.value : (selectedClient.value?.modules ?? [])
  const groups = new Map<string, ClientTsrGroup>()

  for (const component of source) {
    const tsrId = String(component.tsr_id ?? component.tsr?.id ?? '')
    const tsr = component.tsr?.full_tsr_code || 'ТСР не выбран'
    const key = tsrId || '__unassigned__'
    const group = groups.get(key)

    if (group) {
      group.components.push(component)
    } else {
      groups.set(key, { key, tsrId, tsr, components: [component] })
    }
  }

  return [...groups.values()].sort((left, right) => left.tsr.localeCompare(right.tsr, 'ru'))
})

const statusFallbackLabels: Record<string, string> = {
  new: 'Новый',
  work: 'В работе',
  inwork: 'В работе',
  active: 'Активный',
  done: 'Завершен',
  completed: 'Завершен',
  fail: 'Отказ',
  failed: 'Отказ',
  postponed: 'Отложен',
}

const stageFallbackLabels: Record<string, string> = {
  new: 'Новый',
  documents: 'Документы',
  measurement: 'Замер',
  production: 'Производство',
  fitting: 'Примерка',
  contract: 'Договор',
  contractsign: 'Подписание договора',
  delivery: 'Выдача',
  payment: 'Оплата',
  done: 'Завершено',
  completed: 'Завершено',
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
    record.code ??
    record.id ??
    record.name ??
    record.title ??
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
      label: isArchived ? 'Восстановить' : 'Переместить в архив',
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

function getClientTsrLabel(client: Client) {
  const values = (client.modules ?? [])
    .map((moduleItem) => moduleItem.tsr?.full_tsr_code)
    .filter((value): value is string => Boolean(value))
  return values.length ? [...new Set(values)].join('; ') : '-'
}

function getClientPrimaryPhone(client: Client) {
  return String(client.phones?.[0]?.number ?? '-')
}

function getClientDate(client: Client) {
  return formatShortDate(String(client.check_date ?? client.created_at ?? ''))
}

function getClientDeadline(client: Client) {
  return formatShortDate(String(client.deadline ?? ''))
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

function getGroupTotalPrice(group: ClientTsrGroup) {
  return group.components.reduce((sum, component) => sum + parseMoney(component.price), 0)
}

function getContractGroupIds(group: ClientTsrGroup) {
  return group.components
    .map((component) => String(component.module_id ?? ''))
    .filter(Boolean)
}

function isContractGroupSelected(group: ClientTsrGroup) {
  const ids = getContractGroupIds(group)
  return ids.length > 0 && ids.every((id) => selectedContractModuleIds.value.includes(id))
}

function isContractGroupPartiallySelected(group: ClientTsrGroup) {
  const ids = getContractGroupIds(group)
  const selectedCount = ids.filter((id) => selectedContractModuleIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < ids.length
}

function toggleContractGroup(group: ClientTsrGroup, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const groupIds = getContractGroupIds(group)
  const selected = new Set(selectedContractModuleIds.value)

  for (const id of groupIds) {
    if (checked) {
      selected.add(id)
    } else {
      selected.delete(id)
    }
  }

  selectedContractModuleIds.value = [...selected]
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

function getDateModel(value?: string | null) {
  return value ? String(value).slice(0, 10) : ''
}

function buildDeadline(value: string) {
  return value ? `${value}T00:00:00Z` : null
}

function parseMoneyInput(value: string) {
  if (!value.trim()) {
    return null
  }

  const parsed = parseMoney(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatClientMoneyField(field: 'certificate_price') {
  form[field] = formatMoneyInput(form[field])
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

function resetModuleForm() {
  Object.assign(moduleForm, emptyModuleForm)
  editingModuleId.value = null
}

function fillModuleForm(moduleItem: ModuleItem) {
  const quantity = Number(moduleItem.quantity ?? 1) || 1
  const cost = Number(moduleItem.cost ?? 0)
  const price = Number(moduleItem.price ?? 0)

  editingModuleId.value = moduleItem.module_id ? String(moduleItem.module_id) : null
  moduleForm.tsr_id = String(moduleItem.tsr_id ?? moduleItem.tsr?.id ?? '')
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
  moduleForm.pending = String(moduleItem.pending ?? 0)
  moduleForm.prosthetist_keep = String(moduleItem.prosthetist_keep ?? 0)
  moduleForm.order_date_acc_num = moduleItem.order_date_acc_num ?? '-'
  moduleForm.properties = moduleItem.properties ?? '-'
  moduleForm.notes = moduleItem.notes ?? ''
  resetMessages()
}

function buildModulePayload(clientId: string): ModuleCreatePayload {
  const quantity = parsePositiveInteger(moduleForm.quantity)
  const unitCost = parseMoneyInput(moduleForm.unit_cost) ?? 0
  const unitPrice = parseMoneyInput(moduleForm.unit_price) ?? 0

  return {
    client_id: clientId,
    tsr_id: moduleForm.tsr_id,
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
    pending: parseNonNegativeInteger(moduleForm.pending),
    prosthetist_keep: parseNonNegativeInteger(moduleForm.prosthetist_keep),
    order_date_acc_num: moduleForm.order_date_acc_num.trim() || '-',
    properties: moduleForm.properties.trim() || '-',
    notes: optionalString(moduleForm.notes),
  }
}

function validateModuleForm() {
  if (!moduleForm.tsr_id) {
    error.value = 'Для комплектующей нужно выбрать ТСР.'
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
  warehouseModules.value = []
  auditItems.value = []
  Object.keys(groupTsrDrafts).forEach((key) => delete groupTsrDrafts[key])
}

function rememberClientFormState() {
  lastSavedClientState.value = JSON.stringify(form)
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
    expiry_date: '',
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
  resetModuleForm()
  editingPhoneId.value = null
  editingPassportId.value = null
  editingSnilsId.value = null
  isReferenceManagerOpen.value = false
  resetReferenceManagerForm()
  resetMessages()
  rememberClientFormState()
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
      message: 'Закрыть карточку без сохранения внесённых изменений?',
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

function openClientTab(tab: ClientTab) {
  if (tab !== 'main' && !isClientPersisted.value) {
    error.value = 'Сначала сохрани основную карточку клиента.'
    activeTab.value = 'main'
    return
  }

  activeTab.value = tab

  if (tab !== 'main') {
    void loadClientTabData(tab)
  }
}

function isTabLoading(tab: DetailTab) {
  return detailLoadingTab.value === tab
}

function fillForm(client: Client) {
  const passports = Array.isArray(client.passports) ? client.passports : []
  const firstPassport = passports[0]
  const seriesNumberParts = String(firstPassport?.series_number ?? '').split(/\s+/)

  form.last_name = String(client.last_name ?? '')
  form.first_name = String(client.first_name ?? '')
  form.middle_name = String(client.middle_name ?? '')
  form.status = getReferenceValue(client.status_code)
  form.current_stage = getReferenceValue(client.current_stage)
  form.agent_id = String(client.agent_id ?? '')
  form.deadline = getDateModel(client.deadline)
  form.check_date = getDateModel(client.check_date)
  const prosthesisType = String(client.prosthesis_type ?? '')
  form.prosthesis_type = prosthesisOptionValues.has(prosthesisType) ? prosthesisType : ''
  form.certificate_price = client.certificate_price == null ? '' : formatMoneyInput(client.certificate_price)
  form.taxation_system = client.taxation_system === 'ОСНО' ? 'ОСНО' : 'УСН'
  form.place_of_residence = String(client.place_of_residence ?? '')
  form.prosthetist = String(client.prosthetist ?? '')
  form.notes = String(client.notes ?? '')
  snilsForm.ipra_number = String(client.ipra_code ?? '')

  passportForm.series = seriesNumberParts[0] ?? ''
  passportForm.number = seriesNumberParts.slice(1).join(' ')
  passportForm.birth_date = String(firstPassport?.birth_date ?? '').slice(0, 10)
  passportForm.birth_place = String(firstPassport?.birth_place ?? '')
  passportForm.issued_by = String(firstPassport?.issued_by ?? '')
  passportForm.issue_date = String(firstPassport?.issue_date ?? '').slice(0, 10)
  passportForm.department_code = String(firstPassport?.department_code ?? '')
  passportForm.expiry_date = String(firstPassport?.expiry_date ?? '').slice(0, 10)
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
    agent_id: form.agent_id,
    deadline: buildDeadline(form.deadline),
    check_date: form.check_date || null,
    prosthesis_type: optionalString(form.prosthesis_type),
    certificate_price: optionalString(form.certificate_price),
    taxation_system: form.taxation_system,
    place_of_residence: optionalString(form.place_of_residence),
    prosthetist: optionalString(form.prosthetist),
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
    agent_id: form.agent_id,
    deadline: buildDeadline(form.deadline),
    check_date: form.check_date || null,
    prosthesis_type: optionalString(form.prosthesis_type),
    certificate_price: optionalString(form.certificate_price),
    taxation_system: form.taxation_system,
    place_of_residence: optionalString(form.place_of_residence),
    prosthetist: optionalString(form.prosthetist),
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
    error.value = 'Заполни минимум фамилию и имя клиента.'
    return false
  }

  if (!form.status.trim()) {
    error.value = 'Выбери статус клиента.'
    return false
  }

  if (!form.current_stage.trim()) {
    error.value = 'Выбери этап клиента.'
    return false
  }

  if (!form.agent_id) {
    error.value = 'Выбери агента. По backend-схеме agent_id обязателен для клиента.'
    return false
  }

  return true
}

async function loadClients() {
  isLoading.value = true
  error.value = ''

  try {
    const fetchedClients = await fetchClients({
      skip: currentSkip.value,
      limit: pageLimit.value + 1,
      q: query.value.trim() || undefined,
      status: statusFilter.value.trim() || undefined,
      current_stage: stageFilter.value.trim() || undefined,
      agent_id: agentFilter.value.trim() || undefined,
      archived: activeClientListMode.value === 'archive',
    })

    hasMoreClients.value = fetchedClients.length > pageLimit.value
    clients.value = fetchedClients.slice(0, pageLimit.value)
  } catch (caughtError) {
    hasMoreClients.value = false
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

function applyClientFilters() {
  currentPage.value = 1
  void loadClients()
}

function resetClientFilters() {
  query.value = ''
  statusFilter.value = ''
  stageFilter.value = ''
  agentFilter.value = ''
  applyClientFilters()
}

function switchClientListMode(mode: ClientListMode) {
  if (activeClientListMode.value === mode) {
    return
  }

  activeClientListMode.value = mode
  currentPage.value = 1
  selectedClient.value = null
  isClientCardOpen.value = false
  resetMessages()
  void loadClients()
}

async function goToPreviousClientsPage() {
  if (!hasPreviousPage.value) {
    return
  }

  currentPage.value -= 1
  await loadClients()
}

async function goToNextClientsPage() {
  if (!hasNextPage.value) {
    return
  }

  currentPage.value += 1
  await loadClients()
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
      const [clientModuleResponse, warehouseModuleResponse] = await Promise.all([
        fetchModules({ limit: 1000, client_id: clientId, archived }),
        archived
          ? Promise.resolve([])
          : fetchModules({ limit: 1000, unassigned: true, archived: false }),
      ])
      clientModules.value = clientModuleResponse
      warehouseModules.value = warehouseModuleResponse
    } else if (tab === 'documents') {
      const [documentResponse, moduleResponse] = await Promise.all([
        fetchClientDocuments(clientId),
        fetchModules({
          limit: 1000,
          client_id: clientId,
          archived: Boolean(selectedClient.value?.is_archived),
        }),
      ])
      documents.value = documentResponse
      clientModules.value = moduleResponse
      const available = new Set(moduleResponse.map((item) => String(item.module_id)))
      selectedContractModuleIds.value = selectedContractModuleIds.value.filter((id) => available.has(id))
    } else if (tab === 'history') {
      auditItems.value = await fetchEntityAudit('client', clientId)
    }

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

  if (syncForm) {
    fillForm(freshClient)
  }
}

async function selectClient(client: Client) {
  resetMessages()
  resetDetailState()
  activeTab.value = 'main'
  selectedClient.value = client
  isClientCardOpen.value = true
  fillForm(client)

  const clientId = getClientId(client)

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
    error.value = `Не удалось открыть карточку клиента: ${getApiErrorMessage(caughtError)}`
  }
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
      const updatedClient = await updateClient(clientId, buildUpdatePayload())
      selectedClient.value = updatedClient
      fillForm(updatedClient)
      await refreshSelectedClient(clientId)
      await reloadActiveDetailTab()
      successMessage.value = 'Клиент обновлен'
    } else {
      const createdClient = await createClient(buildCreatePayload())
      const clientId = getClientId(createdClient)
      selectedClient.value = createdClient
      fillForm(createdClient)
      await refreshSelectedClient(clientId)
      await reloadActiveDetailTab()
      successMessage.value = 'Клиент создан'
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
    message: `Удалить клиента «${getClientName(client)}»? Это действие нельзя отменить.`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteClient(clientId)
    successMessage.value = 'Клиент удален'

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
  const action = archive ? 'переместить в архив' : 'восстановить'
  const componentNote = archive
    ? ' Все привязанные комплектующие также будут перемещены в архив.'
    : ' Все привязанные комплектующие также будут восстановлены.'

  if (!clientId) {
    return
  }

  if (!(await confirmAction({
    header: archive ? 'Перемещение в архив' : 'Восстановление клиента',
    message: `${action[0].toUpperCase()}${action.slice(1)} клиента «${getClientName(client)}»?${componentNote}`,
    acceptLabel: archive ? 'В архив' : 'Восстановить',
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
      ? 'Клиент и его комплектующие перемещены в архив'
      : 'Клиент и его комплектующие восстановлены'
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
}

function cancelPhoneEdit() {
  editingPhoneId.value = null
  newPhone.phone = ''
  newPhone.comment = ''
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


function startEditPassport(passport: ClientPassport) {
  if (!passport.passport_id) {
    return
  }

  const seriesNumberParts = String(passport.series_number ?? '').split(/\s+/)
  editingPassportId.value = passport.passport_id
  passportForm.series = seriesNumberParts[0] ?? ''
  passportForm.number = seriesNumberParts.slice(1).join(' ')
  passportForm.birth_date = String(passport.birth_date ?? '').slice(0, 10)
  passportForm.birth_place = passport.birth_place ?? ''
  passportForm.issued_by = passport.issued_by ?? ''
  passportForm.issue_date = String(passport.issue_date ?? '').slice(0, 10)
  passportForm.department_code = passport.department_code ?? ''
  passportForm.expiry_date = String(passport.expiry_date ?? '').slice(0, 10)
  passportForm.registration_address = passport.registration_address ?? ''
  resetMessages()
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
    expiry_date: '',
    registration_address: '',
  })
}

async function savePassport() {
  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
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
      expiry_date: passportForm.expiry_date || null,
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
  snilsForm.number = snils.number ?? ''
  snilsForm.ipra_number = selectedClient.value?.ipra_code ?? ''
  snilsForm.ipra_date = String(snils.issued_date ?? '').slice(0, 10)
  resetMessages()
}

function cancelSnilsEdit() {
  editingSnilsId.value = null
  Object.assign(snilsForm, {
    number: '',
    ipra_number: '',
    ipra_date: '',
  })
}

async function saveSnils() {
  isSaving.value = true
  resetMessages()

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
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
    successMessage.value = 'СНИЛС удален'
    cancelSnilsEdit()
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('identity', true)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

function getGroupTsrDraft(group: ClientTsrGroup) {
  return groupTsrDrafts[group.key] ?? group.tsrId
}

function setGroupTsrDraft(group: ClientTsrGroup, event: Event) {
  groupTsrDrafts[group.key] = (event.target as HTMLSelectElement).value
}

async function assignTsrToComponents(componentIds: string[], tsrId: string, message: string) {
  const clientId = selectedClient.value ? getClientId(selectedClient.value) : ''

  if (!clientId || !tsrId || componentIds.length === 0) {
    error.value = 'Выбери ТСР и хотя бы одну комплектующую.'
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await assignClientComponentsTsr(clientId, {
      component_ids: componentIds,
      tsr_id: tsrId,
    })
    Object.keys(groupTsrDrafts).forEach((key) => delete groupTsrDrafts[key])
    successMessage.value = message
    await refreshSelectedClient(clientId, false)
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function assignTsrToGroup(group: ClientTsrGroup) {
  const componentIds = group.components
    .map((component) => String(component.module_id ?? ''))
    .filter(Boolean)
  await assignTsrToComponents(
    componentIds,
    getGroupTsrDraft(group),
    'ТСР назначен всей группе комплектующих',
  )
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

    await updateModule(selectedModuleId.value, { client_id: clientId })
    selectedModuleId.value = ''
    successMessage.value = 'Комплектующая привязана к клиенту'
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

  if (!(await confirmAction({
    header: 'Вернуть на склад',
    message: `Отвязать комплектующую «${getModuleName(moduleItem)}» от клиента и вернуть на склад?`,
    acceptLabel: 'Вернуть на склад',
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await updateModule(moduleItem.module_id, { client_id: null })
    successMessage.value = 'Комплектующая отвязана и возвращена на склад'
    await loadClientTabData('modules', true)
    await loadClients()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
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
      successMessage.value = 'Комплектующая создана и привязана к клиенту'
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

async function removeClientModule(moduleItem: ModuleItem) {
  if (!selectedClient.value || !moduleItem.module_id) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить комплектующую «${getModuleName(moduleItem)}»?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    const clientId = getClientId(selectedClient.value)
    await deleteModule(moduleItem.module_id)
    successMessage.value = 'Комплектующая удалена'
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
    error.value = 'Для формирования договора выбери тип, буквенную часть номера, числовую часть номера и дату.'
    return
  }

  if (!/^\d+$/.test(suffix)) {
    error.value = 'Числовая часть номера договора должна содержать только цифры.'
    return
  }

  if (showExtendedContractDates.value && selectedContractModuleIds.value.length === 0) {
    error.value = 'Для договора ООО выбери хотя бы одну комплектующую клиента.'
    return
  }

  isSaving.value = true

  try {
    const clientId = await ensureClientExists()

    if (!clientId) {
      return
    }

    const payload: ContractGenerationPayload = {
      template_type: contractType.value.trim(),
      document_number: `${prefix}${suffix}`,
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

watch(query, () => {
  window.clearTimeout(clientFilterTimer)
  clientFilterTimer = window.setTimeout(applyClientFilters, 380)
})

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

onMounted(async () => {
  await Promise.all([loadClients(), loadReferences(), loadContractTemplates()])
  await openClientFromRoute(route.query.client_id)
})

onBeforeUnmount(() => {
  window.clearTimeout(clientFilterTimer)
  setBodyModalLock(false)
})
</script>

<template>
  <section class="page-section entity-workspace-page clients-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Клиентская база</p>
        <h1>Клиенты</h1>
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
        Создать клиента
      </button>
    </div>

    <div class="tabs" role="tablist" aria-label="Разделы клиентов">
      <button :class="{ active: activeClientListMode === 'active' }" type="button" @click="switchClientListMode('active')">
        Рабочие
      </button>
      <button :class="{ active: activeClientListMode === 'archive' }" type="button" @click="switchClientListMode('archive')">
        Архив
      </button>
    </div>

    <form class="toolbar-form clients-toolbar" @submit.prevent="applyClientFilters">
      <div class="toolbar-search-wrap">
        <Search :size="17" aria-hidden="true" />
        <input v-model="query" aria-label="Поиск клиента" placeholder="ФИО, телефон или данные клиента" />
      </div>
      <label class="filter-label">
        <span>Статус</span>
        <select v-model="statusFilter" @change="applyClientFilters">
          <option value="">Все статусы</option>
          <option v-for="option in statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="filter-label">
        <span>Этап</span>
        <select v-model="stageFilter" @change="applyClientFilters">
          <option value="">Все этапы</option>
          <option v-for="option in stageOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="filter-label">
        <span>Агент</span>
        <select v-model="agentFilter" @change="applyClientFilters">
          <option value="">Все агенты</option>
          <option v-for="agent in agents" :key="String(agent.agent_id)" :value="agent.agent_id">
            {{ getAgentName(agent) }}
          </option>
        </select>
      </label>
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
        <button
          v-if="activeClientFilterCount"
          class="ghost-button"
          type="button"
          @click="resetClientFilters"
        >
          <X :size="15" aria-hidden="true" />
          Сбросить
        </button>
        <span v-if="activeClientFilterCount" class="filter-count">
          {{ activeClientFilterCount }}
        </span>
      </div>
    </form>

    <p v-if="error && !isClientCardOpen" class="form-error">{{ error }}</p>
    <p v-if="successMessage && !isClientCardOpen" class="form-success">{{ successMessage }}</p>

    <div class="table-wrap desktop-entity-table">
      <table>
        <thead>
          <tr>
            <th>№</th>
            <th>Клиент</th>
            <th class="client-col-prosthetist">Протезист</th>
            <th>ТСР</th>
            <th class="client-col-check-date">Дата пробития</th>
            <th>Сертификат</th>
            <th>Статус</th>
            <th>Этап</th>
            <th>Агент</th>
            <th>Повторное</th>
            <th aria-label="Действия"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading" class="no-row-action">
            <td colspan="11">Загружаем клиентов...</td>
          </tr>
          <tr
            v-for="(client, index) in clients"
            v-else
            :key="String(client.client_id ?? client.external_id)"
            :class="{ selected: selectedClient && getClientId(selectedClient) === getClientId(client) }"
            tabindex="0"
            @click="selectClient(client)"
            @keydown.enter="selectClient(client)"
          >
            <td>{{ currentSkip + index + 1 }}</td>
            <td class="entity-cell">
              <div class="entity-primary">
                <span class="entity-avatar">{{ getClientInitials(client) }}</span>
                <span class="entity-copy">
                  <strong>{{ getClientName(client) }}</strong>
                  <span>{{ getClientPrimaryPhone(client) }} · ID {{ client.external_id || '—' }}</span>
                </span>
              </div>
            </td>
            <td class="client-col-prosthetist">{{ client.prosthetist || '—' }}</td>
            <td class="table-tsr">{{ getClientTsrLabel(client) }}</td>
            <td class="client-col-check-date">{{ getClientDate(client) }}</td>
            <td class="table-money">{{ formatMoney(client.certificate_price) }}</td>
            <td><StatusPill :label="getClientStatusLabel(client)" kind="status" /></td>
            <td><StatusPill :label="getClientStageLabel(client)" kind="stage" /></td>
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
        v-for="client in clients"
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
          <span>Статус <strong><StatusPill :label="getClientStatusLabel(client)" kind="status" /></strong></span>
          <span>Этап <strong><StatusPill :label="getClientStageLabel(client)" kind="stage" /></strong></span>
          <span>Агент <strong>{{ getAgentLabel(client.agent_id) }}</strong></span>
          <span>Повторное <strong>{{ getClientDeadline(client) }}</strong></span>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!isLoading && clients.length === 0"
      title="Клиенты не найдены"
      :description="activeClientFilterCount ? 'Измените или сбросьте фильтры.' : 'Создайте первую карточку клиента.'"
    >
      <button v-if="activeClientFilterCount" class="secondary-button" type="button" @click="resetClientFilters">
        Сбросить фильтры
      </button>
    </EmptyState>

    <div class="pagination-bar" aria-label="Пагинация клиентов">
      <span>Страница {{ currentPage }} · показано {{ clients.length }} · записи {{ currentSkip + 1 }}–{{ currentSkip + clients.length }}</span>
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
              <p class="eyebrow">{{ isEditing ? 'Карточка клиента' : 'Новый клиент' }}</p>
              <h2>{{ isEditing && selectedClient ? getClientName(selectedClient) : 'Создать клиента' }}</h2>
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
                {{ selectedClient.is_archived ? 'Восстановить' : 'В архив' }}
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
            <nav class="client-modal-nav" role="tablist" aria-label="Разделы карточки клиента">
              <button :class="{ active: activeTab === 'main' }" type="button" @click="openClientTab('main')">
                <UserRound :size="17" aria-hidden="true" />
                Основное
              </button>
              <button :class="{ active: activeTab === 'identity' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('identity')">
                <IdCard :size="17" aria-hidden="true" />
                Личные документы
              </button>
              <button :class="{ active: activeTab === 'phones' }" type="button" :disabled="!isClientPersisted" @click="openClientTab('phones')">
                <Phone :size="17" aria-hidden="true" />
                Телефоны
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
          </div>

          <label>
            Агент
            <select v-model="form.agent_id">
              <option value="">Не выбран</option>
              <option v-for="agent in agents" :key="String(agent.agent_id)" :value="agent.agent_id">
                {{ getAgentName(agent) }}
              </option>
            </select>
          </label>

          <div class="form-grid">
            <label>
              Протезист
              <input v-model="form.prosthetist" />
            </label>
            <label>
              Место проживания
              <textarea v-model="form.place_of_residence" rows="3" />
            </label>
          </div>

          <div class="form-heading">
            <div>
              <h2>Сертификат и протезирование</h2>
              <p class="muted">Каждая комплектующая назначается конкретному ТСР клиента.</p>
            </div>
            <button
              v-if="canManageReferences"
              class="secondary-button"
              type="button"
              @click="openReferenceManager"
            >
              Справочник ТСР
            </button>
          </div>

          <div class="form-grid">
            <label>
              Вид протеза
              <select v-model="form.prosthesis_type">
                <option value="" disabled hidden></option>
                <option v-for="option in prosthesisOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Дата пробития
              <DateInput v-model="form.check_date" aria-label="Дата чека" />
            </label>
            <label>
              Стоимость сертификата
              <input v-model="form.certificate_price" inputmode="decimal" placeholder="Например: 250 000" @blur="formatClientMoneyField('certificate_price')" />
            </label>
            <label>
              Налогообложение
              <select v-model="form.taxation_system">
                <option value="УСН">УСН</option>
                <option value="ОСНО">ОСНО</option>
              </select>
            </label>
          </div>

          <label>
            Повторное обращение
            <DateInput v-model="form.deadline" aria-label="Дедлайн" />
          </label>

          <div class="detail-panel tsr-module-panel">
            <p class="eyebrow">ТСР клиента</p>
            <div v-if="clientTsrGroups.length" class="tsr-component-groups">
              <article v-for="group in clientTsrGroups" :key="group.key" class="tsr-component-group">
                <header class="tsr-component-header">
                  <strong>{{ group.tsr }}</strong>
                  <span>Комплектующих: {{ group.components.length }}</span>
                </header>
                <ul class="component-name-list">
                  <li v-for="component in group.components" :key="String(component.module_id)">
                    <strong>{{ getModuleName(component) }}</strong>
                    <span>
                      {{ component.supplier || 'Поставщик не указан' }}
                      · {{ component.quantity ?? 1 }} шт.
                    </span>
                  </li>
                </ul>
              </article>
            </div>
            <p v-else class="muted">После привязки здесь появятся ТСР и списки относящихся к ним комплектующих.</p>
          </div>

          <label>
            Заметки
            <textarea v-model="form.notes" rows="4" />
          </label>
        </form>

        <div v-else-if="activeTab === 'identity'" class="detail-panel">
          <form class="side-form flat-form" @submit.prevent="savePassport">
            <div class="form-heading">
              <h2>Паспорт</h2>
            </div>
            <div class="form-grid">
              <label>
                Серия
                <input v-model="passportForm.series" />
              </label>
              <label>
                Номер
                <input v-model="passportForm.number" />
              </label>
              <label>
                Место рождения
                <input v-model="passportForm.birth_place" />
              </label>
            </div>
            <div class="form-grid">
              <label>
                Дата рождения
                <DateInput v-model="passportForm.birth_date" aria-label="Дата рождения" />
              </label>
              <label>
                Код подразделения
                <input v-model="passportForm.department_code" />
              </label>
              <label>
                Дата выдачи
                <DateInput v-model="passportForm.issue_date" aria-label="Дата выдачи паспорта" />
              </label>
              <label>
                Дата окончания
                <DateInput v-model="passportForm.expiry_date" :max-year="new Date().getFullYear() + 30" aria-label="Паспорт действителен до" />
              </label>
            </div>
            <div class="form-grid">
              <label>
                Кем выдан
                <input v-model="passportForm.issued_by" />
              </label>
              <label>
                Адрес регистрации
                <input v-model="passportForm.registration_address" />
              </label>
            </div>
            <div class="row-actions"><button class="secondary-button" :disabled="isSaving" type="submit">{{ editingPassportId ? 'Обновить паспорт' : 'Сохранить паспорт' }}</button><button v-if="editingPassportId" class="ghost-button" type="button" @click="cancelPassportEdit">Отмена</button></div>
          </form>

          <div class="list-stack">
            <div v-for="passport in passportItems" :key="String(passport.passport_id)" class="list-row">
              <div>
                <strong>{{ passport.series_number }}</strong>
                <span>
                  {{ passport.full_name }} · {{ passport.birth_date ?? 'дата рождения не указана' }} ·
                  {{ passport.issued_by }}
                </span>
              </div>
              <div class="row-actions">
                <button class="ghost-button" type="button" @click="startEditPassport(passport)">Изм.</button>
                <button class="danger-button" :disabled="isSaving" type="button" @click="removePassport(passport)">Удалить</button>
              </div>
            </div>
            <p v-if="passportItems.length === 0" class="muted">Паспорта пока не сохранены.</p>
          </div>

          <form class="side-form flat-form" @submit.prevent="saveSnils">
            <div class="form-heading">
              <h2>СНИЛС / ИПРА</h2>
            </div>
            <div class="form-grid">
              <label>
                СНИЛС
                <input v-model="snilsForm.number" />
              </label>
              <label>
                Номер ИПРА
                <input v-model="snilsForm.ipra_number" />
              </label>
              <label>
                Дата ИПРА
                <DateInput v-model="snilsForm.ipra_date" aria-label="Дата ИПРА" />
              </label>
            </div>
            <div class="row-actions"><button class="secondary-button" :disabled="isSaving" type="submit">{{ editingSnilsId ? 'Обновить СНИЛС' : 'Сохранить СНИЛС/ИПРА' }}</button><button v-if="editingSnilsId" class="ghost-button" type="button" @click="cancelSnilsEdit">Отмена</button></div>
          </form>

          <div class="list-stack">
            <div v-for="snils in snilsItems" :key="String(snils.snils_id)" class="list-row">
              <div>
                <strong>{{ snils.number }}</strong>
                <span>{{ snils.issued_date ? `Выдан: ${snils.issued_date}` : 'Дата выдачи не указана' }}</span>
              </div>
              <div class="row-actions">
                <button class="ghost-button" type="button" @click="startEditSnils(snils)">Изм.</button>
                <button class="danger-button" :disabled="isSaving" type="button" @click="removeSnils(snils)">Удалить</button>
              </div>
            </div>
            <p v-if="snilsItems.length === 0" class="muted">СНИЛС пока не сохранены.</p>
          </div>
        </div>

        <div v-else-if="activeTab === 'phones'" class="detail-panel">
          <p v-if="isTabLoading('phones')" class="muted">Загружаем телефоны...</p>
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

        <div v-else-if="activeTab === 'modules'" class="detail-panel">
          <p v-if="isTabLoading('modules')" class="muted">Загружаем комплектующие...</p>
          <template v-if="!selectedClient?.is_archived">
          <div class="form-heading">
            <h2>Выбрать комплектующую для клиента</h2>
          </div>
          <form class="toolbar-form compact-toolbar" @submit.prevent="assignModule">
            <select v-model="selectedModuleId">
              <option value="">Выбери комплектующую со склада</option>
              <option v-for="moduleItem in warehouseModules" :key="String(moduleItem.module_id)" :value="moduleItem.module_id">
                {{ moduleItem.tsr?.full_tsr_code || 'ТСР не выбран' }} — {{ getModuleName(moduleItem) }}
              </option>
            </select>
            <button class="secondary-button" :disabled="isSaving || !selectedModuleId" type="submit">
              Привязать
            </button>
          </form>

          <form class="side-form flat-form" @submit.prevent="saveClientModule">
            <div class="form-heading">
              <h2>{{ editingModuleId ? 'Редактирование комплектующей' : 'Создать комплектующую для клиента' }}</h2>
              <button v-if="editingModuleId" class="ghost-button" type="button" @click="resetModuleForm">Отмена</button>
            </div>

            <div class="form-grid">
              <label>
                ТСР *
                <select v-model="moduleForm.tsr_id" required>
                  <option value="">Выбери ТСР</option>
                  <option v-for="option in tsrOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label>
                Название и индекс *
                <input v-model="moduleForm.module_name_index" list="client-module-name-index-list" required />
                <datalist id="client-module-name-index-list">
                  <option v-for="option in nameIndexOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </datalist>
              </label>
              <label>
                Поставщик *
                <input v-model="moduleForm.supplier" required />
              </label>
              <label>
                Количество
                <input v-model="moduleForm.quantity" inputmode="numeric" />
              </label>
            </div>

            <div class="form-grid">
              <label>
                Себестоимость за ед.
                <input v-model="moduleForm.unit_cost" inputmode="decimal" @blur="formatModuleMoneyField('unit_cost')" />
              </label>
              <label>
                Цена за ед.
                <input v-model="moduleForm.unit_price" inputmode="decimal" @blur="formatModuleMoneyField('unit_price')" />
              </label>
              <label>
                Номер счета и дата заказа
                <input v-model="moduleForm.order_date_acc_num" />
              </label>
            </div>

            <div class="form-grid">
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
            </div>

            <div class="form-grid">
              <label>
                Заказано
                <input v-model="moduleForm.ordered" type="number" min="0" step="1" />
              </label>
              <label>
                Получено
                <input v-model="moduleForm.recd" type="number" min="0" step="1" />
              </label>
              <label>
                Ожидается
                <input v-model="moduleForm.pending" type="number" min="0" step="1" />
              </label>
              <label>
                У протезиста
                <input v-model="moduleForm.prosthetist_keep" type="number" min="0" step="1" />
              </label>
            </div>

            <label>
              Доп. свойства
              <input v-model="moduleForm.properties" />
            </label>

            <label>
              Заметки
              <textarea v-model="moduleForm.notes" rows="3" />
            </label>

            <button class="secondary-button" :disabled="isSaving" type="submit">
              {{ editingModuleId ? 'Сохранить комплектующую' : 'Создать комплектующую' }}
            </button>
          </form>
          </template>
          <p v-else class="form-hint">
            Комплектующие архивного клиента доступны для просмотра. Чтобы изменять их или назначать ТСР, сначала восстанови клиента.
          </p>

          <div v-if="clientTsrGroups.length" class="tsr-component-groups">
            <article v-for="group in clientTsrGroups" :key="group.key" class="tsr-component-group">
              <header class="tsr-component-header">
                <div>
                  <strong>{{ group.tsr }}</strong>
                  <span>Комплектующих: {{ group.components.length }}</span>
                </div>
                <strong>{{ formatMoney(getGroupTotalPrice(group)) }}</strong>
              </header>
              <div v-if="!selectedClient?.is_archived" class="tsr-assignment-controls">
                <label class="tsr-assignment-field">
                  <span>ТСР всей группы</span>
                  <select
                    :value="getGroupTsrDraft(group)"
                    :aria-label="`ТСР для группы ${group.tsr}`"
                    @change="setGroupTsrDraft(group, $event)"
                  >
                    <option value="">Выбери ТСР</option>
                    <option v-for="option in tsrOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="isSaving || !getGroupTsrDraft(group) || getGroupTsrDraft(group) === group.tsrId"
                  @click="assignTsrToGroup(group)"
                >
                  {{ group.tsrId ? 'Изменить для всей группы' : 'Назначить всей группе' }}
                </button>
              </div>

              <div class="list-stack">
                <div v-for="moduleItem in group.components" :key="String(moduleItem.module_id)" class="list-row">
                  <div>
                    <strong>{{ getModuleName(moduleItem) }}</strong>
                    <span>
                      {{ moduleItem.supplier || moduleItem.properties || 'Комплектующая клиента' }} ·
                      Кол-во: {{ moduleItem.quantity ?? 1 }} ·
                      Себест.: {{ formatMoney(moduleItem.cost) }} ·
                      Цена: {{ formatMoney(moduleItem.price) }}
                    </span>
                  </div>
                  <div v-if="!selectedClient?.is_archived" class="row-actions component-actions">
                    <button
                      class="ghost-button"
                      type="button"
                      title="Изменить данные или ТСР комплектующей"
                      @click="fillModuleForm(moduleItem)"
                    >
                      Изм.
                    </button>
                    <button class="ghost-button" :disabled="isSaving" type="button" @click="unassignModule(moduleItem)">
                      На склад
                    </button>
                    <button class="danger-button" :disabled="isSaving" type="button" @click="removeClientModule(moduleItem)">
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
          <p v-else class="muted">К клиенту пока не привязаны комплектующие.</p>
        </div>

        <div v-else-if="activeTab === 'documents'" class="detail-panel">
          <p v-if="isTabLoading('documents')" class="muted">Загружаем документы...</p>
          <form class="toolbar-form contract-toolbar" @submit.prevent="generateContract">
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
              <input v-model="contractNumberSuffix" class="contract-number-input" inputmode="numeric" placeholder="021225" />
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
          <div v-if="showExtendedContractDates" class="contract-module-selector">
            <p class="eyebrow">ТСР и комплектующие для договора</p>
            <article v-for="group in clientTsrGroups" :key="group.key" class="contract-tsr-group">
              <label class="checkbox-label contract-tsr-heading">
                <input
                  type="checkbox"
                  :checked="isContractGroupSelected(group)"
                  :indeterminate="isContractGroupPartiallySelected(group)"
                  @change="toggleContractGroup(group, $event)"
                />
                <span>
                  <strong>{{ group.tsr }}</strong>
                  · {{ group.components.length }} комплектующих
                  · {{ formatMoney(getGroupTotalPrice(group)) }}
                </span>
              </label>
              <div class="contract-component-list">
                <label
                  v-for="component in group.components"
                  :key="String(component.module_id)"
                  class="checkbox-label"
                >
                  <input
                    v-model="selectedContractModuleIds"
                    type="checkbox"
                    :value="String(component.module_id)"
                  />
                  <span>
                    <strong>{{ getModuleName(component) }}</strong>
                    · {{ component.quantity ?? 1 }} шт.
                    · {{ formatMoney(component.price) }}
                  </span>
                </label>
              </div>
            </article>
            <p v-if="clientTsrGroups.length === 0" class="muted">
              Сначала привяжи к клиенту комплектующие и назначь им ТСР.
            </p>
          </div>
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
              {{ isSaving ? 'Сохраняем...' : isEditing ? 'Сохранить изменения' : 'Создать клиента' }}
            </button>
          </div>
        </section>
      </div>
    </Teleport>

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

          <form class="reference-editor" @submit.prevent="saveManagedReference">
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
                <span>№ {{ index + 1 }}</span>
              </div>
              <div class="row-actions">
                <button class="ghost-button" type="button" :disabled="isReferenceSaving" @click="startEditReference(item)">Изм.</button>
                <button class="danger-button" type="button" :disabled="isReferenceSaving" @click="removeManagedReference(item)">Удалить</button>
              </div>
            </article>
            <p v-if="filteredReferenceItems.length === 0" class="empty-state">Записей не найдено.</p>
          </div>

          <p class="form-hint">
            Здесь управляются только коды ТСР. Поле «Вид протеза» использует фиксированный список категорий конечностей.
          </p>
        </section>
      </div>
    </Teleport>
  </section>
</template>
