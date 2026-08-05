<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DateInput from '@/shared/ui/DateInput.vue'
import ContractAccountingTab from '@/pages/ContractAccountingTab.vue'
import { formatMoney, formatMoneyInput, parseMoney } from '@/shared/lib/money'

import { useAuthStore } from '@/app/stores/auth'
import {
  createAccountingCustomField,
  deleteAccountingCustomField,
  fetchAccountingCustomFields,
  fetchClientContractCoverage,
  updateClientAccountingValues,
} from '@/shared/api/accounting'
import { fetchUserSettings, updateUserSettings } from '@/shared/api/auth'
import { fetchClients, updateClient } from '@/shared/api/clients'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import { matchesTableFilter, nextSortState, sortTableRows, type SortDirection, type TableFilterKind } from '@/shared/lib/table'
import SortableFilterHeader from '@/shared/ui/SortableFilterHeader.vue'
import type {
  AccountingCustomField,
  Client,
  ClientContractCoverage,
  ClientUpdatePayload,
} from '@/shared/types/entities'

type ExpenseKey =
  | 'prosthetist_work'
  | 'patient_travel'
  | 'patient_accommodation'
  | 'patient_meals'
  | 'patient_payment'
  | 'other_expenses'
  | 'agency_expenses'

type EditableRow = Record<ExpenseKey, string> & {
  custom: Record<string, string>
}

const expenseColumns: Array<{ key: ExpenseKey; label: string }> = [
  { key: 'prosthetist_work', label: 'Работа протезиста' },
  { key: 'patient_travel', label: 'Проезд пациента' },
  { key: 'patient_accommodation', label: 'Проживание пациента' },
  { key: 'patient_meals', label: 'Питание пациента' },
  { key: 'patient_payment', label: 'Пациенту' },
  { key: 'other_expenses', label: 'Прочее' },
  { key: 'agency_expenses', label: 'Агентские' },
]

const leadingColumns = [
  { key: 'client', label: 'Клиент' },
  { key: 'certificate', label: 'Сертификат' },
  { key: 'modules_cost', label: 'Стоимость комплектующих' },
]

const trailingColumns = [
  { key: 'vat', label: 'НДС' },
  { key: 'tax', label: 'Налог' },
  { key: 'acquiring', label: 'Эквайринг' },
  { key: 'profit', label: 'Прибыль' },
]

const authStore = useAuthStore()
const router = useRouter()
const activeAccountingTab = ref<'clients' | 'contracts'>('clients')
const clients = ref<Client[]>([])
const customFields = ref<AccountingCustomField[]>([])
const contractCoverage = ref<ClientContractCoverage[]>([])
const query = ref('')
const startDate = ref('')
const endDate = ref('')
const hideFailed = ref(true)
const taxUsnPercent = ref(6)
const taxOsnoPercent = ref(15)
const acquiringPercent = ref(1)
const vatPercent = ref(20)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>([])
const knownColumnKeys = ref<string[]>([])
const accountingColumnFilters = reactive<Record<string, string>>({})
const accountingSortKey = ref<string | null>(null)
const accountingSortDirection = ref<SortDirection>(null)
const editableRows = reactive<Record<string, EditableRow>>({})
const isLoading = ref(false)
const isSaving = ref(false)
const isPercentSaving = ref(false)
const isSettingsReady = ref(false)
let percentSaveTimeout: number | undefined
const error = ref('')
const successMessage = ref('')
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Бухгалтерия')

const numericCustomFields = computed(() =>
  customFields.value.filter((field) => getFieldType(field) === 'number'),
)

const availableColumns = computed(() => [
  ...leadingColumns,
  ...expenseColumns,
  ...customFields.value.map((field) => ({
    key: getCustomColumnKey(field),
    label: getFieldName(field),
  })),
  ...trailingColumns,
])

const coverageByClientId = computed(() => new Map(
  contractCoverage.value.map((coverage) => [coverage.client_id, coverage]),
))

