<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import MonthInput from '@/shared/ui/MonthInput.vue'

const props = withDefaults(defineProps<{
  startDate: string
  endDate: string
  label?: string
  storageKey?: string
}>(), {
  label: 'Период бухгалтерии',
  storageKey: '',
})

const emit = defineEmits<{
  'update:startDate': [value: string]
  'update:endDate': [value: string]
}>()

type PeriodMode = 'month' | 'custom' | 'all'
const mode = ref<PeriodMode>('month')
const monthValue = ref('')
const rangeStartMonth = ref('')
const rangeEndMonth = ref('')
const initialized = ref(false)


type PersistedPeriodState = {
  mode: PeriodMode
  month: string
  rangeStart: string
  rangeEnd: string
}

function loadPersistedState(): PersistedPeriodState | null {
  if (!props.storageKey || typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(props.storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<PersistedPeriodState>
    if (!['month', 'custom', 'all'].includes(String(parsed.mode))) return null
    return {
      mode: parsed.mode as PeriodMode,
      month: normalizeMonth(String(parsed.month ?? '')),
      rangeStart: normalizeMonth(String(parsed.rangeStart ?? '')),
      rangeEnd: normalizeMonth(String(parsed.rangeEnd ?? '')),
    }
  } catch {
    return null
  }
}

function persistState() {
  if (!props.storageKey || typeof window === 'undefined') return
  const payload: PersistedPeriodState = {
    mode: mode.value,
    month: monthValue.value,
    rangeStart: rangeStartMonth.value,
    rangeEnd: rangeEndMonth.value,
  }
  try {
    window.localStorage.setItem(props.storageKey, JSON.stringify(payload))
  } catch {
    // localStorage may be disabled by browser policy; filtering still works normally.
  }
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function normalizeMonth(value: string) {
  return /^\d{4}-\d{2}$/.test(value) ? value : ''
}

function monthBounds(month: string) {
  const normalized = normalizeMonth(month)
  if (!normalized) return { start: '', end: '' }

  const [yearText, monthText] = normalized.split('-')
  const year = Number(yearText)
  const monthNumber = Number(monthText)
  const lastDay = new Date(year, monthNumber, 0).getDate()
  return {
    start: `${yearText}-${monthText}-01`,
    end: `${yearText}-${monthText}-${String(lastDay).padStart(2, '0')}`,
  }
}

function monthFromRange(start: string, end: string) {
  if (!/^\d{4}-\d{2}-01$/.test(start) || !end) return ''
  const month = start.slice(0, 7)
  const bounds = monthBounds(month)
  return bounds.start === start && bounds.end === end ? month : ''
}

function monthFromDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.slice(0, 7) : ''
}

function formatMonth(month: string) {
  const normalized = normalizeMonth(month)
  if (!normalized) return ''
  const [year, monthNumber] = normalized.split('-').map(Number)
  return new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' })
    .format(new Date(year, monthNumber - 1, 1))
}

function setMonth(month = monthValue.value || currentMonth()) {
  const normalized = normalizeMonth(month) || currentMonth()
  monthValue.value = normalized
  mode.value = 'month'
  const bounds = monthBounds(normalized)
  emit('update:startDate', bounds.start)
  emit('update:endDate', bounds.end)
  persistState()
}

function ensureRangeMonths() {
  if (!rangeStartMonth.value) {
    rangeStartMonth.value = monthFromDate(props.startDate) || monthValue.value || currentMonth()
  }
  if (!rangeEndMonth.value) {
    rangeEndMonth.value = monthFromDate(props.endDate) || rangeStartMonth.value
  }
}

function setCustom() {
  mode.value = 'custom'
  ensureRangeMonths()
  applyMonthRange()
}

function applyMonthRange() {
  const startMonth = normalizeMonth(rangeStartMonth.value)
  const endMonth = normalizeMonth(rangeEndMonth.value)
  if (!startMonth || !endMonth) return

  if (startMonth > endMonth) {
    rangeEndMonth.value = startMonth
  }

  const startBounds = monthBounds(rangeStartMonth.value)
  const endBounds = monthBounds(rangeEndMonth.value)
  emit('update:startDate', startBounds.start)
  emit('update:endDate', endBounds.end)
  persistState()
}

function setAll() {
  mode.value = 'all'
  emit('update:startDate', '')
  emit('update:endDate', '')
  persistState()
}

const periodText = computed(() => {
  if (mode.value === 'all') return 'За весь период'
  if (mode.value === 'custom') {
    const start = formatMonth(rangeStartMonth.value)
    const end = formatMonth(rangeEndMonth.value)
    if (start && end) return start === end ? start : `${start} — ${end}`
    return 'Диапазон месяцев'
  }
  return formatMonth(monthValue.value) || 'Текущий месяц'
})

watch(
  () => [props.startDate, props.endDate] as const,
  ([start, end]) => {
    if (!initialized.value) return
    if (!start && !end) {
      mode.value = 'all'
      persistState()
      return
    }

    const exactMonth = monthFromRange(start, end)
    if (exactMonth) {
      monthValue.value = exactMonth
      if (mode.value !== 'custom') mode.value = 'month'
      persistState()
      return
    }

    rangeStartMonth.value = monthFromDate(start)
    rangeEndMonth.value = monthFromDate(end)
    mode.value = 'custom'
    persistState()
  },
)

onMounted(() => {
  const suppliedMonth = monthFromRange(props.startDate, props.endDate)
  if (suppliedMonth) {
    monthValue.value = suppliedMonth
    mode.value = 'month'
  } else if (props.startDate || props.endDate) {
    rangeStartMonth.value = monthFromDate(props.startDate) || currentMonth()
    rangeEndMonth.value = monthFromDate(props.endDate) || rangeStartMonth.value
    mode.value = 'custom'
  } else {
    const persisted = loadPersistedState()
    if (persisted?.mode === 'all') {
      mode.value = 'all'
      monthValue.value = persisted.month || currentMonth()
      rangeStartMonth.value = persisted.rangeStart
      rangeEndMonth.value = persisted.rangeEnd
      emit('update:startDate', '')
      emit('update:endDate', '')
    } else if (persisted?.mode === 'custom' && persisted.rangeStart && persisted.rangeEnd) {
      mode.value = 'custom'
      monthValue.value = persisted.month || persisted.rangeStart
      rangeStartMonth.value = persisted.rangeStart
      rangeEndMonth.value = persisted.rangeEnd
      applyMonthRange()
    } else if (persisted?.mode === 'month' && persisted.month) {
      setMonth(persisted.month)
    } else {
      setMonth(currentMonth())
    }
  }
  initialized.value = true
  persistState()
})
</script>

<template>
  <div class="accounting-period-filter">
    <div class="accounting-period-heading">
      <div class="accounting-period-title">
        <p class="eyebrow">{{ label }}</p>
        <strong>{{ periodText }}</strong>
      </div>
      <div class="accounting-period-modes" role="group" aria-label="Режим периода бухгалтерии">
        <button type="button" :class="{ active: mode === 'month' }" @click="setMonth()">Месяц</button>
        <button type="button" :class="{ active: mode === 'custom' }" @click="setCustom">Период</button>
        <button type="button" :class="{ active: mode === 'all' }" @click="setAll">Всё время</button>
      </div>
    </div>

    <div class="accounting-period-body">
      <div v-if="mode === 'month'" class="accounting-period-fields accounting-period-fields-month">
        <label>
          <span>Месяц</span>
          <MonthInput v-model="monthValue" aria-label="Месяц бухгалтерии" @update:model-value="setMonth($event)" />
        </label>
        <p class="accounting-period-note">Будет выбран весь месяц — с 1-го числа по последний день.</p>
      </div>

      <div v-else-if="mode === 'custom'" class="accounting-period-fields accounting-period-fields-range">
        <label>
          <span>С месяца</span>
          <MonthInput v-model="rangeStartMonth" aria-label="Начальный месяц бухгалтерии" @update:model-value="applyMonthRange" />
        </label>
        <label>
          <span>По месяц</span>
          <MonthInput v-model="rangeEndMonth" aria-label="Конечный месяц бухгалтерии" @update:model-value="applyMonthRange" />
        </label>
      </div>

      <div v-else class="accounting-period-all-state">
        <strong>Фильтр по дате отключён</strong>
        <span>Показывается бухгалтерия за весь доступный период.</span>
      </div>
    </div>
  </div>
</template>
