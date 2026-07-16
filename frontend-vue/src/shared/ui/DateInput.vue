<script setup lang="ts">
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

function normalizeDate(value?: string | null) {
  const raw = String(value ?? '').slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : ''
}

function updateDate(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <input
    class="date-input"
    type="date"
    :value="normalizeDate(modelValue)"
    :min="`${props.minYear}-01-01`"
    :max="`${props.maxYear}-12-31`"
    :disabled="disabled"
    :required="required"
    :aria-label="ariaLabel"
    @input="updateDate"
  />
</template>