type CertificateSlice = { id: string; date: string; amount: number }

function getCertificateSlices(client: Client): CertificateSlice[] {
  const normalized = (client.tsr_items ?? [])
    .map((item) => ({
      id: String(item.client_tsr_id ?? ''),
      date: String(item.check_date ?? '').slice(0, 10),
      amount: parseMoney(item.certificate_price),
    }))
    .filter((item) => item.amount > 0)

  if (normalized.length > 0) return normalized
  return [{
    id: '',
    date: String(client.check_date ?? '').slice(0, 10),
    amount: parseMoney(client.certificate_price),
  }]
}

function getVisibleCertificateSlices(client: Client) {
  return getCertificateSlices(client).filter((item) => {
    if (!startDate.value && !endDate.value) return true
    if (!item.date) return false
    if (startDate.value && item.date < startDate.value) return false
    if (endDate.value && item.date > endDate.value) return false
    return true
  })
}

function clientSearchText(client: Client) {
  return [
    getClientName(client), getAgentName(client), client.external_id,
    client.notes, client.ipra_code, client.place_of_residence,
    ...(client.phones ?? []).map((phone) => phone.number),
    ...(client.passports ?? []).flatMap((passport) => [
      passport.full_name, passport.series_number, passport.registration_address,
    ]),
    ...(client.snils ?? []).map((snils) => snils.number),
    ...(client.tsr_items ?? []).flatMap((item) => [
      item.tsr?.full_tsr_code, item.certificate_price, item.check_date,
    ]),
  ].filter(Boolean).join(' ').toLocaleLowerCase('ru-RU')
}

const filteredClients = computed(() => {
  const normalizedQuery = query.value.trim().toLocaleLowerCase('ru-RU')
  return clients.value.filter((client) => {
    if (hideFailed.value && isFailedClient(client)) return false
    if ((startDate.value || endDate.value) && getVisibleCertificateSlices(client).length === 0) return false
    return !normalizedQuery || clientSearchText(client).includes(normalizedQuery)
  })
})

const calculatedRows = computed(() =>
  filteredClients.value.map((client) => {
    const certificateSlices = getVisibleCertificateSlices(client)
    const certificateIds = new Set(certificateSlices.map((item) => item.id).filter(Boolean))
    const rawCertificate = certificateSlices.reduce((sum, item) => sum + item.amount, 0)
    const rawModulesCost = getModulesCost(client, certificateIds)
    const editable = ensureEditableRow(client)
    const fixedExpenses = expenseColumns.reduce((sum, column) => sum + parseMoney(editable[column.key]), 0)
    const customExpenses = numericCustomFields.value.reduce(
      (sum, field) => sum + parseMoney(getCustomEditableValue(client, field)),
      0,
    )
    const taxPercent = getClientTaxPercent(client)
    const vat = rawCertificate * (vatPercent.value / (100 + vatPercent.value))
    const revenueWithoutVat = rawCertificate - vat
    const acquiring = rawCertificate * (acquiringPercent.value / 100)
    const taxBase = Math.max(
      0,
      revenueWithoutVat - rawModulesCost - fixedExpenses - customExpenses - acquiring,
    )
    const tax = taxBase * (taxPercent / 100)
    const profit = revenueWithoutVat - rawModulesCost - fixedExpenses - customExpenses - acquiring - tax

    return {
      client,
      certificateDates: certificateSlices.map((item) => item.date).filter(Boolean),
      certificate: rawCertificate,
      modulesCost: rawModulesCost,
      fixedExpenses,
      customExpenses,
      vat,
      tax,
      acquiring,
      profit,
    }
  }),
)

