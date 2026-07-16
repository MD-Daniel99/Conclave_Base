<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
  query: string
  startDate: string
  endDate: string
  taxPercent: number
  acquiringPercent: number
  isPercentSaving: boolean
}>()

const emit = defineEmits<{
  (event: 'update:tax-percent', value: number): void
  (event: 'update:acquiring-percent', value: number): void
  (event: 'custom-fields-changed'): void
}>()

type ExpenseKey =
  | 'prosthetist_work'
  | 'patient_travel'
  | 'patient_accommodation'
  | 'patient_payment'
  | 'other_expenses'
  | 'agency_expenses'

type EditableContractRow = Record<ExpenseKey, string> & { custom: Record<string, string> }

const expenseColumns: Array<{ key: ExpenseKey; label: string }> = [
  { key: 'prosthetist_work', label: 'Работа протезиста' },
  { key: 'patient_travel', label: 'Проезд пациента' },
  { key: 'patient_accommodation', label: 'Проживание пациента' },
  { key: 'patient_payment', label: 'Пациенту' },
  { key: 'other_expenses', label: 'Прочее' },
  { key: 'agency_expenses', label: 'Агентские' },
]

const baseColumns = [
  { key: 'document', label: 'Договор / клиент' },
  { key: 'date', label: 'Дата договора' },
  { key: 'certificate', label: 'Серт.' },
  { key: 'modules_cost', label: 'Модули' },
  ...expenseColumns,
  { key: 'tax', label: 'Налог' },
  { key: 'acquiring', label: 'Эквайринг' },
  { key: 'profit', label: 'Прибыль' },
]

const reportRows = ref<ContractAccountingRow[]>([])
const customFields = ref<AccountingReportField[]>([])
const editable = reactive<Record<string, EditableContractRow>>({})
const hideFailed = ref(true)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>(baseColumns.map((column) => column.key))
const knownColumnKeys = ref<string[]>(baseColumns.map((column) => column.key))
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const success = ref('')

const taxModel = computed({
  get: () => props.taxPercent,
  set: (value: number) => emit('update:tax-percent', Number(value) || 0),
})
const acquiringModel = computed({
  get: () => props.acquiringPercent,
  set: (value: number) => emit('update:acquiring-percent', Number(value) || 0),
})
const availableColumns = computed(() => [
  ...baseColumns,
  ...customFields.value.map((field) => ({ key: customColumnKey(field), label: field.label })),
])

