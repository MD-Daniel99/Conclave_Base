<script setup lang="ts">
import { computed, ref } from 'vue'
import { MTZ_DIAGNOSES, suggestMtzDiagnoses } from '@/shared/lib/mtzDiagnosis'

const props = defineProps<{ modelValue: string[]; tsrLabels: string[]; options?: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const showAll = ref(false)
const suggested = computed(() => suggestMtzDiagnoses(props.tsrLabels))
const options = computed(() => {
  const allowed = props.options?.length ? props.options : MTZ_DIAGNOSES
  const filtered = suggested.value.filter(v => allowed.includes(v))
  return (showAll.value || filtered.length === 0) ? allowed : filtered
})

function toggle(item: string, checked: boolean) {
  const next = checked
    ? [...new Set([...props.modelValue, item])]
    : props.modelValue.filter((value) => value !== item)
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="mtz-diagnosis-picker">
    <div class="mtz-diagnosis-top">
      <strong>Диагноз (можно выбрать несколько)</strong>
      <label v-if="suggested.length" class="mtz-diagnosis-show-all">
        <input v-model="showAll" type="checkbox" /> Все варианты
      </label>
    </div>
    <p class="form-hint">{{ suggested.length ? 'Показаны варианты по указанным ТСР. Уточните фактический диагноз пациента.' : 'Для этих ТСР не определена группа — показаны все варианты.' }}</p>
    <div class="mtz-diagnosis-list" role="group" aria-label="Диагнозы МТЗ">
      <label v-for="item in options" :key="item" class="mtz-diagnosis-choice">
        <input type="checkbox" :checked="modelValue.includes(item)" @change="toggle(item, ($event.target as HTMLInputElement).checked)" />
        <span>{{ item }}</span>
      </label>
    </div>
    <p v-if="modelValue.length" class="form-hint">Выбрано диагнозов: {{ modelValue.length }}</p>
    <div v-if="modelValue.some((item) => !options.includes(item))" class="mtz-diagnosis-selected">
      <label v-for="item in modelValue.filter((item) => !options.includes(item))" :key="item" class="mtz-diagnosis-choice">
        <input type="checkbox" checked @change="toggle(item, false)" /> <span>{{ item }}</span>
      </label>
    </div>
  </div>
</template>

<style scoped>
.mtz-diagnosis-picker { display: grid; gap: .5rem; min-width: 0; }
.mtz-diagnosis-top { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.mtz-diagnosis-show-all { display: inline-flex; align-items: center; gap: .5rem; white-space: nowrap; }
.mtz-diagnosis-list { display: grid; gap: .35rem; max-height: 260px; overflow: auto; padding: .5rem; border: 1px solid var(--border, #657187); border-radius: 10px; }
.mtz-diagnosis-choice { display: flex; align-items: flex-start; gap: .5rem; line-height: 1.4; cursor: pointer; }
.mtz-diagnosis-choice input { margin-top: .2rem; flex-shrink: 0; width: 1rem; height: 1rem; }
.mtz-diagnosis-selected { padding: .45rem .6rem; border-inline-start: 2px solid currentColor; }
</style>
