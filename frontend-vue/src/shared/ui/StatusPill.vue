<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'

const props = withDefaults(defineProps<{
  label?: string | null
  kind?: 'status' | 'stage' | 'neutral'
}>(), {
  label: 'Не указан',
  kind: 'neutral',
})

const normalized = computed(() => String(props.label ?? '').toLowerCase())

const tone = computed(() => {
  const value = normalized.value

  if (/(готов|заверш|выполн|актив|получ|оплач|выдан)/.test(value)) {
    return 'success'
  }

  if (/(отказ|удален|ошиб|просроч|заблок)/.test(value)) {
    return 'danger'
  }

  if (/(ожида|отлож|провер|соглас|пример|замер)/.test(value)) {
    return 'warn'
  }

  if (props.kind === 'stage' || /(работ|производ|договор|документ)/.test(value)) {
    return 'info'
  }

  return 'secondary'
})
</script>

<template>
  <Tag
    :value="label || 'Не указан'"
    :severity="tone"
    :class="['status-pill', `status-pill-${kind}`]"
    rounded
  />
</template>
