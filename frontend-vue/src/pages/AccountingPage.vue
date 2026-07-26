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
  { key: 'client', label: 'Договор / клиент' },
  { key: 'certificate', label: 'Сертификат' },
  { key: 'modules_cost', label: 'Стоимость комплектующих' },
]

const trailingColumns = [
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
const taxOsnoPercent = ref(20)
const acquiringPercent = ref(1)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>([])
const knownColumnKeys = ref<string[]>([])
const editableRows = reactive<Record<string, EditableRow>>({})
const isLoading = ref(false)
const isSaving = ref(false)
const isPercentSaving = ref(false)
const isSettingsReady = ref(false)
let percentSaveTimeout: number | undefined
const error = ref('')
const successMessage = ref('')

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

const filteredClients = computed(() => {
  const normalizedQuery = query.value.trim().toLowerCase()

  return clients.value.filter((client) => {
    if (hideFailed.value && isFailedClient(client)) {
      return false
    }

    const date = getCheckDate(client)

    if ((startDate.value || endDate.value) && !date) {
      return false
    }

    if (startDate.value && date && date < startDate.value) {
      return false
    }

    if (endDate.value && date && date > endDate.value) {
      return false
    }

    if (!normalizedQuery) {
      return true
    }

    return `${getClientName(client)} ${getAgentName(client)}`.toLowerCase().includes(normalizedQuery)
  })
})

const rows = computed(() =>
  filteredClients.value.map((client) => {
    const rawCertificate = parseMoney(client.certificate_price)
    const rawModulesCost = getModulesCost(client)
    const editable = ensureEditableRow(client)
    const fixedExpenses = expenseColumns.reduce((sum, column) => (
      sum + (isColumnVisible(column.key) ? parseMoney(editable[column.key]) : 0)
    ), 0)
    const customExpenses = numericCustomFields.value.reduce((sum, field) => {
      if (!isColumnVisible(getCustomColumnKey(field))) {
        return sum
      }

      return sum + parseMoney(getCustomEditableValue(client, field))
    }, 0)

    const certificate = isColumnVisible('certificate') ? rawCertificate : 0
    const modulesCost = isColumnVisible('modules_cost') ? rawModulesCost : 0
    const taxPercent = getClientTaxPercent(client)
    const tax = isColumnVisible('tax') ? certificate * (taxPercent / 100) : 0
    const acquiring = isColumnVisible('acquiring')
      ? certificate * (acquiringPercent.value / 100)
      : 0
    const hasNoAccountingBasis = rawModulesCost === 0 && !getCheckDate(client)
    const profit = hasNoAccountingBasis
      ? 0
      : certificate - modulesCost - fixedExpenses - customExpenses - tax - acquiring

    return {
      client,
      certificate,
      modulesCost,
      fixedExpenses,
      customExpenses,
      tax,
      taxPercent,
      acquiring,
      profit,
    }
  }),
)

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

const totals = computed(() =>
  rows.value.reduce(
    (acc, row) => {
      acc.certificate += row.certificate
      acc.modulesCost += row.modulesCost
      acc.fixedExpenses += row.fixedExpenses
      acc.customExpenses += row.customExpenses
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
  return String(client.check_date ?? '').slice(0, 10)
}

function getTaxationSystem(client: Client): 'УСН' | 'ОСНО' {
  return client.taxation_system === 'ОСНО' ? 'ОСНО' : 'УСН'
}

function getClientTaxPercent(client: Client) {
  return getTaxationSystem(client) === 'ОСНО' ? taxOsnoPercent.value : taxUsnPercent.value
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

function getModulesCost(client: Client) {
  return (client.modules ?? []).reduce((sum, component) => {
    if (component.is_archived) {
      return sum
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

  if (!fieldId || !window.confirm(`Удалить поле «${getFieldName(field)}» из обеих бухгалтерий?`)) {
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

watch([query, startDate, endDate, hideFailed, pageLimit], resetAccountingPage)
watch([taxUsnPercent, taxOsnoPercent, acquiringPercent], queuePercentSettingsSave)
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
  <section class="page-section">
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
        Налог УСН, %
        <input v-model.number="taxUsnPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        Налог ОСНО, %
        <input v-model.number="taxOsnoPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        Эквайринг, %
        <input v-model.number="acquiringPercent" min="0" step="0.1" type="number" />
      </label>
      <span class="muted accounting-autosave-status">
        {{ isPercentSaving ? 'Сохраняем проценты...' : 'Проценты сохраняются автоматически' }}
      </span>
    </div>

    <template v-if="activeAccountingTab === 'clients'">
      <form class="inline-search wide-search contract-accounting-search" @submit.prevent="loadData">
        <input v-model="query" placeholder="Клиент или агент" />
        <DateInput v-model="startDate" aria-label="Дата начала" />
        <DateInput v-model="endDate" aria-label="Дата окончания" />
        <button class="secondary-button" type="submit">Обновить</button>
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
            {{ formatMoney(totals.modulesCost + totals.fixedExpenses + totals.customExpenses + totals.tax + totals.acquiring) }}
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

      <p class="form-hint">Снятые финансовые колонки исключаются из расчёта расходов и чистой прибыли.</p>

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
              <th v-if="isColumnVisible('client')">Договор / клиент</th>
              <th v-if="isColumnVisible('certificate')">Сертификат</th>
              <th v-if="isColumnVisible('modules_cost')">Стоимость комплектующих</th>
              <th v-for="column in expenseColumns.filter((item) => isColumnVisible(item.key))" :key="column.key">
                {{ column.label }}
              </th>
              <th
                v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))"
                :key="getFieldId(field)"
              >
                {{ getFieldName(field) }}
              </th>
              <th v-if="isColumnVisible('tax')">Налог</th>
              <th v-if="isColumnVisible('acquiring')">Эквайринг</th>
              <th v-if="isColumnVisible('profit')">Прибыль</th>
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
                  <span class="muted">{{ getTaxationSystem(row.client) }}</span>
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
              <td
                v-if="isColumnVisible('tax')"
                class="table-money"
                :title="`${getTaxationSystem(row.client)} · ${row.taxPercent}%`"
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
    />
  </section>
</template>
