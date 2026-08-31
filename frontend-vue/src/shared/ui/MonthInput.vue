<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue?: string
  minYear?: number
  maxYear?: number
  ariaLabel?: string
}>(), {
  modelValue: '',
  minYear: 1900,
  maxYear: 2100,
  ariaLabel: 'Месяц',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const month = ref('')
const year = ref('')

const monthOptions = [
  { value: '01', title: 'Январь' },
  { value: '02', title: 'Февраль' },
  { value: '03', title: 'Март' },
  { value: '04', title: 'Апрель' },
  { value: '05', title: 'Май' },
  { value: '06', title: 'Июнь' },
  { value: '07', title: 'Июль' },
  { value: '08', title: 'Август' },
  { value: '09', title: 'Сентябрь' },
  { value: '10', title: 'Октябрь' },
  { value: '11', title: 'Ноябрь' },
  { value: '12', title: 'Декабрь' },
]

function syncFromModel(value?: string) {
  const match = String(value ?? '').match(/^(\d{4})-(\d{2})$/)
  if (!match) {
    month.value = ''
    year.value = ''
    return
  }
  year.value = match[1]
  month.value = match[2]
}

function commit() {
  const numericYear = Number(year.value)
  if (!/^\d{2}$/.test(month.value) || !/^\d{4}$/.test(year.value)) return
  if (numericYear < props.minYear || numericYear > props.maxYear) return
  emit('update:modelValue', `${year.value}-${month.value}`)
}

watch(() => props.modelValue, syncFromModel, { immediate: true })
</script>

<template>
  <div class="month-input" :aria-label="ariaLabel">
    <select
      v-model="month"
      class="month-input-month"
      :aria-label="`${ariaLabel}: месяц`"
      title="Месяц"
      @change="commit"
    >
      <option value="">ММ</option>
      <option v-for="option in monthOptions" :key="option.value" :value="option.value" :title="option.title">
        {{ option.value }}
      </option>
    </select>
    <input
      v-model="year"
      class="month-input-year"
      type="number"
      inputmode="numeric"
      :min="minYear"
      :max="maxYear"
      placeholder="ГГГГ"
      :aria-label="`${ariaLabel}: год`"
      title="Год"
      @input="commit"
      @blur="commit"
    />
  </div>
</template>

<style scoped>
.month-input {
  display: grid;
  grid-template-columns: 72px minmax(92px, 1fr);
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}
.month-input select,
.month-input input {
  width: 100%;
  min-width: 0;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.month-input-year {
  appearance: textfield;
}
.month-input-year::-webkit-inner-spin-button,
.month-input-year::-webkit-outer-spin-button {
  margin: 0;
  appearance: none;
}
</style>
