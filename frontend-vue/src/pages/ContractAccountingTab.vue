<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DateInput from '@/shared/ui/DateInput.vue'
import { formatMoney, formatMoneyInput, parseMoney } from '@/shared/lib/money'
import {
  createAccountingCustomField,
  deleteAccountingCustomField,
  fetchContractAccountingReport,
  updateContractAccounting,
} from '@/shared/api/accounting'
import { getApiErrorMessage } from '@/shared/api/http'
import type { AccountingReportField, ContractAccountingRow } from '@/shared/types/entities'

const props = defineProps<{
  taxUsnPercent: number
  taxOsnoPercent: number
  acquiringPercent: number
}>()
const router = useRouter()

type ExpenseKey =
  | 'prosthetist_work'
  | 'patient_travel'
  | 'patient_accommodation'
  | 'patient_meals'
  | 'patient_payment'
  | 'other_expenses'
  | 'agency_expenses'

type EditableContractRow = Record<ExpenseKey, string> & {
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

const reportRows = ref<ContractAccountingRow[]>([])
const customFields = ref<AccountingReportField[]>([])
const editable = reactive<Record<string, EditableContractRow>>({})
const query = ref('')
const startDate = ref('')
const endDate = ref('')
const hideFailed = ref(true)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>([])
const knownColumnKeys = ref<string[]>([])
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const success = ref('')

const availableColumns = computed(() => [
  ...leadingColumns,
  ...expenseColumns,
  ...customFields.value.map((field) => ({
    key: getCustomColumnKey(field),
    label: field.label,
  })),
  ...trailingColumns,
])

function getDocumentId(row: ContractAccountingRow) {
  return row.document.document_id
}

function openClientCard(row: ContractAccountingRow) {
  if (row.client.client_id) {
    void router.push({ name: 'clients', query: { client_id: row.client.client_id } })
  }
}

function ensureRow(row: ContractAccountingRow) {
  const id = getDocumentId(row)

  if (!editable[id]) {
    editable[id] = {
      prosthetist_work: formatMoneyInput(row.amounts.prosthetist_work ?? 0),
      patient_travel: formatMoneyInput(row.amounts.patient_travel ?? 0),
      patient_accommodation: formatMoneyInput(row.amounts.patient_accommodation ?? 0),
      patient_meals: formatMoneyInput(row.amounts.patient_meals ?? 0),
      patient_payment: formatMoneyInput(row.amounts.patient_payment ?? 0),
      other_expenses: formatMoneyInput(row.amounts.other_expenses ?? 0),
      agency_expenses: formatMoneyInput(row.amounts.agency_expenses ?? 0),
      custom: Object.fromEntries(
        Object.entries(row.custom_values ?? {}).map(([key, value]) => [key, String(value ?? '')]),
      ),
    }
  }

  return editable[id]
}

function isNumericField(field: AccountingReportField) {
  return field.type === 'number'
}

function getExpense(row: ContractAccountingRow, key: ExpenseKey) {
  return ensureRow(row)[key]
}

function setExpense(row: ContractAccountingRow, key: ExpenseKey, value: string) {
  ensureRow(row)[key] = value
}

function formatExpense(row: ContractAccountingRow, key: ExpenseKey) {
  setExpense(row, key, formatMoneyInput(getExpense(row, key)))
}

function getCustom(row: ContractAccountingRow, field: AccountingReportField) {
  return ensureRow(row).custom[field.key] ?? ''
}

function setCustom(row: ContractAccountingRow, field: AccountingReportField, value: string) {
  ensureRow(row).custom[field.key] = value
}

function formatCustom(row: ContractAccountingRow, field: AccountingReportField) {
  if (isNumericField(field)) {
    setCustom(row, field, formatMoneyInput(getCustom(row, field)))
  }
}

function getCustomColumnKey(field: AccountingReportField) {
  return `custom:${field.key}`
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

function syncSelectedColumns() {
  const availableKeys = availableColumns.value.map((column) => column.key)
  const available = new Set(availableKeys)

  if (knownColumnKeys.value.length === 0) {
    selectedColumnKeys.value = availableKeys
    knownColumnKeys.value = availableKeys
    return
  }

  const newKeys = availableKeys.filter((key) => !knownColumnKeys.value.includes(key))
  selectedColumnKeys.value = [
    ...selectedColumnKeys.value.filter((key) => available.has(key)),
    ...newKeys,
  ]
  knownColumnKeys.value = availableKeys
}

function getTaxationSystem(row: ContractAccountingRow): 'УСН' | 'ОСНО' {
  return row.client.taxation_system === 'ОСНО' ? 'ОСНО' : 'УСН'
}

function getTaxPercent(row: ContractAccountingRow) {
  return getTaxationSystem(row) === 'ОСНО' ? props.taxOsnoPercent : props.taxUsnPercent
}

function isFailedRow(row: ContractAccountingRow) {
  const text = `${row.client.status ?? ''} ${row.client.current_stage ?? ''}`.toLowerCase()
  return ['fail', 'hold', 'cancel', 'отказ', 'отлож', 'отмен'].some((token) => text.includes(token))
}

function getDocumentDate(row: ContractAccountingRow) {
  return String(row.document.date ?? row.document.created_at ?? '').slice(0, 10)
}

function getDocumentSortKey(row: ContractAccountingRow) {
  return [
    row.document.created_at ?? '',
    getDocumentDate(row),
    row.document.document_id,
  ].join('|')
}

const calculatedRows = computed(() => {
  const groupedRows = new Map<string, ContractAccountingRow[]>()

  reportRows.value.forEach((row) => {
    const group = groupedRows.get(row.client.client_id) ?? []
    group.push(row)
    groupedRows.set(row.client.client_id, group)
  })

  const calculated: Array<{
    row: ContractAccountingRow
    certificate: number
    modulesCost: number
    fixedExpenses: number
    customExpenses: number
    tax: number
    taxPercent: number
    acquiring: number
    profit: number
    appliesPercentageExpenses: boolean
  }> = []

  groupedRows.forEach((clientRows) => {
    const chronologicalRows = [...clientRows].sort((left, right) => {
      const leftIndex = left.amounts.contract_index
      const rightIndex = right.amounts.contract_index
      if (typeof leftIndex === 'number' && typeof rightIndex === 'number') {
        return leftIndex - rightIndex
      }
      return getDocumentSortKey(left).localeCompare(getDocumentSortKey(right))
    })
    const certificateOriginal = isColumnVisible('certificate')
      ? parseMoney(
        chronologicalRows[0]?.amounts.certificate_original
          ?? chronologicalRows[0]?.amounts.certificate
          ?? 0,
      )
      : 0
    let certificateBalance = certificateOriginal

    chronologicalRows.forEach((row, index) => {
      const values = ensureRow(row)
      const fixedExpenses = expenseColumns.reduce((sum, column) => (
        sum + (isColumnVisible(column.key) ? parseMoney(values[column.key]) : 0)
      ), 0)
      const customExpenses = customFields.value.reduce((sum, field) => {
        if (!isNumericField(field) || !isColumnVisible(getCustomColumnKey(field))) {
          return sum
        }
        return sum + parseMoney(values.custom[field.key])
      }, 0)
      const modulesCost = isColumnVisible('modules_cost') ? row.amounts.modules_cost : 0
      const taxPercent = getTaxPercent(row)
      const appliesPercentageExpenses = row.amounts.applies_percentage_expenses ?? index === 0
      const tax = isColumnVisible('tax') && appliesPercentageExpenses
        ? certificateOriginal * (taxPercent / 100)
        : 0
      const acquiring = isColumnVisible('acquiring') && appliesPercentageExpenses
        ? certificateOriginal * (props.acquiringPercent / 100)
        : 0
      const certificate = certificateBalance
      const profit = certificate - modulesCost - fixedExpenses - customExpenses - tax - acquiring
      certificateBalance = profit

      calculated.push({
        row,
        certificate,
        modulesCost,
        fixedExpenses,
        customExpenses,
        tax,
        taxPercent,
        acquiring,
        profit,
        appliesPercentageExpenses,
      })
    })
  })

  return calculated.sort((left, right) => (
    getDocumentSortKey(right.row).localeCompare(getDocumentSortKey(left.row))
  ))
})

const rows = computed(() => {
  const normalized = query.value.trim().toLowerCase()

  return calculatedRows.value
    .filter((item) => {
      const row = item.row
      if (hideFailed.value && isFailedRow(row)) {
        return false
      }

      const documentDate = getDocumentDate(row)
      if (startDate.value && documentDate < startDate.value) {
        return false
      }
      if (endDate.value && documentDate > endDate.value) {
        return false
      }

      return !normalized || [
        row.document.filename,
        row.document.document_number ?? '',
        row.client.full_name,
      ].join(' ').toLowerCase().includes(normalized)
    })
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

const totals = computed(() => {
  const byClient = new Map<string, typeof rows.value>()

  rows.value.forEach((item) => {
    const group = byClient.get(item.row.client.client_id) ?? []
    group.push(item)
    byClient.set(item.row.client.client_id, group)
  })

  return [...byClient.values()].reduce((totalsAcc, clientRows) => {
    const chronologicalRows = [...clientRows].sort((left, right) => {
      const leftIndex = left.row.amounts.contract_index
      const rightIndex = right.row.amounts.contract_index
      if (typeof leftIndex === 'number' && typeof rightIndex === 'number') {
        return leftIndex - rightIndex
      }
      return getDocumentSortKey(left.row).localeCompare(getDocumentSortKey(right.row))
    })
    totalsAcc.certificate += chronologicalRows[0]?.certificate ?? 0
    totalsAcc.expenses += chronologicalRows.reduce((sum, item) => (
      sum + item.modulesCost + item.fixedExpenses + item.customExpenses + item.tax + item.acquiring
    ), 0)
    totalsAcc.profit += chronologicalRows[chronologicalRows.length - 1]?.profit ?? 0
    return totalsAcc
  }, { certificate: 0, expenses: 0, profit: 0 })
})

function resetPage() {
  currentPage.value = 1
}

function visibleColumnCount() {
  return availableColumns.value.filter((column) => isColumnVisible(column.key)).length + 1
}

async function loadData() {
  isLoading.value = true
  error.value = ''

  try {
    const report = await fetchContractAccountingReport({
      hide_failed: false,
      tax_usn_percent: props.taxUsnPercent,
      tax_osno_percent: props.taxOsnoPercent,
      acquiring_percent: props.acquiringPercent,
    })
    reportRows.value = report.rows
    customFields.value = report.custom_fields
    Object.keys(editable).forEach((key) => delete editable[key])
    syncSelectedColumns()
    resetPage()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isLoading.value = false
  }
}

async function saveRow(row: ContractAccountingRow) {
  isSaving.value = true
  error.value = ''
  success.value = ''
  const values = ensureRow(row)

  try {
    await updateContractAccounting(getDocumentId(row), {
      ...Object.fromEntries(
        expenseColumns.map((column) => [column.key, parseMoney(values[column.key])]),
      ),
      custom_values: Object.fromEntries(
        customFields.value.map((field) => [
          field.key,
          isNumericField(field)
            ? parseMoney(values.custom[field.key])
            : (values.custom[field.key] ?? ''),
        ]),
      ),
    })
    success.value = 'Расходы по договору сохранены'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function addField() {
  const name = newFieldName.value.trim()
  if (!name) {
    return
  }

  isSaving.value = true
  error.value = ''

  try {
    await createAccountingCustomField({ field_name: name, field_type: newFieldType.value })
    newFieldName.value = ''
    success.value = 'Поле добавлено'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function removeField(field: AccountingReportField) {
  if (!window.confirm(`Удалить поле «${field.label}» из обеих бухгалтерий?`)) {
    return
  }

  isSaving.value = true
  error.value = ''

  try {
    await deleteAccountingCustomField(field.key)
    success.value = 'Поле удалено'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

watch([query, startDate, endDate, hideFailed, pageLimit], resetPage)
onMounted(loadData)
</script>

<template>
  <div class="accounting-tab-content">
    <form class="inline-search wide-search contract-accounting-search" @submit.prevent="loadData">
      <input v-model="query" placeholder="Договор или клиент" />
      <DateInput v-model="startDate" aria-label="Дата начала" />
      <DateInput v-model="endDate" aria-label="Дата окончания" />
      <button class="secondary-button" type="submit">Обновить</button>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>

    <div class="metric-grid">
      <div class="metric-card">
        <span>Сумма сертификатов</span>
        <strong>{{ formatMoney(totals.certificate) }}</strong>
      </div>
      <div class="metric-card">
        <span>Расходы</span>
        <strong>{{ formatMoney(totals.expenses) }}</strong>
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
      <button class="secondary-button" :disabled="isSaving || !newFieldName.trim()" type="button" @click="addField">
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

    <p class="form-hint">
      Для нескольких договоров одного клиента сертификат учитывается один раз. Каждый следующий договор показывает остаток
      после расходов по предыдущим договорам; налог и эквайринг начисляются только в первом договоре.
      Снятые финансовые колонки исключаются из расчёта.
    </p>

    <div class="field-chip-row" aria-label="Настройка колонок бухгалтерии по договорам">
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

    <div v-if="customFields.length" class="field-chip-row">
      <button
        v-for="field in customFields"
        :key="field.key"
        class="field-chip"
        :disabled="isSaving"
        type="button"
        @click="removeField(field)"
      >
        {{ field.label }} · {{ field.type === 'number' ? 'число' : 'текст' }} ×
      </button>
    </div>

    <p v-if="isLoading" class="muted">Загружаем договорную бухгалтерию...</p>

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
              :key="field.key"
            >
              {{ field.label }}
            </th>
            <th v-if="isColumnVisible('tax')">Налог</th>
            <th v-if="isColumnVisible('acquiring')">Эквайринг</th>
            <th v-if="isColumnVisible('profit')">Прибыль</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedRows" :key="getDocumentId(item.row)">
            <td v-if="isColumnVisible('client')" class="accounting-identity-cell">
              <button class="link-button accounting-client-link" type="button" @click="openClientCard(item.row)">
                <strong>{{ item.row.document.filename }}</strong>
                <span class="muted">{{ item.row.client.short_name }} · {{ getTaxationSystem(item.row) }}</span>
                <span v-if="item.row.amounts.contract_count && item.row.amounts.contract_count > 1" class="muted">
                  Договор {{ item.row.amounts.contract_index }} из {{ item.row.amounts.contract_count }}
                </span>
              </button>
            </td>
            <td
              v-if="isColumnVisible('certificate')"
              class="table-money"
              :title="item.row.amounts.contract_index && item.row.amounts.contract_index > 1
                ? 'Остаток сертификата перед расходами по этому договору'
                : 'Полная стоимость сертификата'"
            >
              {{ formatMoney(item.certificate) }}
            </td>
            <td v-if="isColumnVisible('modules_cost')" class="table-money">{{ formatMoney(item.modulesCost) }}</td>
            <td v-for="column in expenseColumns.filter((entry) => isColumnVisible(entry.key))" :key="column.key">
              <input
                class="table-input"
                :value="getExpense(item.row, column.key)"
                inputmode="decimal"
                @input="setExpense(item.row, column.key, ($event.target as HTMLInputElement).value)"
                @blur="formatExpense(item.row, column.key)"
              />
            </td>
            <td
              v-for="field in customFields.filter((entry) => isColumnVisible(getCustomColumnKey(entry)))"
              :key="field.key"
            >
              <input
                class="table-input"
                :value="getCustom(item.row, field)"
                :inputmode="isNumericField(field) ? 'decimal' : 'text'"
                @input="setCustom(item.row, field, ($event.target as HTMLInputElement).value)"
                @blur="formatCustom(item.row, field)"
              />
            </td>
            <td
              v-if="isColumnVisible('tax')"
              class="table-money"
              :title="item.appliesPercentageExpenses
                ? `${getTaxationSystem(item.row)} · ${item.taxPercent}%`
                : 'Налог уже учтён в первом договоре этого клиента'"
            >
              {{ formatMoney(item.tax) }}
            </td>
            <td v-if="isColumnVisible('acquiring')" class="table-money">{{ formatMoney(item.acquiring) }}</td>
            <td
              v-if="isColumnVisible('profit')"
              class="table-money"
              :class="{ profitNegative: item.profit < 0 }"
            >
              <strong>{{ formatMoney(item.profit) }}</strong>
            </td>
            <td>
              <button class="ghost-button" :disabled="isSaving" type="button" @click="saveRow(item.row)">
                Сохранить
              </button>
            </td>
          </tr>
          <tr v-if="rows.length === 0">
            <td :colspan="visibleColumnCount()">Сгенерированные договоры с метаданными не найдены.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination-bar" aria-label="Пагинация бухгалтерии по договорам">
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
  </div>
</template>
