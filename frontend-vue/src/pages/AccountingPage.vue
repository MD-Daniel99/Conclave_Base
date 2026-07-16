<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
import type { AccountingCustomField, Client, ClientContractCoverage } from '@/shared/types/entities'

type ClientExpenseKey =
  | 'prosthetist_work'
  | 'patient_travel'
  | 'patient_accommodation'
  | 'patient_payment'
  | 'other_expenses'
  | 'agency_expenses'

type EditableRow = Record<ClientExpenseKey, string> & {
  custom: Record<string, string>
}

const clientExpenseColumns: Array<{ key: ClientExpenseKey; label: string }> = [
  { key: 'prosthetist_work', label: 'Работа протезиста' },
  { key: 'patient_travel', label: 'Проезд пациента' },
  { key: 'patient_accommodation', label: 'Проживание пациента' },
  { key: 'patient_payment', label: 'Пациенту' },
  { key: 'other_expenses', label: 'Прочее' },
  { key: 'agency_expenses', label: 'Агентские' },
]

const authStore = useAuthStore()
const activeAccountingTab = ref<'clients' | 'contracts'>('clients')
const contractAccountingTab = ref<{ loadData: () => Promise<void> } | null>(null)
const clients = ref<Client[]>([])
const customFields = ref<AccountingCustomField[]>([])
const contractCoverageByClient = ref<Record<string, ClientContractCoverage>>({})
const query = ref('')
const startDate = ref('')
const endDate = ref('')
const hideFailed = ref(true)
const taxPercent = ref(6)
const acquiringPercent = ref(1)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>([
  'client',
  'contract_date',
  'revenue',
  'modules_cost',
  ...clientExpenseColumns.map((column) => column.key),
  'tax',
  'acquiring',
  'profit',
])
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

const baseColumns = [
  { key: 'client', label: 'Клиент' },
  { key: 'contract_date', label: 'Дата договора' },
  { key: 'revenue', label: 'Серт.' },
  { key: 'modules_cost', label: 'Модули' },
  ...clientExpenseColumns,
  { key: 'tax', label: 'Налог' },
  { key: 'acquiring', label: 'Эквайринг' },
  { key: 'profit', label: 'Прибыль' },
]

const availableColumns = computed(() => [
  ...baseColumns,
  ...customFields.value.map((field) => ({ key: getCustomColumnKey(field), label: getFieldName(field) })),
])