function accountingColumnValue(row: (typeof calculatedRows.value)[number], key: string): unknown {
  if (key === 'client') return `${getClientName(row.client)} ${getAgentName(row.client)} ${row.certificateDates.join(' ')}`
  if (key === 'certificate') return row.certificate
  if (key === 'modules_cost') return row.modulesCost
  if (key === 'vat') return row.vat
  if (key === 'tax') return row.tax
  if (key === 'acquiring') return row.acquiring
  if (key === 'profit') return row.profit
  if (key.startsWith('custom:')) {
    const field = customFields.value.find((item) => getCustomColumnKey(item) === key)
    return field ? getCustomEditableValue(row.client, field) : ''
  }
  if (expenseColumns.some((column) => column.key === key)) {
    return parseMoney(getExpenseValue(row.client, key as ExpenseKey))
  }
  return ''
}

function accountingFilterKind(key: string): TableFilterKind {
  if (key === 'client') return 'text'
  if (key.startsWith('custom:')) {
    const field = customFields.value.find((item) => getCustomColumnKey(item) === key)
    return field && getFieldType(field) === 'text' ? 'text' : 'number'
  }
  return 'number'
}

function sortAccounting(key: string) {
  const next = nextSortState({ key: accountingSortKey.value, direction: accountingSortDirection.value }, key)
  accountingSortKey.value = next.key
  accountingSortDirection.value = next.direction
  currentPage.value = 1
}

const rows = computed(() => {
  const filtered = calculatedRows.value.filter((row) => availableColumns.value.every((column) => (
    matchesTableFilter(
      accountingColumnValue(row, column.key),
      accountingColumnFilters[column.key] ?? '',
      accountingFilterKind(column.key),
    )
  )))
  return sortTableRows(filtered, accountingSortKey.value, accountingSortDirection.value, accountingColumnValue)
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageLimit.value
  return rows.value.slice(start, start + pageLimit.value)
})

const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => currentPage.value * pageLimit.value < rows.value.length)
const visibleRangeStart = computed(() => (
  rows.value.length === 0 ? 0 : (currentPage.value - 1) * pageLimit.value + 1
))
const visibleRangeEnd = computed(() => Math.min(currentPage.value * pageLimit.value, rows.value.length))
const activeAccountingFilterCount = computed(() => [
  query.value.trim(),
  startDate.value,
  endDate.value,
  ...Object.values(accountingColumnFilters).map((value) => value.trim()),
].filter(Boolean).length)

const totals = computed(() =>
  rows.value.reduce(
    (acc, row) => {
      acc.certificate += row.certificate
      acc.modulesCost += row.modulesCost
      acc.fixedExpenses += row.fixedExpenses
      acc.customExpenses += row.customExpenses
      acc.vat += row.vat
      acc.tax += row.tax
      acc.acquiring += row.acquiring
      acc.profit += row.profit
      return acc
    },
    {
      certificate: 0,
      modulesCost: 0,
      fixedExpenses: 0,
      customExpenses: 0,
      vat: 0,
      tax: 0,
      acquiring: 0,
      profit: 0,
    },
  ),
)

function resetMessages() {
  error.value = ''
  successMessage.value = ''
}

function getClientId(client: Client) {
  return String(client.client_id ?? '')
}

function openClientCard(client: Client) {
  const clientId = getClientId(client)
  if (clientId) {
    void router.push({ name: 'clients', query: { client_id: clientId } })
  }
}

function getClientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ') || 'Без имени'
}

function getAgentName(client: Client) {
  const agent = client.agent
  return agent ? [agent.last_name, agent.first_name, agent.middle_name].filter(Boolean).join(' ') : '—'
}

function getCheckDate(client: Client) {
  const dates = getVisibleCertificateSlices(client).map((item) => item.date).filter(Boolean).sort()
  return dates.length > 0 ? dates[dates.length - 1] : ''
}

function getTaxationSystem(client: Client) {
  return `УСН ${getClientTaxPercent(client)}%`
}

function getClientTaxPercent(client: Client) {
  return client.taxation_system === 'ОСНО' ? taxOsnoPercent.value : taxUsnPercent.value
}

