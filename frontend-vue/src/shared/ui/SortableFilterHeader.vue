<script setup lang="ts">
import type { SortDirection, TableFilterKind } from '@/shared/lib/table'

interface FilterOption {
  value: string | number
  label: string
}

const props = withDefaults(defineProps<{
  label: string
  columnKey: string
  sortKey?: string | null
  sortDirection?: SortDirection
  filterValue?: string | number | null
  filterKind?: TableFilterKind
  options?: FilterOption[]
  placeholder?: string
  filterAriaLabel?: string
  filterable?: boolean
}>(), {
  sortKey: null,
  sortDirection: null,
  filterValue: '',
  filterKind: 'text',
  options: () => [],
  placeholder: 'Фильтр…',
  filterAriaLabel: '',
  filterable: true,
})

const emit = defineEmits<{
  sort: [key: string]
  'update:filterValue': [value: string]
}>()

function updateFilter(event: Event) {
  emit('update:filterValue', (event.target as HTMLInputElement | HTMLSelectElement).value)
}
</script>

<template>
  <th class="filterable-table-header">
    <button
      type="button"
      class="table-sort-button"
      :class="{ 'is-sorted': props.sortKey === props.columnKey }"
      :aria-label="`Сортировать: ${props.label}`"
      @click="emit('sort', props.columnKey)"
    >
      <span>{{ props.label }}</span>
      <span class="table-sort-indicator" aria-hidden="true">
        {{ props.sortKey === props.columnKey ? (props.sortDirection === 'asc' ? '▲' : '▼') : '↕' }}
      </span>
    </button>

    <select
      v-if="props.filterable && props.filterKind === 'select'"
      class="table-column-filter"
      :value="props.filterValue ?? ''"
      :aria-label="props.filterAriaLabel || `Фильтр: ${props.label}`"
      @click.stop
      @change="updateFilter"
    >
      <option value="">Все</option>
      <option v-for="option in props.options" :key="String(option.value)" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <input
      v-else-if="props.filterable"
      class="table-column-filter"
      :type="props.filterKind === 'date' ? 'text' : 'text'"
      :inputmode="props.filterKind === 'number' ? 'decimal' : undefined"
      :value="props.filterValue ?? ''"
      :placeholder="props.placeholder"
      :aria-label="props.filterAriaLabel || `Фильтр: ${props.label}`"
      @click.stop
      @input="updateFilter"
    />
  </th>
</template>
