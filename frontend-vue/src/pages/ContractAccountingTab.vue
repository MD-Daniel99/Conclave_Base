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
  fetchContractExpenseHistory,
  addContractExpense,
  updateContractExpense,
  deleteContractExpense,
  updateContractExpenseStatus,
} from '@/shared/api/accounting'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import { matchesTableFilter, nextSortState, sortTableRows, type SortDirection, type TableFilterKind } from '@/shared/lib/table'
import SortableFilterHeader from '@/shared/ui/SortableFilterHeader.vue'
import type { AccountingReportField, ContractAccountingRow } from '@/shared/types/entities'

const props = defineProps<{
  taxUsnPercent: number
  taxOsnoPercent: number
  acquiringPercent: number
  vatPercent: number
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
  { key: 'vat', label: 'НДС' },
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
const hideFailed = ref(false)
const newFieldName = ref('')
const newFieldType = ref<'number' | 'text'>('number')
const pageLimit = ref(50)
const currentPage = ref(1)
const selectedColumnKeys = ref<string[]>([])
const knownColumnKeys = ref<string[]>([])
const contractColumnFilters = reactive<Record<string, string>>({})
const contractSortKey = ref<string | null>(null)
const contractSortDirection = ref<SortDirection>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const success = ref('')
const confirmAction = useAppConfirm()
useSuccessToast(success, 'Договорная бухгалтерия')

const selectedExpenseRow = ref<ContractAccountingRow | null>(null)
const selectedExpenseFieldKey = ref('')
const selectedExpenseFieldLabel = ref('')
const selectedExpenseHistory = ref<Awaited<ReturnType<typeof fetchContractExpenseHistory>> | null>(null)
const expenseDialogLoading = ref(false)
const expenseAmount = ref('')
const expenseDescription = ref('')
const expensePaid = ref(true)
const editingExpenseId = ref<string | null>(null)
const editExpenseAmount = ref('')
const editExpenseDescription = ref('')
const pendingDeleteExpenseId = ref<string | null>(null)

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

function getCustom(row: ContractAccountingRow, field: AccountingReportField) {
  return ensureRow(row).custom[field.key] ?? ''
}

function setCustom(row: ContractAccountingRow, field: AccountingReportField, value: string) {
  ensureRow(row).custom[field.key] = value
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

function getTaxationSystem(row: ContractAccountingRow) {
  return `УСН ${getTaxPercent(row)}%`
}

function getTaxPercent(row: ContractAccountingRow) {
  return row.client.taxation_system === 'ОСНО' ? props.taxOsnoPercent : props.taxUsnPercent
}

function isFailedRow(row: ContractAccountingRow) {
  const text = `${row.client.status ?? ''} ${row.client.current_stage ?? ''}`.toLocaleLowerCase('ru-RU')
  return ['fail', 'hold', 'cancel', 'отказ', 'отлож', 'отмен'].some((token) => text.includes(token))
}

function getDocumentDate(row: ContractAccountingRow) {
  return String(row.document.certificate_date ?? '').slice(0, 10)
}

function getDocumentSortKey(row: ContractAccountingRow) {
  return [row.document.created_at ?? '', getDocumentDate(row), row.document.document_id].join('|')
}

const calculatedRows = computed(() => reportRows.value.map((row) => {
  const values = ensureRow(row)
  const fixedExpenses = expenseColumns.reduce((sum, column) => {
    const unpaid = column.key === 'prosthetist_work' && row.expense_status?.[column.key] === 'unpaid'
    return sum + (unpaid ? 0 : parseMoney(row.amounts[column.key]))
  }, 0)
  const customExpenses = customFields.value.reduce((sum, field) => (
    isNumericField(field) ? sum + parseMoney(values.custom[field.key]) : sum
  ), 0)
  const certificate = parseMoney(row.amounts.certificate)
  const modulesCost = parseMoney(row.amounts.modules_cost)
  const taxPercent = getTaxPercent(row)
  const vat = certificate * (props.vatPercent / (100 + props.vatPercent))
  const revenueWithoutVat = certificate - vat
  const acquiring = certificate * (props.acquiringPercent / 100)
  const taxBase = Math.max(
    0,
    revenueWithoutVat - modulesCost - fixedExpenses - customExpenses - acquiring,
  )
  const tax = taxBase * (taxPercent / 100)
  const profit = revenueWithoutVat - modulesCost - fixedExpenses - customExpenses - acquiring - tax
  return {
    row,
    certificate,
    modulesCost,
    fixedExpenses,
    customExpenses,
    vat,
    tax,
    acquiring,
    profit,
  }
}))

type CalculatedContractRow = (typeof calculatedRows.value)[number]

function contractColumnValue(item: CalculatedContractRow, key: string): unknown {
  if (key === 'client') return [
    item.row.document.filename,
    item.row.document.document_number,
    item.row.client.full_name,
    item.row.client.short_name,
    getDocumentDate(item.row),
  ].filter(Boolean).join(' ')
  if (key === 'certificate') return item.certificate
  if (key === 'modules_cost') return item.modulesCost
  if (key === 'vat') return item.vat
  if (key === 'tax') return item.tax
  if (key === 'acquiring') return item.acquiring
  if (key === 'profit') return item.profit
  if (key.startsWith('custom:')) {
    const field = customFields.value.find((entry) => getCustomColumnKey(entry) === key)
    return field ? getCustom(item.row, field) : ''
  }
  if (expenseColumns.some((column) => column.key === key)) {
    return parseMoney(getExpense(item.row, key as ExpenseKey))
  }
  return ''
}

function contractFilterKind(key: string): TableFilterKind {
  if (key === 'client') return 'text'
  if (key.startsWith('custom:')) {
    const field = customFields.value.find((entry) => getCustomColumnKey(entry) === key)
    return field && !isNumericField(field) ? 'text' : 'number'
  }
  return 'number'
}

function sortContracts(key: string) {
  const next = nextSortState({ key: contractSortKey.value, direction: contractSortDirection.value }, key)
  contractSortKey.value = next.key
  contractSortDirection.value = next.direction
  currentPage.value = 1
}

const rows = computed(() => {
  const normalized = query.value.trim().toLocaleLowerCase('ru-RU')
  const filtered = calculatedRows.value.filter((item) => {
    const row = item.row
    if (hideFailed.value && isFailedRow(row)) return false
    const certificateDate = getDocumentDate(row)
    if ((startDate.value || endDate.value) && !certificateDate) return false
    if (startDate.value && certificateDate < startDate.value) return false
    if (endDate.value && certificateDate > endDate.value) return false
    const searchable = String(contractColumnValue(item, 'client')).toLocaleLowerCase('ru-RU')
    if (normalized && !searchable.includes(normalized)) return false
    return availableColumns.value.every((column) => matchesTableFilter(
      contractColumnValue(item, column.key),
      contractColumnFilters[column.key] ?? '',
      contractFilterKind(column.key),
    ))
  })
  const defaultSorted = contractSortKey.value
    ? filtered
    : [...filtered].sort((left, right) => getDocumentSortKey(right.row).localeCompare(getDocumentSortKey(left.row)))
  return sortTableRows(defaultSorted, contractSortKey.value, contractSortDirection.value, contractColumnValue)
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageLimit.value
  return rows.value.slice(start, start + pageLimit.value)
})

const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => currentPage.value * pageLimit.value < rows.value.length)
const visibleRangeStart = computed(() => rows.value.length === 0 ? 0 : (currentPage.value - 1) * pageLimit.value + 1)
const visibleRangeEnd = computed(() => Math.min(currentPage.value * pageLimit.value, rows.value.length))
const activeContractFilterCount = computed(() => [
  query.value.trim(),
  startDate.value,
  endDate.value,
  hideFailed.value ? 'hide-failed' : '',
  ...Object.values(contractColumnFilters).map((value) => value.trim()),
].filter(Boolean).length)

const totals = computed(() => rows.value.reduce((acc, item) => {
  acc.certificate += item.certificate
  acc.expenses += item.modulesCost + item.fixedExpenses + item.customExpenses + item.vat + item.tax + item.acquiring
  acc.profit += item.profit
  return acc
}, { certificate: 0, expenses: 0, profit: 0 }))

function resetPage() {
  currentPage.value = 1
}

function resetContractFilters() {
  query.value = ''
  startDate.value = ''
  endDate.value = ''
  hideFailed.value = false
  Object.keys(contractColumnFilters).forEach((key) => { contractColumnFilters[key] = '' })
  contractSortKey.value = null
  contractSortDirection.value = null
  resetPage()
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
      vat_percent: props.vatPercent,
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

function getExpenseCellTotal(row: ContractAccountingRow, key: string) {
  const history = selectedExpenseRow.value === row && selectedExpenseFieldKey.value === key ? selectedExpenseHistory.value : null
  if (history) return history.total
  if (key.startsWith('custom:')) {
    const field = customFields.value.find((item) => getCustomColumnKey(item) === key)
    return field ? parseMoney(getCustom(row, field)) : 0
  }
  return parseMoney(getExpense(row, key as ExpenseKey))
}

function getExpenseCellLabel(key: string) {
  const fixed = expenseColumns.find((column) => column.key === key)
  if (fixed) return fixed.label
  const field = customFields.value.find((item) => getCustomColumnKey(item) === key)
  return field ? field.label : key
}

async function openExpenseCell(row: ContractAccountingRow, key: string) {
  selectedExpenseRow.value = row
  selectedExpenseFieldKey.value = key
  selectedExpenseFieldLabel.value = getExpenseCellLabel(key)
  expenseAmount.value = ''
  expenseDescription.value = ''
  editingExpenseId.value = null
  editExpenseAmount.value = ''
  editExpenseDescription.value = ''
  pendingDeleteExpenseId.value = null
  selectedExpenseHistory.value = null
  expensePaid.value = true
  expenseDialogLoading.value = true
  try {
    selectedExpenseHistory.value = await fetchContractExpenseHistory(getDocumentId(row), key)
    expensePaid.value = selectedExpenseHistory.value.paid
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
    selectedExpenseRow.value = null
  } finally {
    expenseDialogLoading.value = false
  }
}

function closeExpenseCell() {
  selectedExpenseRow.value = null
  selectedExpenseHistory.value = null
  selectedExpenseFieldKey.value = ''
  editingExpenseId.value = null
  pendingDeleteExpenseId.value = null
  expenseAmount.value = ''
  expenseDescription.value = ''
}

function startEditExpense(entry: { id: string; amount: number; description: string }) {
  editingExpenseId.value = entry.id
  editExpenseAmount.value = formatMoneyInput(entry.amount)
  editExpenseDescription.value = entry.description
  pendingDeleteExpenseId.value = null
}

function cancelEditExpense() {
  editingExpenseId.value = null
  editExpenseAmount.value = ''
  editExpenseDescription.value = ''
}

async function saveEditedExpense() {
  const row = selectedExpenseRow.value
  const key = selectedExpenseFieldKey.value
  const entryId = editingExpenseId.value
  const amount = parseMoney(editExpenseAmount.value)
  const description = editExpenseDescription.value.trim()
  if (!row || !key || !entryId) return
  if (!(amount > 0)) { error.value = 'Введите сумму расхода больше нуля.'; return }
  if (!description) { error.value = 'Введите название или описание расхода.'; return }
  expenseDialogLoading.value = true
  try {
    selectedExpenseHistory.value = await updateContractExpense(getDocumentId(row), key, entryId, { amount, description })
    editingExpenseId.value = null
    success.value = 'Расход изменён'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    expenseDialogLoading.value = false
  }
}

function requestDeleteExpense(entryId: string) {
  pendingDeleteExpenseId.value = pendingDeleteExpenseId.value === entryId ? null : entryId
  editingExpenseId.value = null
}

async function confirmDeleteExpense(entryId: string) {
  const row = selectedExpenseRow.value
  const key = selectedExpenseFieldKey.value
  if (!row || !key) return
  expenseDialogLoading.value = true
  try {
    selectedExpenseHistory.value = await deleteContractExpense(getDocumentId(row), key, entryId)
    pendingDeleteExpenseId.value = null
    success.value = 'Расход удалён'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    expenseDialogLoading.value = false
  }
}

async function saveExpenseEntry() {
  const row = selectedExpenseRow.value
  const key = selectedExpenseFieldKey.value
  const amount = parseMoney(expenseAmount.value)
  const description = expenseDescription.value.trim()
  if (!row || !key) return
  if (!(amount > 0)) { error.value = 'Введите сумму расхода больше нуля.'; return }
  if (!description) { error.value = 'Введите название или описание расхода.'; return }
  expenseDialogLoading.value = true
  try {
    selectedExpenseHistory.value = await addContractExpense(getDocumentId(row), {
      field_key: key, amount, description, paid: key === 'prosthetist_work' ? expensePaid.value : true,
    })
    expenseAmount.value = ''
    expenseDescription.value = ''
    success.value = 'Расход добавлен'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    expenseDialogLoading.value = false
  }
}

async function changeProsthetistPaymentStatus(paid: boolean) {
  const row = selectedExpenseRow.value
  if (!row || selectedExpenseFieldKey.value !== 'prosthetist_work') return
  expenseDialogLoading.value = true
  try {
    selectedExpenseHistory.value = await updateContractExpenseStatus(getDocumentId(row), 'prosthetist_work', paid)
    expensePaid.value = paid
    success.value = paid ? 'Работа протезиста отмечена как оплаченная' : 'Работа протезиста отмечена как неоплаченная'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    expenseDialogLoading.value = false
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
  if (!(await confirmAction({
    message: `Удалить поле «${field.label}» из обеих бухгалтерий?`,
    danger: true,
  }))) {
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

watch([query, startDate, endDate, hideFailed, pageLimit, contractColumnFilters], resetPage, { deep: true })
onMounted(loadData)
</script>

<template>
  <div class="accounting-tab-content">
    <form class="inline-search wide-search contract-accounting-search" @submit.prevent="loadData">
      <input v-model="query" placeholder="Договор, клиент, номер или дата пробития" />
      <DateInput v-model="startDate" aria-label="Дата начала" />
      <DateInput v-model="endDate" aria-label="Дата окончания" />
      <button class="secondary-button" type="submit">Обновить</button>
      <button v-if="activeContractFilterCount" class="ghost-button" type="button" @click="resetContractFilters">
        Сбросить фильтры
      </button>
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
      Скрытие колонок не влияет на расчёты. Каждый договор считается отдельно: НДС извлекается из суммы сертификата, эквайринг считается от полной суммы, а УСН — от выручки без НДС за вычетом себестоимости комплектующих и эквайринга.
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
            <SortableFilterHeader v-if="isColumnVisible('client')" label="Договор / клиент" column-key="client" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.client" @sort="sortContracts" @update:filter-value="contractColumnFilters.client = $event" />
            <SortableFilterHeader v-if="isColumnVisible('certificate')" label="Сертификат" column-key="certificate" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.certificate" @sort="sortContracts" @update:filter-value="contractColumnFilters.certificate = $event" />
            <SortableFilterHeader v-if="isColumnVisible('modules_cost')" label="Стоимость комплектующих" column-key="modules_cost" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.modules_cost" @sort="sortContracts" @update:filter-value="contractColumnFilters.modules_cost = $event" />
            <SortableFilterHeader
              v-for="column in expenseColumns.filter((item) => isColumnVisible(item.key))"
              :key="column.key"
              :label="column.label"
              :column-key="column.key"
              filter-kind="number"
              placeholder="Сумма или диапазон"
              :sort-key="contractSortKey"
              :sort-direction="contractSortDirection"
              :filter-value="contractColumnFilters[column.key]"
              @sort="sortContracts"
              @update:filter-value="contractColumnFilters[column.key] = $event"
            />
            <SortableFilterHeader
              v-for="field in customFields.filter((item) => isColumnVisible(getCustomColumnKey(item)))"
              :key="field.key"
              :label="field.label"
              :column-key="getCustomColumnKey(field)"
              :filter-kind="isNumericField(field) ? 'number' : 'text'"
              :placeholder="isNumericField(field) ? 'Сумма или диапазон' : 'Фильтр…'"
              :sort-key="contractSortKey"
              :sort-direction="contractSortDirection"
              :filter-value="contractColumnFilters[getCustomColumnKey(field)]"
              @sort="sortContracts"
              @update:filter-value="contractColumnFilters[getCustomColumnKey(field)] = $event"
            />
            <SortableFilterHeader v-if="isColumnVisible('vat')" label="НДС" column-key="vat" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.vat" @sort="sortContracts" @update:filter-value="contractColumnFilters.vat = $event" />
            <SortableFilterHeader v-if="isColumnVisible('tax')" label="Налог" column-key="tax" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.tax" @sort="sortContracts" @update:filter-value="contractColumnFilters.tax = $event" />
            <SortableFilterHeader v-if="isColumnVisible('acquiring')" label="Эквайринг" column-key="acquiring" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.acquiring" @sort="sortContracts" @update:filter-value="contractColumnFilters.acquiring = $event" />
            <SortableFilterHeader v-if="isColumnVisible('profit')" label="Прибыль" column-key="profit" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="contractSortKey" :sort-direction="contractSortDirection" :filter-value="contractColumnFilters.profit" @sort="sortContracts" @update:filter-value="contractColumnFilters.profit = $event" />
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in pagedRows" :key="getDocumentId(item.row)">
            <td v-if="isColumnVisible('client')" class="accounting-identity-cell">
              <button class="link-button accounting-client-link" type="button" @click="openClientCard(item.row)">
                <strong>{{ item.row.document.filename }}</strong>
                <span class="muted">{{ item.row.client.short_name }} · {{ getTaxationSystem(item.row) }}</span>
                <span class="muted">Дата пробития: {{ getDocumentDate(item.row) || '—' }}</span>
              </button>
            </td>
            <td
              v-if="isColumnVisible('certificate')"
              class="table-money"
              title="Стоимость сертификата, на основании которого создан этот договор"
            >
              {{ formatMoney(item.certificate) }}
            </td>
            <td v-if="isColumnVisible('modules_cost')" class="table-money">{{ formatMoney(item.modulesCost) }}</td>
            <td v-for="column in expenseColumns.filter((entry) => isColumnVisible(entry.key))" :key="column.key">
              <button
                class="accounting-expense-cell"
                :class="{ 'accounting-expense-unpaid': column.key === 'prosthetist_work' && item.row.expense_status?.prosthetist_work === 'unpaid' }"
                type="button"
                @click="openExpenseCell(item.row, column.key)"
              >
                {{ formatMoney(getExpenseCellTotal(item.row, column.key)) }}
                <span v-if="column.key === 'prosthetist_work' && item.row.expense_status?.prosthetist_work === 'unpaid'" class="accounting-unpaid-badge">Не оплачено</span>
              </button>
            </td>
            <td
              v-for="field in customFields.filter((entry) => isColumnVisible(getCustomColumnKey(entry)))"
              :key="field.key"
            >
              <button
                v-if="isNumericField(field)"
                class="accounting-expense-cell"
                type="button"
                @click="openExpenseCell(item.row, getCustomColumnKey(field))"
              >
                {{ formatMoney(getExpenseCellTotal(item.row, getCustomColumnKey(field))) }}
              </button>
              <input
                v-else
                class="table-input"
                :value="getCustom(item.row, field)"
                inputmode="text"
                @input="setCustom(item.row, field, ($event.target as HTMLInputElement).value)"
              />
            </td>
            <td
              v-if="isColumnVisible('vat')"
              class="table-money"
              :title="`НДС по этому договору · ${props.vatPercent}%`"
            >
              {{ formatMoney(item.vat) }}
            </td>
            <td
              v-if="isColumnVisible('tax')"
              class="table-money"
              :title="`${getTaxationSystem(item.row)} по этому договору`"
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


    <div v-if="selectedExpenseRow" class="accounting-expense-modal" role="dialog" aria-modal="true">
      <div class="accounting-expense-backdrop" @click="closeExpenseCell"></div>
      <section class="accounting-expense-dialog">
        <div class="accounting-expense-dialog-head">
          <div>
            <p class="eyebrow">{{ selectedExpenseRow.document.filename }}</p>
            <h2>{{ selectedExpenseFieldLabel }}</h2>
            <p class="muted">Текущая сумма: <strong>{{ formatMoney(selectedExpenseHistory?.total ?? 0) }}</strong></p>
          </div>
          <button class="ghost-button" type="button" @click="closeExpenseCell">Закрыть</button>
        </div>

        <div v-if="expenseDialogLoading && !selectedExpenseHistory" class="muted">Загружаем историю...</div>
        <template v-else>
          <div class="accounting-expense-history">
            <template v-if="selectedExpenseHistory?.entries.length">
              <div v-for="entry in selectedExpenseHistory.entries" :key="entry.id" class="accounting-expense-entry">
                <template v-if="editingExpenseId === entry.id">
                  <div class="accounting-expense-edit-form">
                    <label><span>Сумма</span><input v-model="editExpenseAmount" inputmode="decimal" /></label>
                    <label><span>Описание</span><input v-model="editExpenseDescription" maxlength="500" /></label>
                    <div class="accounting-expense-entry-actions">
                      <button class="primary-button" type="button" :disabled="expenseDialogLoading" @click="saveEditedExpense">Сохранить</button>
                      <button class="secondary-button" type="button" :disabled="expenseDialogLoading" @click="cancelEditExpense">Отмена</button>
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div><strong>{{ formatMoney(entry.amount) }}</strong><span>{{ entry.description }}</span></div>
                  <div class="accounting-expense-entry-meta">
                    <small>{{ entry.username || 'Система' }} · {{ entry.created_at ? new Date(entry.created_at).toLocaleString('ru-RU') : 'ранее' }}</small>
                    <div class="accounting-expense-entry-actions">
                      <button class="ghost-button" type="button" :disabled="expenseDialogLoading" @click="startEditExpense(entry)">Изменить</button>
                      <button class="danger-button" type="button" :disabled="expenseDialogLoading" @click="requestDeleteExpense(entry.id)">Удалить</button>
                    </div>
                  </div>
                  <div v-if="pendingDeleteExpenseId === entry.id" class="accounting-expense-delete-confirm">
                    <span>Удалить этот расход? Сумма будет пересчитана.</span>
                    <div class="accounting-expense-entry-actions">
                      <button class="danger-button" type="button" :disabled="expenseDialogLoading" @click="confirmDeleteExpense(entry.id)">Удалить</button>
                      <button class="secondary-button" type="button" :disabled="expenseDialogLoading" @click="pendingDeleteExpenseId = null">Отмена</button>
                    </div>
                  </div>
                </template>
              </div>
            </template>
            <p v-else class="muted">Расходов пока нет.</p>
          </div>

          <div v-if="selectedExpenseFieldKey === 'prosthetist_work'" class="accounting-payment-status">
            <span class="muted">Статус выплаты:</span>
            <button class="status-choice" :class="{ active: expensePaid }" type="button" @click="changeProsthetistPaymentStatus(true)">Оплачено</button>
            <button class="status-choice unpaid" :class="{ active: !expensePaid }" type="button" @click="changeProsthetistPaymentStatus(false)">Не оплачено</button>
          </div>

          <form class="accounting-expense-add" @submit.prevent="saveExpenseEntry">
            <label><span>Новый расход</span><input v-model="expenseAmount" inputmode="decimal" placeholder="Сумма" required /></label>
            <label class="accounting-expense-description"><span>На что расход</span><input v-model="expenseDescription" placeholder="Например: дополнительная оплата работы" maxlength="500" required /></label>
            <button class="primary-button" :disabled="expenseDialogLoading" type="submit">Добавить расход</button>
          </form>
        </template>
      </section>
    </div>
</div>
</template>