function clientRequiresContract(client: Client) {
  return coverageByClientId.value.get(getClientId(client))?.requires_contract ?? false
}

function isFailedClient(client: Client) {
  const status = String(client.status_code ?? '').toLowerCase()
  const stage = String(client.current_stage ?? '').toLowerCase()
  const text = `${status} ${stage}`
  return ['fail', 'hold', 'cancel', 'отказ', 'отлож', 'отмен'].some((token) => text.includes(token))
}

function getModulesCost(client: Client, visibleCertificateIds: Set<string>) {
  const dateFilterActive = Boolean(startDate.value || endDate.value)
  const hasNormalizedCertificates = (client.tsr_items ?? []).length > 0
  return (client.modules ?? []).reduce((sum, component) => {
    if (component.is_archived) return sum
    if (dateFilterActive && hasNormalizedCertificates) {
      const certificateId = String(component.client_tsr_id ?? '')
      if (!certificateId || !visibleCertificateIds.has(certificateId)) return sum
    }
    return sum + parseMoney(component.cost)
  }, 0)
}

function getFieldId(field: AccountingCustomField) {
  return String(field.field_id ?? field.id ?? '')
}

function getFieldName(field: AccountingCustomField) {
  return String(field.field_name ?? field.name ?? field.label ?? getFieldId(field))
}

function getFieldType(field: AccountingCustomField) {
  return String(field.field_type ?? field.type ?? 'number') === 'text' ? 'text' : 'number'
}

function getCustomColumnKey(field: AccountingCustomField) {
  return `custom:${getFieldId(field)}`
}

function isColumnVisible(key: string) {
  return selectedColumnKeys.value.includes(key)
}

function toggleColumn(key: string) {
  if (selectedColumnKeys.value.includes(key)) {
    selectedColumnKeys.value = selectedColumnKeys.value.filter((item) => item !== key)
  } else {
    selectedColumnKeys.value = [...selectedColumnKeys.value, key]
  }
}

function visibleColumnCount() {
  return availableColumns.value.filter((column) => isColumnVisible(column.key)).length + 1
}

function syncSelectedColumns() {
  const availableKeys = availableColumns.value.map((column) => column.key)
  const available = new Set(availableKeys)

  if (knownColumnKeys.value.length === 0) {
    knownColumnKeys.value = availableKeys
    selectedColumnKeys.value = availableKeys
    return
  }

  const newKeys = availableKeys.filter((key) => !knownColumnKeys.value.includes(key))
  selectedColumnKeys.value = [
    ...selectedColumnKeys.value.filter((key) => available.has(key)),
    ...newKeys,
  ]
  knownColumnKeys.value = availableKeys
}

function resetAccountingPage() {
  currentPage.value = 1
}

function resetAccountingFilters() {
  query.value = ''
  startDate.value = ''
  endDate.value = ''
  Object.keys(accountingColumnFilters).forEach((key) => { accountingColumnFilters[key] = '' })
  accountingSortKey.value = null
  accountingSortDirection.value = null
  resetAccountingPage()
}

function ensureEditableRow(client: Client) {
  const clientId = getClientId(client)

  if (!editableRows[clientId]) {
    editableRows[clientId] = {
      prosthetist_work: formatMoneyInput(client.prosthetist_work ?? 0),
      patient_travel: formatMoneyInput(client.patient_travel ?? 0),
      patient_accommodation: formatMoneyInput(client.patient_accommodation ?? 0),
      patient_meals: formatMoneyInput(client.patient_meals ?? 0),
      patient_payment: formatMoneyInput(client.patient_payment ?? 0),
      other_expenses: formatMoneyInput(client.other_expenses ?? 0),
      agency_expenses: formatMoneyInput(client.agency_expenses ?? 0),
      custom: {},
    }
  }

  return editableRows[clientId]
}

function getExpenseValue(client: Client, key: ExpenseKey) {
  return ensureEditableRow(client)[key]
}