function ensureRow(row: ContractAccountingRow) {
  const id = row.document.document_id
  if (!editable[id]) {
    editable[id] = {
      prosthetist_work: String(row.amounts.prosthetist_work ?? 0),
      patient_travel: String(row.amounts.patient_travel ?? 0),
      patient_accommodation: String(row.amounts.patient_accommodation ?? 0),
      patient_payment: String(row.amounts.patient_payment ?? 0),
      other_expenses: String(row.amounts.other_expenses ?? 0),
      agency_expenses: String(row.amounts.agency_expenses ?? 0),
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
function customColumnKey(field: AccountingReportField) {
  return `custom:${field.key}`
}
function isColumnVisible(key: string) {
  return selectedColumnKeys.value.includes(key)
}
function toggleColumn(key: string) {
  selectedColumnKeys.value = isColumnVisible(key)
    ? selectedColumnKeys.value.filter((item) => item !== key)
    : [...selectedColumnKeys.value, key]
}
function syncSelectedColumns() {
  const keys = availableColumns.value.map((column) => column.key)
  const available = new Set(keys)
  const newKeys = keys.filter((key) => !knownColumnKeys.value.includes(key))
  selectedColumnKeys.value = [
    ...selectedColumnKeys.value.filter((key) => available.has(key)),
    ...newKeys,
  ]
  knownColumnKeys.value = keys
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
function contractDate(row: ContractAccountingRow) {
  return String(row.document.date ?? row.document.created_at ?? '').slice(0, 10)
}
function formatDate(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('ru-RU').format(date)
}
function isFailedRow(row: ContractAccountingRow) {
  const text = `${row.client.status ?? ''} ${row.client.current_stage ?? ''}`.toLowerCase()
  return ['fail', 'hold', 'cancel', 'отказ', 'отлож', 'отмен'].some((token) => text.includes(token))
}

const rows = computed(() => {
  const normalized = props.query.trim().toLowerCase()
  return reportRows.value
    .filter((row) => {
      if (hideFailed.value && isFailedRow(row)) return false
      const date = contractDate(row)
      if ((props.startDate || props.endDate) && !date) return false
      if (props.startDate && date < props.startDate) return false
      if (props.endDate && date > props.endDate) return false
      if (!normalized) return true
      return `${row.document.filename} ${row.document.document_number ?? ''} ${row.client.full_name}`
        .toLowerCase()
        .includes(normalized)
    })
    .map((row) => {
      const values = ensureRow(row)
      const certificate = isColumnVisible('certificate') ? row.amounts.certificate : 0
      const modulesCost = isColumnVisible('modules_cost') ? row.amounts.modules_cost : 0
      const fixedExpenses = expenseColumns.reduce(
        (sum, column) => sum + (isColumnVisible(column.key) ? parseMoney(values[column.key]) : 0),
        0,
      )
      const customExpenses = customFields.value.reduce(
        (sum, field) => sum + (
          isNumericField(field) && isColumnVisible(customColumnKey(field))
            ? parseMoney(values.custom[field.key])
            : 0
        ),
        0,
      )
      const tax = isColumnVisible('tax') ? certificate * (props.taxPercent / 100) : 0
      const acquiring = isColumnVisible('acquiring') ? certificate * (props.acquiringPercent / 100) : 0
      const profit = certificate - modulesCost - fixedExpenses - customExpenses - tax - acquiring
      return { row, certificate, modulesCost, fixedExpenses, customExpenses, tax, acquiring, profit }
    })
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageLimit.value
  return rows.value.slice(start, start + pageLimit.value)
})
const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => currentPage.value * pageLimit.value < rows.value.length)
const visibleRangeStart = computed(() => rows.value.length === 0 ? 0 : (currentPage.value - 1) * pageLimit.value + 1)
const visibleRangeEnd = computed(() => Math.min(currentPage.value * pageLimit.value, rows.value.length))
const visibleColumnCount = computed(() => (
  baseColumns.filter((column) => isColumnVisible(column.key)).length
  + customFields.value.filter((field) => isColumnVisible(customColumnKey(field))).length
  + 1
))
const totals = computed(() => rows.value.reduce((acc, item) => {
  acc.certificate += item.certificate
  acc.modulesCost += item.modulesCost
  acc.fixedExpenses += item.fixedExpenses
  acc.customExpenses += item.customExpenses
  acc.tax += item.tax
  acc.acquiring += item.acquiring
  acc.profit += item.profit
  return acc
}, {
  certificate: 0,
  modulesCost: 0,
  fixedExpenses: 0,
  customExpenses: 0,
  tax: 0,
  acquiring: 0,
  profit: 0,
}))
const totalExpenses = computed(() => (
  totals.value.modulesCost
  + totals.value.fixedExpenses
  + totals.value.customExpenses
  + totals.value.tax
  + totals.value.acquiring
))

function resetPage() {
  currentPage.value = 1
}

async function loadData() {
  isLoading.value = true
  error.value = ''
  try {
    const report = await fetchContractAccountingReport({
      hide_failed: false,
      tax_percent: props.taxPercent,
      acquiring_percent: props.acquiringPercent,
    })
    reportRows.value = report.rows
    customFields.value = report.custom_fields
    syncSelectedColumns()
    Object.keys(editable).forEach((key) => delete editable[key])
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
    await updateContractAccounting(row.document.document_id, {
      ...Object.fromEntries(expenseColumns.map((column) => [column.key, parseMoney(values[column.key])])),
      custom_values: Object.fromEntries(customFields.value.map((field) => [
        field.key,
        isNumericField(field) ? parseMoney(values.custom[field.key]) : (values.custom[field.key] ?? ''),
      ])),
    })
    success.value = 'Значения сохранены'
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
    error.value = 'Введите название нового поля.'
    return
  }
  if (customFields.value.some((field) => field.label.toLowerCase() === name.toLowerCase())) {
    error.value = 'Поле с таким названием уже есть.'
    return
  }
  isSaving.value = true
  error.value = ''
  try {
    await createAccountingCustomField({ field_name: name, field_type: newFieldType.value })
    newFieldName.value = ''
    success.value = 'Поле добавлено'
    await loadData()
    emit('custom-fields-changed')
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function removeField(field: AccountingReportField) {
  if (!window.confirm(`Удалить поле «${field.label}» из обеих бухгалтерий?`)) return
  isSaving.value = true
  error.value = ''
  try {
    await deleteAccountingCustomField(field.key)
    success.value = 'Поле удалено'
    await loadData()
    emit('custom-fields-changed')
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

watch(
  [() => props.query, () => props.startDate, () => props.endDate, hideFailed, pageLimit],
  resetPage,
)
onMounted(loadData)
defineExpose({ loadData })
</script>

<template>
  <div class="accounting-tab-content">
    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>

    <div class="metric-grid">
      <div class="metric-card">
        <span>Сумма сертификатов</span>
        <strong>{{ formatMoney(totals.certificate) }}</strong>
      </div>
      <div class="metric-card">
        <span>Расходы</span>
        <strong>{{ formatMoney(totalExpenses) }}</strong>
      </div>
      <div class="metric-card">
        <span>Чистая прибыль</span>
        <strong>{{ formatMoney(totals.profit) }}</strong>
      </div>
    </div>

    <div class="toolbar-form accounting-toolbar">
      <label>
        Налог, %
        <input v-model.number="taxModel" min="0" step="0.1" type="number" />
      </label>
      <label>
        Эквайринг, %
        <input v-model.number="acquiringModel" min="0" step="0.1" type="number" />
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
      <button class="secondary-button" :disabled="isSaving || !newFieldName.trim()" type="button" @click="addField">
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

    <div class="field-chip-row" aria-label="Настройка колонок договорной бухгалтерии">
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
        :key="field.key"
        class="field-chip"
        :disabled="isSaving"
        type="button"
        @click="removeField(field)"
      >
        {{ field.label }} · {{ isNumericField(field) ? 'число' : 'текст' }} ×
      </button>
    </div>

    <p v-if="isLoading" class="muted">Загружаем бухгалтерию...</p>

    <div v-else class="table-wrap accounting-table">
      <table>
        <thead>
          <tr>
            <th v-if="isColumnVisible('document')">Договор / клиент</th>
            <th v-if="isColumnVisible('date')">Дата договора</th>
            <th v-if="isColumnVisible('certificate')">Серт.</th>
            <th v-if="isColumnVisible('modules_cost')">Модули</th>
            <th v-for="column in expenseColumns.filter((item) => isColumnVisible(item.key))" :key="column.key">
              {{ column.label }}
            </th>
            <th v-for="field in customFields.filter((item) => isColumnVisible(customColumnKey(item)))" :key="field.key">
              {{ field.label }}
            </th>
            <th v-if="isColumnVisible('tax')">Налог</th>
            <th v-if="isColumnVisible('acquiring')">Эквайринг</th>
            <th v-if="isColumnVisible('profit')">Прибыль</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedRows" :key="item.row.document.document_id">
            <td v-if="isColumnVisible('document')">
              <strong>{{ item.row.document.filename }}</strong>
              <span class="muted">{{ item.row.client.short_name }}</span>
            </td>
            <td v-if="isColumnVisible('date')">{{ formatDate(contractDate(item.row)) }}</td>
            <td v-if="isColumnVisible('certificate')">{{ formatMoney(item.certificate) }}</td>
            <td v-if="isColumnVisible('modules_cost')">{{ formatMoney(item.modulesCost) }}</td>
            <td v-for="column in expenseColumns.filter((entry) => isColumnVisible(entry.key))" :key="column.key">
              <input
                class="table-input"
                :value="getExpense(item.row, column.key)"
                inputmode="decimal"
                @input="setExpense(item.row, column.key, ($event.target as HTMLInputElement).value)"
                @blur="formatExpense(item.row, column.key)"
              />
            </td>
            <td v-for="field in customFields.filter((entry) => isColumnVisible(customColumnKey(entry)))" :key="field.key">
              <input
                class="table-input"
                :value="getCustom(item.row, field)"
                :inputmode="isNumericField(field) ? 'decimal' : 'text'"
                @input="setCustom(item.row, field, ($event.target as HTMLInputElement).value)"
                @blur="formatCustom(item.row, field)"
              />
            </td>
            <td v-if="isColumnVisible('tax')">{{ formatMoney(item.tax) }}</td>
            <td v-if="isColumnVisible('acquiring')">{{ formatMoney(item.acquiring) }}</td>
            <td v-if="isColumnVisible('profit')" :class="{ profitNegative: item.profit < 0 }">
              <strong>{{ formatMoney(item.profit) }}</strong>
            </td>
            <td class="accounting-actions-cell">
              <button class="ghost-button" :disabled="isSaving" type="button" @click="saveRow(item.row)">
                Сохранить
              </button>
            </td>
          </tr>
          <tr v-if="rows.length === 0">
            <td :colspan="visibleColumnCount">Нет данных для отчета.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination-bar" aria-label="Пагинация договорной бухгалтерии">
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
</template>