const filteredClients = computed(() => {
  const normalizedQuery = query.value.trim().toLowerCase()

  return clients.value.filter((client) => {
    if (hideFailed.value && isFailedClient(client)) {
      return false
    }

    const date = getClientContractDate(client)

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
    const rawRevenue = parseMoney(client.certificate_price)
    const rawModulesCost = getModulesCost(client)
    const editable = ensureEditableRow(client)
    const customTotal = numericCustomFields.value.reduce((sum, field) => {
      if (!isColumnVisible(getCustomColumnKey(field))) {
        return sum
      }

      return sum + parseMoney(getCustomEditableValue(client, field))
    }, 0)

    const revenue = isColumnVisible('revenue') ? rawRevenue : 0
    const modulesCost = isColumnVisible('modules_cost') ? rawModulesCost : 0
    const fixedExpenses = clientExpenseColumns.reduce(
      (sum, column) => sum + (isColumnVisible(column.key) ? parseMoney(editable[column.key]) : 0),
      0,
    )

    const tax = isColumnVisible('tax') ? revenue * (taxPercent.value / 100) : 0
    const acquiring = isColumnVisible('acquiring') ? revenue * (acquiringPercent.value / 100) : 0
    const hasNoAccountingBasis = rawModulesCost === 0 && !getCheckDate(client)
    const profit = hasNoAccountingBasis
      ? 0
      : revenue - tax - acquiring - modulesCost - fixedExpenses - customTotal

    return {
      client,
      contractCoverage: contractCoverageByClient.value[getClientId(client)],
      revenue,
      modulesCost,
      fixedExpenses,
      customTotal,
      tax,
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
const visibleRangeStart = computed(() => (rows.value.length === 0 ? 0 : (currentPage.value - 1) * pageLimit.value + 1))
const visibleRangeEnd = computed(() => Math.min(currentPage.value * pageLimit.value, rows.value.length))

const totals = computed(() =>
  rows.value.reduce(
    (acc, row) => {
      acc.revenue += row.revenue
      acc.modulesCost += row.modulesCost
      acc.fixedExpenses += row.fixedExpenses
      acc.customTotal += row.customTotal
      acc.tax += row.tax
      acc.acquiring += row.acquiring
      acc.profit += row.profit
      return acc
    },
    {
      revenue: 0,
      modulesCost: 0,
      fixedExpenses: 0,
      customTotal: 0,
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

function getClientContractDate(client: Client) {
  return contractCoverageByClient.value[getClientId(client)]?.latest_contract_date ?? ''
}

function isFailedClient(client: Client) {
  const status = String(client.status_code ?? '').toLowerCase()
  const stage = String(client.current_stage ?? '').toLowerCase()
  const text = `${status} ${stage}`
  return ['fail', 'hold', 'cancel', 'отказ', 'отлож', 'отмен'].some((token) => text.includes(token))
}

function formatDate(value: string) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ru-RU').format(date)
}

function getModulesCost(client: Client) {
  return (client.modules ?? []).reduce((sum, moduleItem) => sum + parseMoney(moduleItem.cost), 0)
}

function getContractCoverageMessage(coverage?: ClientContractCoverage) {
  if (!coverage?.requires_contract) {
    return ''
  }
  if (coverage.uncovered_module_names.length > 0) {
    return `Не включены в договор: ${coverage.uncovered_module_names.join(', ')}`
  }
  return 'У клиента нет сформированного договора.'
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
  const customVisibleCount = customFields.value.filter((field) => isColumnVisible(getCustomColumnKey(field))).length
  const baseVisibleCount = baseColumns.filter((column) => isColumnVisible(column.key)).length
  return baseVisibleCount + customVisibleCount + 1
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
      prosthetist_work: String(client.prosthetist_work ?? 0),
      patient_travel: String(client.patient_travel ?? 0),
      patient_accommodation: String(client.patient_accommodation ?? 0),
      patient_payment: String(client.patient_payment ?? 0),
      other_expenses: String(client.other_expenses ?? 0),
      agency_expenses: String(client.agency_expenses ?? 0),
      custom: {},
    }
  }

  return editableRows[clientId]
}

function getExpenseEditableValue(client: Client, key: ClientExpenseKey) {
  return ensureEditableRow(client)[key]
}

function setExpenseEditableValue(client: Client, key: ClientExpenseKey, value: string) {
  ensureEditableRow(client)[key] = value
}

function formatExpenseEditableValue(client: Client, key: ClientExpenseKey) {
  setExpenseEditableValue(client, key, formatMoneyInput(getExpenseEditableValue(client, key)))
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
  const fieldId = getFieldId(field)
  ensureEditableRow(client).custom[fieldId] = value
}

function formatCustomEditableValue(client: Client, field: AccountingCustomField) {
  if (getFieldType(field) !== 'number') {
    return
  }

  setCustomEditableValue(client, field, formatMoneyInput(getCustomEditableValue(client, field)))
}

async function loadSettings() {
  const userId = authStore.user?.user_id

  if (!userId) {
    isSettingsReady.value = true
    return
  }

  try {
    const settings = await fetchUserSettings(userId)

    if (typeof settings.tax_percent === 'number') {
      taxPercent.value = settings.tax_percent
    }

    if (typeof settings.acq_percent === 'number') {
      acquiringPercent.value = settings.acq_percent
    }
  } catch {
    // настройки не должны блокировать бухгалтерию
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
      tax_percent: taxPercent.value,
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
    contractCoverageByClient.value = Object.fromEntries(
      coverageResponse.map((item) => [item.client_id, item]),
    )
    syncSelectedColumns()

    Object.keys(editableRows).forEach((key) => delete editableRows[key])
    resetAccountingPage()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

async function refreshActiveAccounting() {
  if (activeAccountingTab.value === 'clients') {
    await loadData()
  } else {
    await contractAccountingTab.value?.loadData()
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
    await updateClient(clientId, {
      ...Object.fromEntries(
        clientExpenseColumns.map((column) => [column.key, parseMoney(row[column.key])]),
      ),
    })

    const values = customFields.value
      .map((field) => {
        const fieldId = getFieldId(field)
        const rawValue = row.custom[fieldId] ?? ''
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

  if (!fieldId || !window.confirm(`Удалить поле "${getFieldName(field)}"?`)) {
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
watch([taxPercent, acquiringPercent], queuePercentSettingsSave)

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
      <form class="inline-search wide-search" @submit.prevent="refreshActiveAccounting">
        <input v-model="query" :placeholder="activeAccountingTab === 'clients' ? 'Поиск клиента или агента' : 'Поиск договора или клиента'" />
        <DateInput v-model="startDate" aria-label="Дата начала" />
        <DateInput v-model="endDate" aria-label="Дата окончания" />
        <button class="secondary-button" type="submit">Обновить</button>
      </form>
    </div>

    <div class="tabs" role="tablist">
      <button :class="{ active: activeAccountingTab === 'clients' }" type="button" @click="activeAccountingTab = 'clients'">
        По клиентам
      </button>
      <button :class="{ active: activeAccountingTab === 'contracts' }" type="button" @click="activeAccountingTab = 'contracts'">
        По договорам
      </button>
    </div>

    <div v-if="activeAccountingTab === 'clients'" class="accounting-tab-content">
    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

    <div class="metric-grid">
      <div class="metric-card">
        <span>Сумма сертификатов</span>
        <strong>{{ formatMoney(totals.revenue) }}</strong>
      </div>
      <div class="metric-card">
        <span>Расходы</span>
        <strong>{{ formatMoney(totals.modulesCost + totals.fixedExpenses + totals.customTotal + totals.tax + totals.acquiring) }}</strong>
      </div>
      <div class="metric-card">
        <span>Чистая прибыль</span>
        <strong>{{ formatMoney(totals.profit) }}</strong>
      </div>
    </div>

    <div class="toolbar-form accounting-toolbar">
      <label>
        Налог, %
        <input v-model.number="taxPercent" min="0" step="0.1" type="number" />
      </label>
      <label>
        Эквайринг, %
        <input v-model.number="acquiringPercent" min="0" step="0.1" type="number" />
      </label>
      <label class="checkbox-label">
        <input v-model="hideFailed" type="checkbox" />
        Скрыть отказы и отложенных
      </label>
      <input v-model="newFieldName" placeholder="Новое поле" />
      <select v-model="newFieldType">
        <option value="number">Число / расход</option>
        <option value="text">Текст</option>
      </select>
      <button class="secondary-button" :disabled="isSaving || !newFieldName.trim()" type="button" @click="addCustomField">
        Добавить поле
      </button>
      <span class="muted accounting-autosave-status">
        {{ isPercentSaving ? 'Сохраняем проценты...' : 'Проценты сохраняются автоматически' }}
      </span>
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

    <p class="form-hint">Снятые финансовые колонки исключаются из расчета расходов и чистой прибыли.</p>

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
            <th v-if="isColumnVisible('client')">Клиент</th>
            <th v-if="isColumnVisible('contract_date')">Дата договора</th>
            <th v-if="isColumnVisible('revenue')">Серт.</th>
            <th v-if="isColumnVisible('modules_cost')">Модули</th>
            <th v-for="column in clientExpenseColumns.filter((item) => isColumnVisible(item.key))" :key="column.key">
              {{ column.label }}
            </th>
            <th v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))" :key="getFieldId(field)">
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
            :class="{ 'accounting-contract-required': row.contractCoverage?.requires_contract }"
          >
            <td v-if="isColumnVisible('client')">
              <strong>{{ getClientName(row.client) }}</strong>
              <span
                v-if="row.contractCoverage?.requires_contract"
                class="accounting-contract-warning"
                :title="getContractCoverageMessage(row.contractCoverage)"
              >
                Необходимо сделать договор
              </span>
            </td>
            <td v-if="isColumnVisible('contract_date')">{{ formatDate(getClientContractDate(row.client)) }}</td>
            <td v-if="isColumnVisible('revenue')">{{ formatMoney(row.revenue) }}</td>
            <td v-if="isColumnVisible('modules_cost')">{{ formatMoney(row.modulesCost) }}</td>
            <td v-for="column in clientExpenseColumns.filter((item) => isColumnVisible(item.key))" :key="column.key">
              <input
                class="table-input"
                :value="getExpenseEditableValue(row.client, column.key)"
                inputmode="decimal"
                @input="setExpenseEditableValue(row.client, column.key, ($event.target as HTMLInputElement).value)"
                @blur="formatExpenseEditableValue(row.client, column.key)"
              />
            </td>
            <td v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))" :key="getFieldId(field)">
              <input
                class="table-input"
                :value="getCustomEditableValue(row.client, field)"
                :inputmode="getFieldType(field) === 'number' ? 'decimal' : 'text'"
                @input="setCustomEditableValue(row.client, field, ($event.target as HTMLInputElement).value)"
                @blur="formatCustomEditableValue(row.client, field)"
              />
            </td>
            <td v-if="isColumnVisible('tax')">{{ formatMoney(row.tax) }}</td>
            <td v-if="isColumnVisible('acquiring')">{{ formatMoney(row.acquiring) }}</td>
            <td v-if="isColumnVisible('profit')" :class="{ profitNegative: row.profit < 0 }">
              <strong>{{ formatMoney(row.profit) }}</strong>
            </td>
            <td class="accounting-actions-cell">
              <button class="ghost-button" :disabled="isSaving" type="button" @click="saveClientValues(row.client)">
                Сохранить
              </button>
            </td>
          </tr>
          <tr v-if="rows.length === 0">
            <td :colspan="visibleColumnCount()">Нет данных для отчета.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination-bar" aria-label="Пагинация бухгалтерии">
      <span>Страница {{ currentPage }} · показано {{ pagedRows.length }} из {{ rows.length }} · записи {{ visibleRangeStart }}–{{ visibleRangeEnd }}</span>
      <div class="row-actions">
        <button class="secondary-button" type="button" :disabled="isLoading || !hasPreviousPage" @click="currentPage -= 1">
          Назад
        </button>
        <button class="secondary-button" type="button" :disabled="isLoading || !hasNextPage" @click="currentPage += 1">
          Вперед
        </button>
      </div>
    </div>
    </div>
    <ContractAccountingTab
      v-else
      ref="contractAccountingTab"
      :query="query"
      :start-date="startDate"
      :end-date="endDate"
      :tax-percent="taxPercent"
      :acquiring-percent="acquiringPercent"
      :is-percent-saving="isPercentSaving"
      @update:tax-percent="taxPercent = $event"
      @update:acquiring-percent="acquiringPercent = $event"
      @custom-fields-changed="loadData"
    />
  </section>
</template>
