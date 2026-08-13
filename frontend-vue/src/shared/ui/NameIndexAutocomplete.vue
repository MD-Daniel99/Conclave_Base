<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  options: Array<{ value: string; label: string }>
  placeholder?: string
  required?: boolean
  showAllOnFocus?: boolean
}>(), {
  placeholder: 'Введите название или индекс',
  required: false,
  showAllOnFocus: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const open = ref(false)

const query = computed(() => props.modelValue.trim().toLocaleLowerCase('ru-RU'))
const matches = computed(() => {
  const source = props.options.filter((option) => option.label.trim())
  const filtered = query.value
    ? source.filter((option) => option.label.toLocaleLowerCase('ru-RU').includes(query.value))
    : (props.showAllOnFocus ? source : [])
  return filtered.slice(0, 10)
})

function selectOption(label: string) {
  emit('update:modelValue', label)
  open.value = false
}

function highlightParts(label: string) {
  if (!query.value) return [{ text: label, match: false }]
  const lower = label.toLocaleLowerCase('ru-RU')
  const index = lower.indexOf(query.value)
  if (index < 0) return [{ text: label, match: false }]
  return [
    { text: label.slice(0, index), match: false },
    { text: label.slice(index, index + query.value.length), match: true },
    { text: label.slice(index + query.value.length), match: false },
  ].filter((part) => part.text)
}
</script>

<template>
  <div class="name-index-autocomplete" @focusin="open = true" @focusout="open = false">
    <input
      :value="modelValue"
      :placeholder="placeholder"
      :required="required"
      autocomplete="off"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value); open = true"
      @keydown.esc="open = false"
    />
    <div v-if="open && matches.length" class="name-index-autocomplete-menu" role="listbox">
      <button
        v-for="option in matches"
        :key="option.value || option.label"
        type="button"
        class="name-index-autocomplete-option"
        @mousedown.prevent="selectOption(option.label)"
      >
        <span>
          <template v-for="(part, index) in highlightParts(option.label)" :key="`${option.value}-${index}`">
            <mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template>
          </template>
        </span>
        <small>из справочника</small>
      </button>
    </div>
  </div>
</template>