function setExpenseValue(client: Client, key: ExpenseKey, value: string) {
  ensureEditableRow(client)[key] = value
}

function formatExpenseValue(client: Client, key: ExpenseKey) {
  setExpenseValue(client, key, formatMoneyInput(getExpenseValue(client, key)))
}

function getCustomEditableValue(client: Client, field: AccountingCustomField) {
  const row = ensureEditableRow(client)
  const fieldId = getFieldId(field)

  if (!(fieldId in row.custom)) {
    const fieldName = getFieldName(field)
    const source = client.custom_fields ?? {}
    const initialValue = source[fieldName] ?? source[fieldId] ?? ''
    row.custom[fieldId] = initialValue == null ? '' : String(initialValue)
  }

  return row.custom[fieldId]
}

function setCustomEditableValue(client: Client, field: AccountingCustomField, value: string) {
  ensureEditableRow(client).custom[getFieldId(field)] = value
}

function formatCustomEditableValue(client: Client, field: AccountingCustomField) {
  if (getFieldType(field) === 'number') {
    setCustomEditableValue(client, field, formatMoneyInput(getCustomEditableValue(client, field)))
  }
}

async function loadSettings() {
  const userId = authStore.user?.user_id

  if (!userId) {
    isSettingsReady.value = true
    return
  }

  try {
    const settings = await fetchUserSettings(userId)
    const savedUsn = settings.tax_usn_percent ?? settings.tax_percent

    if (typeof savedUsn === 'number') {
      taxUsnPercent.value = savedUsn
    }
    if (typeof settings.tax_osno_percent === 'number') {
      taxOsnoPercent.value = settings.tax_osno_percent
    }
    if (typeof settings.acq_percent === 'number') {
      acquiringPercent.value = settings.acq_percent
    }
    if (typeof settings.vat_percent === 'number') {
      vatPercent.value = settings.vat_percent
    }
  } catch {
    // Настройки не должны блокировать бухгалтерию.
  } finally {
    isSettingsReady.value = true
  }
}

function queuePercentSettingsSave() {
  if (!isSettingsReady.value) {
    return
  }

  window.clearTimeout(percentSaveTimeout)
  percentSaveTimeout = window.setTimeout(() => {
    void savePercentSettings()
  }, 800)
}

async function savePercentSettings() {
  const userId = authStore.user?.user_id

  if (!userId) {
    return
  }

  isPercentSaving.value = true

  try {
    await updateUserSettings(userId, {
      tax_percent: taxUsnPercent.value,
      tax_usn_percent: taxUsnPercent.value,
      tax_osno_percent: taxOsnoPercent.value,
      acq_percent: acquiringPercent.value,
      vat_percent: vatPercent.value,
    })
    successMessage.value = 'Проценты сохранены автоматически'
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isPercentSaving.value = false
  }
}

