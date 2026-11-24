<script setup lang="ts">
import { computed, ref } from 'vue'
import type { MtzConclusionItem, MtzTemplateOption, MtzFormConfig } from '@/shared/api/documents'

const props = defineProps<{ modelValue: MtzConclusionItem[]; templates: MtzTemplateOption[]; config?: MtzFormConfig | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: MtzConclusionItem[]] }>()
const choice = ref('')
const selectedChoice = computed(() => choice.value || props.templates[0]?.value || '')
const levelName = computed(() => props.config?.manual.amputation_level?.label ?? '1.1 Уровень ампутации для этого ТСР')
const levelCodeName = computed(() => props.config?.manual.amputation_code?.label ?? 'Код классификации (необязательно)')
const perItemFields = computed(() => props.config?.custom_fields.filter(f => f.scope==='per_item' && f.kind !== 'auto') ?? [])
function addConclusion() {
  if (!selectedChoice.value || props.modelValue.length >= 40) return
  emit('update:modelValue', [...props.modelValue, { template_type: selectedChoice.value, amputation_level: '',extra_fields:{} }])
}
function patch(index: number, values: Partial<MtzConclusionItem>) {
  emit('update:modelValue', props.modelValue.map((item, i) => i === index ? { ...item, ...values } : item))
}
function patchExtra(index:number,key:string,val:string){
  patch(index,{extra_fields:{...props.modelValue[index].extra_fields,[key]:val}})
}
function move(index: number, offset: number) {
  const target=index+offset
  if (target<0 || target>=props.modelValue.length) return
  const rows=[...props.modelValue];[rows[index],rows[target]]=[rows[target],rows[index]]
  emit('update:modelValue',rows)
}
function remove(index: number) { emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
function label(key: string) { return props.templates.find(x => x.value===key)?.label ?? 'Заключение недоступно' }
</script>

<template>
  <section class="mtz-conclusions-picker mtz-section">
    <div class="mtz-section-title"><span class="mtz-section-index">01</span><div><h3>Заключения ТСР</h3><p>Выберите от одного до 40 вариантов, порядок можно изменить</p></div><span class="mtz-count">{{ modelValue.length }} выбрано</span></div>
    <div class="mtz-conclusions-add">
      <label class="mtz-form-label">Вид ТСР
        <select v-model="choice" :disabled="!templates.length">
          <option value="" disabled>Выберите заключение</option>
          <option v-for="template in templates" :key="template.value" :value="template.value">{{ template.label }}</option>
        </select>
      </label>
      <button class="primary-button" type="button" :disabled="!templates.length || modelValue.length >= 40" @click="addConclusion">+ Добавить ТСР</button>
    </div>
    <ol v-if="modelValue.length" class="mtz-conclusions-list">
      <li v-for="(item, index) in modelValue" :key="index" class="mtz-conclusions-item">
        <div class="mtz-conclusions-item-head">
          <span class="mtz-conclusion-index">{{ index+1 }}</span>
          <strong>{{ label(item.template_type) }}</strong>
          <div class="mtz-item-actions">
            <button type="button" title="Переместить выше" :disabled="index===0" @click="move(index,-1)">↑</button>
            <button type="button" title="Переместить ниже" :disabled="index===modelValue.length-1" @click="move(index,1)">↓</button>
            <button type="button" class="mtz-remove" title="Удалить из выбора" @click="remove(index)">×</button>
          </div>
        </div>
        <div class="mtz-item-inputs">
          <label class="mtz-form-label">{{ levelName }}
            <input :value="item.amputation_level" maxlength="512" :placeholder="config?.manual.amputation_level?.placeholder ?? 'Уровень ампутации'" @input="patch(index,{amputation_level:($event.target as HTMLInputElement).value})" />
          </label>
          <label class="mtz-form-label">{{ levelCodeName }}
            <input :value="item.amputation_code ?? ''" maxlength="40" :placeholder="config?.manual.amputation_code?.placeholder ?? 'Например 1.1.3'" @input="patch(index,{amputation_code:($event.target as HTMLInputElement).value})" />
          </label>
          <label v-for="field in perItemFields" :key="field.key" class="mtz-form-label">{{ field.label }}
            <select v-if="field.kind==='select'" :value="item.extra_fields?.[field.key] ?? ''" @change="patchExtra(index,field.key,($event.target as HTMLSelectElement).value)">
              <option value="">Выберите</option><option v-for="opt in field.options" :key="opt">{{ opt }}</option>
            </select>
            <input v-else :value="item.extra_fields?.[field.key] ?? ''" maxlength="500" :placeholder="field.placeholder" @input="patchExtra(index,field.key,($event.target as HTMLInputElement).value)" />
          </label>
        </div>
      </li>
    </ol>
    <div v-else class="mtz-empty">Пока нет заключений. Выберите вид ТСР в списке выше.</div>
    <p class="mtz-helper">Для каждого ТСР свой уровень ампутации. Состояние культи, активность и вес вводятся ниже один раз.</p>
  </section>
</template>
