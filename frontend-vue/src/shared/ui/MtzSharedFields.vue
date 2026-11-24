<script setup lang="ts">
import { computed } from 'vue'
import MtzDiagnosisPicker from '@/shared/ui/MtzDiagnosisPicker.vue'
import { MTZ_DISABILITY_REASONS } from '@/shared/lib/mtzDiagnosis'
import type { MtzFormConfig } from '@/shared/api/documents'

const props = defineProps<{
  config?: MtzFormConfig | null
  reason: string
  diagnoses: string[]
  stump: string
  activity: string
  weight: string
  mse: string
  tsrLabels: string[]
  extraValues: Record<string,string>
}>()
const emit = defineEmits<{
  'update:reason': [value:string]; 'update:diagnoses':[value:string[]]
  'update:stump':[value:string]; 'update:activity':[value:string]
  'update:weight':[value:string]; 'update:extraValues':[value:Record<string,string>]
}>()
const reasonOptions = computed(() => props.config?.manual.disability_group_reason?.options ?? [...MTZ_DISABILITY_REASONS])
const stumpOptions = computed(() => props.config?.manual.stump_condition?.options ?? ['Функциональная','Нефункциональная'])
const activityOptions = computed(() => props.config?.manual.activity_level?.options ?? ['2-3','3-4'])
const customFields = computed(() => props.config?.custom_fields.filter(f => f.scope==='shared' && f.kind !== 'auto') ?? [])
function extraChange(key:string, value:string) {
  emit('update:extraValues',{...props.extraValues,[key]:value})
}
</script>

<template>
  <div class="mtz-form-fieldset">
    <section class="mtz-section">
      <div class="mtz-section-title"><span class="mtz-section-index">02</span><div><h3>Данные заключения</h3><p>Общие параметры для всех выбранных ТСР</p></div></div>
      <div class="mtz-input-grid">
        <label class="mtz-form-label mtz-span-all">
          {{ config?.manual.disability_group_reason?.label ?? 'Причина инвалидности' }}
          <select :value="reason" @change="emit('update:reason',($event.target as HTMLSelectElement).value)">
            <option value="">Выберите причину</option>
            <option v-for="item in reasonOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <div class="mtz-readonly-mse mtz-span-all"><span>Справка МСЭ · из карточки пациента</span><strong>{{ mse || 'Не заполнена' }}</strong></div>
        <div class="mtz-span-all"><MtzDiagnosisPicker :model-value="diagnoses" :tsr-labels="tsrLabels" :options="config?.manual.diagnoses?.options" @update:model-value="emit('update:diagnoses',$event)" /></div>
        <fieldset class="mtz-control-group"><legend>{{ config?.manual.stump_condition?.label ?? '1.2 Состояние культи' }}</legend>
          <div class="mtz-choice-pills"><button v-for="opt in stumpOptions" :key="opt" type="button" :class="{ selected: stump===opt }" :aria-pressed="stump===opt" @click="emit('update:stump',opt)">{{ opt }}</button></div>
        </fieldset>
        <fieldset class="mtz-control-group"><legend>{{ config?.manual.activity_level?.label ?? '1.3 Уровень активности' }}</legend>
          <div class="mtz-choice-pills"><button v-for="opt in activityOptions" :key="opt" type="button" :class="{ selected: activity===opt }" :aria-pressed="activity===opt" @click="emit('update:activity',opt)">{{ opt }}</button></div>
        </fieldset>
        <label class="mtz-form-label">{{ config?.manual.weight_kg?.label ?? '1.4 Вес пациента (кг)' }}
          <input :value="weight" inputmode="decimal" :placeholder="config?.manual.weight_kg?.placeholder ?? 'Например: 82'" @input="emit('update:weight',($event.target as HTMLInputElement).value)" />
        </label>
        <label v-for="field in customFields" :key="field.key" class="mtz-form-label">
          {{ field.label }} <span v-if="!field.required" class="mtz-optional">необязательно</span>
          <select v-if="field.kind==='select'" :value="extraValues[field.key] ?? ''" @change="extraChange(field.key,($event.target as HTMLSelectElement).value)">
            <option value="">Выберите вариант</option>
            <option v-for="option in field.options" :key="option">{{ option }}</option>
          </select>
          <input v-else :value="extraValues[field.key] ?? ''" :placeholder="field.placeholder" maxlength="500" @input="extraChange(field.key,($event.target as HTMLInputElement).value)" />
        </label>
      </div>
    </section>
  </div>
</template>
