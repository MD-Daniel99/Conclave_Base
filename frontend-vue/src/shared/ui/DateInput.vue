<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue?: string | null
  minYear?: number
  maxYear?: number
  disabled?: boolean
  required?: boolean
  ariaLabel?: string
}>(), {
  modelValue: '',
  minYear: 1900,
  maxYear: 2100,
  disabled: false,
  required: false,
  ariaLabel: 'Дата',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const day = ref('')
const month = ref('')
const year = ref('')

const monthOptions = [
  { value: '01', label: '01', title: 'Январь' },
  { value: '02', label: '02', title: 'Февраль' },
  { value: '03', label: '03', title: 'Март' },
  { value: '04', label: '04', title: 'Апрель' },
  { value: '05', label: '05', title: 'Май' },
  { value: '06', label: '06', title: 'Июнь' },
  { value: '07', label: '07', title: 'Июль' },
  { value: '08', label: '08', title: 'Август' },
  { value: '09', label: '09', title: 'Сентябрь' },
  { value: '10', label: '10', title: 'Октябрь' },
  { value: '11', label: '11', title: 'Ноябрь' },
  { value: '12', label: '12', title: 'Декабрь' },
]

function normalizeDate(value?: string | null) {
  const raw = String(value ?? '').slice(0, 10)
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)

  if (!match) {
    return null
  }

  const parsedYear = Number(match[1])
  const parsedMonth = Number(match[2])
  const parsedDay = Number(match[3])
  const candidate = new Date(Date.UTC(parsedYear, parsedMonth - 1, parsedDay))
  const isExactDate = candidate.getUTCFullYear() === parsedYear
    && candidate.getUTCMonth() === parsedMonth - 1
    && candidate.getUTCDate() === parsedDay

  if (!isExactDate || parsedYear < props.minYear || parsedYear > props.maxYear) {
    return null
  }

  return { day: match[3], month: match[2], year: match[1] }
}

function syncFromModel(value?: string | null) {
  const parsed = normalizeDate(value)
  day.value = parsed?.day ?? ''
  month.value = parsed?.month ?? ''
  year.value = parsed?.year ?? ''
}

function getDaysInMonth(rawYear: string, rawMonth: string) {
  const parsedYear = Number(rawYear)
  const parsedMonth = Number(rawMonth)

  if (!Number.isInteger(parsedYear) || !Number.isInteger(parsedMonth) || parsedMonth < 1 || parsedMonth > 12) {
    return 31
  }

  return new Date(Date.UTC(parsedYear, parsedMonth, 0)).getUTCDate()
}

const dayOptions = computed(() => {
  const count = getDaysInMonth(year.value, month.value)
  return Array.from({ length: count }, (_, index) => String(index + 1).padStart(2, '0'))
})

const hasDraft = computed(() => Boolean(day.value || month.value || year.value))

function commitDate() {
  if (!day.value || !month.value || !/^\d{4}$/.test(year.value)) {
    return
  }

  const parsedYear = Number(year.value)
  if (parsedYear < props.minYear || parsedYear > props.maxYear) {
    return
  }

  const lastDay = getDaysInMonth(year.value, month.value)
  const normalizedDay = Math.min(Number(day.value), lastDay)
  day.value = String(normalizedDay).padStart(2, '0')
  emit('update:modelValue', `${year.value}-${month.value}-${day.value}`)
}

function clearDate() {
  day.value = ''
  month.value = ''
  year.value = ''
  emit('update:modelValue', '')
}

watch(
  () => [props.modelValue, props.minYear, props.maxYear] as const,
  ([value]) => syncFromModel(value),
  { immediate: true },
)
</script>

<template>
  <div class="date-input" :aria-label="ariaLabel">
    <select
      v-model="day"
      class="date-input-day"
      :disabled="disabled"
      :required="required"
      :aria-label="`${ariaLabel}: день`"
      title="День"
      @change="commitDate"
    >
      <option value="">ДД</option>
      <option v-for="option in dayOptions" :key="option" :value="option">{{ option }}</option>
    </select>
    <select
      v-model="month"
      class="date-input-month"
      :disabled="disabled"
      :required="required"
      :aria-label="`${ariaLabel}: месяц`"
      title="Месяц"
      @change="commitDate"
    >
      <option value="">ММ</option>
      <option
        v-for="option in monthOptions"
        :key="option.value"
        :value="option.value"
        :title="option.title"
      >
        {{ option.label }}
      </option>
    </select>
    <input
      v-model="year"
      class="date-input-year"
      type="number"
      inputmode="numeric"
      :min="minYear"
      :max="maxYear"
      :disabled="disabled"
      :required="required"
      placeholder="ГГГГ"
      :aria-label="`${ariaLabel}: год`"
      title="Год можно ввести с клавиатуры"
      @input="commitDate"
      @blur="commitDate"
    />
    <button
      v-if="hasDraft && !required"
      class="date-input-clear"
      type="button"
      :disabled="disabled"
      :aria-label="`Очистить поле «${ariaLabel}»`"
      title="Очистить дату"
      @click="clearDate"
    >
      ×
    </button>
  </div>
</template>