async function loadData() {
  isLoading.value = true
  error.value = ''

  try {
    const [clientsResponse, fieldsResponse, coverageResponse] = await Promise.all([
      fetchClients({ limit: 100000 }),
      fetchAccountingCustomFields(),
      fetchClientContractCoverage(),
    ])

    clients.value = clientsResponse
    customFields.value = fieldsResponse
    contractCoverage.value = coverageResponse
    syncSelectedColumns()
    Object.keys(editableRows).forEach((key) => delete editableRows[key])
    resetAccountingPage()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

async function saveClientValues(client: Client) {
  const clientId = getClientId(client)

  if (!clientId) {
    return
  }

  const row = ensureEditableRow(client)
  isSaving.value = true
  resetMessages()

  try {
    const expensePayload = Object.fromEntries(
      expenseColumns.map((column) => [column.key, parseMoney(row[column.key])]),
    ) as ClientUpdatePayload
    await updateClient(clientId, expensePayload)

    const values = customFields.value
      .map((field) => {
        const fieldId = getFieldId(field)
        const rawValue = getCustomEditableValue(client, field)
        return {
          field_id: fieldId,
          value: getFieldType(field) === 'number' ? parseMoney(rawValue) : rawValue,
        }
      })
      .filter((value) => value.field_id)

    if (values.length > 0) {
      await updateClientAccountingValues(clientId, values)
    }

    successMessage.value = 'Значения сохранены'
    await loadData()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function addCustomField() {
  const name = newFieldName.value.trim()

  if (!name) {
    error.value = 'Введите название нового поля.'
    return
  }

  if (customFields.value.some((field) => getFieldName(field).toLowerCase() === name.toLowerCase())) {
    error.value = 'Поле с таким названием уже есть.'
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await createAccountingCustomField({ field_name: name, field_type: newFieldType.value })
    newFieldName.value = ''
    successMessage.value = 'Поле добавлено'
    await loadData()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeCustomField(field: AccountingCustomField) {
  const fieldId = getFieldId(field)

  if (!fieldId) {
    return
  }

  if (!(await confirmAction({
    message: `Удалить поле «${getFieldName(field)}» из обеих бухгалтерий?`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteAccountingCustomField(fieldId)
    successMessage.value = 'Поле удалено'
    await loadData()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

watch([query, startDate, endDate, hideFailed, pageLimit, accountingColumnFilters], resetAccountingPage, { deep: true })
watch([taxUsnPercent, taxOsnoPercent, acquiringPercent, vatPercent], queuePercentSettingsSave)
watch(activeAccountingTab, (tab) => {
  if (tab === 'clients') {
    void loadData()
  }
})

onMounted(async () => {
  await Promise.all([loadSettings(), loadData()])
})
</script>

<template>
  <section class="page-section accounting-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Admin</p>
        <h1>Бухгалтерия</h1>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button :class="{ active: activeAccountingTab === 'clients' }" type="button" @click="activeAccountingTab = 'clients'">
        По клиентам
      </button>
      <button :class="{ active: activeAccountingTab === 'contracts' }" type="button" @click="activeAccountingTab = 'contracts'">
        По договорам
      </button>
    </div>

    <div class="toolbar-form accounting-percent-toolbar">
      <label>
        УСН · первая ставка, %
        <input v-model.number="taxUsnPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        УСН · вторая ставка, %
        <input v-model.number="taxOsnoPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        Эквайринг, %
        <input v-model.number="acquiringPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        НДС, %
        <input v-model.number="vatPercent" min="0" step="0.1" type="number" />
      </label>
      <span class="muted accounting-autosave-status">
        {{ isPercentSaving ? 'Сохраняем проценты...' : 'Проценты сохраняются автоматически' }}
      </span>
    </div>

    <template v-if="activeAccountingTab === 'clients'">
      <form class="inline-search wide-search contract-accounting-search" @submit.prevent="loadData">
        <input v-model="query" placeholder="ФИО, телефон, паспорт, СНИЛС, ТСР или агент" />
        <DateInput v-model="startDate" aria-label="Дата начала" />
        <DateInput v-model="endDate" aria-label="Дата окончания" />
        <button class="secondary-button" type="submit">Обновить</button>
        <button v-if="activeAccountingFilterCount" class="ghost-button" type="button" @click="resetAccountingFilters">
          Сбросить фильтры
        </button>
      </form>

      <p v-if="error" class="form-error">{{ error }}</p>
      <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

      <div class="metric-grid">
        <div class="metric-card">
          <span>Сумма сертификатов</span>
          <strong>{{ formatMoney(totals.certificate) }}</strong>
        </div>
        <div class="metric-card">
          <span>Расходы</span>
          <strong>
            {{ formatMoney(totals.modulesCost + totals.fixedExpenses + totals.customExpenses + totals.vat + totals.tax + totals.acquiring) }}
          </strong>
        </div>
        <div class="metric-card">
          <span>Чистая прибыль</span>
          <strong>{{ formatMoney(totals.profit) }}</strong>
        </div>
      </div>

      <div class="toolbar-form accounting-toolbar">
        <label class="checkbox-label">
          <input v-model="hideFailed" type="checkbox" />
          Скрыть отказы и отложенных
        </label>
        <input v-model="newFieldName" placeholder="Новое поле для обеих бухгалтерий" />
        <select v-model="newFieldType">
          <option value="number">Число / расход</option>
          <option value="text">Текст</option>
        </select>
        <button class="secondary-button" :disabled="isSaving || !newFieldName.trim()" type="button" @click="addCustomField">
          Добавить поле
        </button>
        <label class="compact-field">
          На странице
          <select v-model.number="pageLimit">
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </label>
      </div>

      <p class="form-hint">Скрытие колонок не влияет на расчёты. НДС извлекается из суммы сертификата, эквайринг считается от полной суммы, а УСН — от выручки без НДС за вычетом себестоимости комплектующих и эквайринга.</p>

      <div class="field-chip-row" aria-label="Настройка колонок бухгалтерии">
        <button
          v-for="column in availableColumns"
          :key="column.key"
          class="field-chip"
          :class="{ muted: !isColumnVisible(column.key) }"
          type="button"
          @click="toggleColumn(column.key)"
        >
          {{ isColumnVisible(column.key) ? '✓' : '+' }} {{ column.label }}
        </button>
      </div>

      <div v-if="customFields.length > 0" class="field-chip-row">
        <button
          v-for="field in customFields"
          :key="getFieldId(field)"
          class="field-chip"
          :disabled="isSaving"
          type="button"
          @click="removeCustomField(field)"
        >
          {{ getFieldName(field) }} · {{ getFieldType(field) === 'number' ? 'число' : 'текст' }} ×
        </button>
      </div>

      <p v-if="isLoading" class="muted">Загружаем бухгалтерию...</p>

      <div v-else class="table-wrap accounting-table">
        <table>
          <thead>
            <tr>
              <SortableFilterHeader v-if="isColumnVisible('client')" label="Клиент" column-key="client" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.client" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.client = $event" />
              <SortableFilterHeader v-if="isColumnVisible('certificate')" label="Сертификат" column-key="certificate" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.certificate" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.certificate = $event" />
              <SortableFilterHeader v-if="isColumnVisible('modules_cost')" label="Стоимость комплектующих" column-key="modules_cost" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.modules_cost" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.modules_cost = $event" />
              <SortableFilterHeader
                v-for="column in expenseColumns.filter((item) => isColumnVisible(item.key))"
                :key="column.key"
                :label="column.label"
                :column-key="column.key"
                filter-kind="number"
                placeholder="Сумма или диапазон"
                :sort-key="accountingSortKey"
                :sort-direction="accountingSortDirection"
                :filter-value="accountingColumnFilters[column.key]"
                @sort="sortAccounting"
                @update:filter-value="accountingColumnFilters[column.key] = $event"
              />
              <SortableFilterHeader
                v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))"
                :key="getFieldId(field)"
                :label="getFieldName(field)"
                :column-key="getCustomColumnKey(field)"
                :filter-kind="getFieldType(field) === 'number' ? 'number' : 'text'"
                :placeholder="getFieldType(field) === 'number' ? 'Сумма или диапазон' : 'Фильтр…'"
                :sort-key="accountingSortKey"
                :sort-direction="accountingSortDirection"
                :filter-value="accountingColumnFilters[getCustomColumnKey(field)]"
                @sort="sortAccounting"
                @update:filter-value="accountingColumnFilters[getCustomColumnKey(field)] = $event"
              />
              <SortableFilterHeader v-if="isColumnVisible('vat')" label="НДС" column-key="vat" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.vat" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.vat = $event" />
              <SortableFilterHeader v-if="isColumnVisible('tax')" label="Налог" column-key="tax" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.tax" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.tax = $event" />
              <SortableFilterHeader v-if="isColumnVisible('acquiring')" label="Эквайринг" column-key="acquiring" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.acquiring" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.acquiring = $event" />
              <SortableFilterHeader v-if="isColumnVisible('profit')" label="Прибыль" column-key="profit" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="accountingSortKey" :sort-direction="accountingSortDirection" :filter-value="accountingColumnFilters.profit" @sort="sortAccounting" @update:filter-value="accountingColumnFilters.profit = $event" />
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in pagedRows"
              :key="getClientId(row.client)"
              :class="{ 'contract-required-row': clientRequiresContract(row.client) }"
            >
              <td v-if="isColumnVisible('client')" class="accounting-identity-cell">
                <button class="link-button accounting-client-link" type="button" @click="openClientCard(row.client)">
                  <strong>{{ getClientName(row.client) }}</strong>
                  <span class="muted">{{ getTaxationSystem(row.client) }} · дата пробития {{ getCheckDate(row.client) || '—' }}</span>
                  <span v-if="clientRequiresContract(row.client)" class="contract-warning">
                    Необходимо сделать договор
                  </span>
                </button>
              </td>
              <td v-if="isColumnVisible('certificate')" class="table-money">{{ formatMoney(row.certificate) }}</td>
              <td v-if="isColumnVisible('modules_cost')" class="table-money">{{ formatMoney(row.modulesCost) }}</td>
              <td v-for="column in expenseColumns.filter((item) => isColumnVisible(item.key))" :key="column.key">
                <input
                  class="table-input"
                  :value="getExpenseValue(row.client, column.key)"
                  inputmode="decimal"
                  @input="setExpenseValue(row.client, column.key, ($event.target as HTMLInputElement).value)"
                  @blur="formatExpenseValue(row.client, column.key)"
                />
              </td>
              <td
                v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))"
                :key="getFieldId(field)"
              >
                <input
                  class="table-input"
                  :value="getCustomEditableValue(row.client, field)"
                  :inputmode="getFieldType(field) === 'number' ? 'decimal' : 'text'"
                  @input="setCustomEditableValue(row.client, field, ($event.target as HTMLInputElement).value)"
                  @blur="formatCustomEditableValue(row.client, field)"
                />
              </td>
              <td v-if="isColumnVisible('vat')" class="table-money">{{ formatMoney(row.vat) }}</td>
              <td
                v-if="isColumnVisible('tax')"
                class="table-money"
                :title="getTaxationSystem(row.client)"
              >
                {{ formatMoney(row.tax) }}
              </td>
              <td v-if="isColumnVisible('acquiring')" class="table-money">{{ formatMoney(row.acquiring) }}</td>
              <td
                v-if="isColumnVisible('profit')"
                class="table-money"
                :class="{ profitNegative: row.profit < 0 }"
              >
                <strong>{{ formatMoney(row.profit) }}</strong>
              </td>
              <td class="row-actions">
                <button class="ghost-button" :disabled="isSaving" type="button" @click="saveClientValues(row.client)">
                  Сохранить
                </button>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td :colspan="visibleColumnCount()">Нет данных для отчёта.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pagination-bar" aria-label="Пагинация бухгалтерии">
        <span>
          Страница {{ currentPage }} · показано {{ pagedRows.length }} из {{ rows.length }}
          · записи {{ visibleRangeStart }}–{{ visibleRangeEnd }}
        </span>
        <div class="row-actions">
          <button class="secondary-button" type="button" :disabled="isLoading || !hasPreviousPage" @click="currentPage -= 1">
            Назад
          </button>
          <button class="secondary-button" type="button" :disabled="isLoading || !hasNextPage" @click="currentPage += 1">
            Вперёд
          </button>
        </div>
      </div>
    </template>

    <ContractAccountingTab
      v-else
      :tax-usn-percent="taxUsnPercent"
      :tax-osno-percent="taxOsnoPercent"
      :acquiring-percent="acquiringPercent"
      :vat-percent="vatPercent"
    />
  </section>
</template>
