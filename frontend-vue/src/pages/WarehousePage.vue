<script setup lang="ts">
import NameIndexAutocomplete from '@/shared/ui/NameIndexAutocomplete.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Archive, Eye, PackageOpen, Plus, RotateCcw, Search, Trash2, X } from '@lucide/vue'
import { fetchClients } from '@/shared/api/clients'
import {
  archiveComponent,
  createComponent,
  deleteComponent,
  fetchComponents,
  moveComponentToStock,
  moveComponentToWorkStock,
  restoreComponent,
  updateComponent,
} from '@/shared/api/components'
import { getApiErrorMessage } from '@/shared/api/http'
import { fetchNameIndexReferences, fetchTsrReferences } from '@/shared/api/references'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import { matchesTableFilter, nextSortState, sortTableRows, type SortDirection } from '@/shared/lib/table'
import { formatMoney, formatMoneyInput } from '@/shared/lib/money'
import ActionMenu, { type ActionMenuItem } from '@/shared/ui/ActionMenu.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'
import StatusPill from '@/shared/ui/StatusPill.vue'
import SortableFilterHeader from '@/shared/ui/SortableFilterHeader.vue'
import type {
  Client,
  ComponentCreatePayload,
  ComponentItem,
  ComponentUpdatePayload,
  ReferenceItem,
} from '@/shared/types/entities'

type CountInput = string | number
type WarehouseListMode = 'active' | 'stock' | 'archive'
type WarehouseBulkAction = 'stock' | 'work' | 'archive' | 'restore' | 'delete'

type ComponentForm = {
  tsr_id: string
  module_name_index: string
  supplier: string
  ordered: CountInput
  order_date_acc_num: string
  quantity: string
  size: string
  stiffness: string
  side: string
  unit_cost: string
  unit_price: string
  recd: CountInput
  pending: CountInput
  prosthetist_keep: CountInput
  properties: string
  client_id: string
  notes: string
}

const emptyComponentForm: ComponentForm = {
  tsr_id: '',
  module_name_index: '',
  supplier: '',
  ordered: '0',
  order_date_acc_num: '-',
  quantity: '1',
  size: '',
  stiffness: '',
  side: '',
  unit_cost: '',
  unit_price: '',
  recd: '0',
  pending: '0',
  prosthetist_keep: '0',
  properties: '-',
  client_id: '',
  notes: '',
}

const components = ref<ComponentItem[]>([])
const clients = ref<Client[]>([])
const nameIndexReferences = ref<ReferenceItem[]>([])
const tsrReferences = ref<ReferenceItem[]>([])
const selectedComponent = ref<ComponentItem | null>(null)
const isComponentCardOpen = ref(false)
const query = ref('')
const warehouseColumnFilters = reactive<Record<string, string>>({ name: '', supplier: '', quantity: '', cost: '', price: '', order: '', owner: '' })
const warehouseSortKey = ref<string | null>(null)
const warehouseSortDirection = ref<SortDirection>(null)
const pageLimit = ref(100)
const currentPage = ref(1)
const activeWarehouseListMode = ref<WarehouseListMode>('active')
const selectedComponentIds = ref<string[]>([])
const componentForm = reactive<ComponentForm>({ ...emptyComponentForm })
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const successMessage = ref('')

const isEditingComponent = computed(() => Boolean(selectedComponent.value?.module_id))
const currentSkip = computed(() => (currentPage.value - 1) * pageLimit.value)
const hasPreviousPage = computed(() => currentPage.value > 1)

function warehouseRowNumber(item: ComponentItem) {
  const index = components.value.findIndex((candidate) => getComponentId(candidate) === getComponentId(item))
  return index >= 0 ? index + 1 : 0
}

function warehouseColumnValue(item: ComponentItem, key: string) {
  if (key === 'number') return warehouseRowNumber(item)
  if (key === 'name') return `${getComponentName(item)} ${item.tsr?.full_tsr_code || ''}`
  if (key === 'cost') return item.cost ?? 0
  if (key === 'price') return item.price ?? 0
  if (key === 'order') return `Заказано ${item.ordered ?? 0} Получено ${item.recd ?? 0} Ожидается ${item.pending ?? 0}`
  if (key === 'owner') return getClientLabel(item.client_id)
  return item[key as keyof ComponentItem]
}

function sortWarehouse(key: string) {
  const next = nextSortState({ key: warehouseSortKey.value, direction: warehouseSortDirection.value }, key)
  warehouseSortKey.value = next.key
  warehouseSortDirection.value = next.direction
  currentPage.value = 1
}

const filteredComponents = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('ru-RU')
  const filtered = components.value.filter((item) => {
    const searchable = [
      getComponentName(item), item.tsr?.full_tsr_code, item.supplier,
      item.order_date_acc_num, item.properties, item.notes, getClientLabel(item.client_id),
    ].filter(Boolean).join(' ').toLocaleLowerCase('ru-RU')
    if (needle && !searchable.includes(needle)) return false
    return Object.entries(warehouseColumnFilters).every(([key, filter]) => {
      const kind = ['number', 'quantity', 'cost', 'price'].includes(key) ? 'number' : 'text'
      return matchesTableFilter(warehouseColumnValue(item, key), filter, kind)
    })
  })
  return sortTableRows(filtered, warehouseSortKey.value, warehouseSortDirection.value, warehouseColumnValue)
})
const pagedComponents = computed(() => filteredComponents.value.slice(currentSkip.value, currentSkip.value + pageLimit.value))
const hasMore = computed(() => currentSkip.value + pageLimit.value < filteredComponents.value.length)
const componentQuantity = computed(() => Math.max(1, Math.trunc(toNumber(componentForm.quantity, 1))))
const componentTotalCost = computed(() => (toOptionalNumber(componentForm.unit_cost) ?? 0) * componentQuantity.value)
const componentTotalPrice = computed(() => (toOptionalNumber(componentForm.unit_price) ?? 0) * componentQuantity.value)
const stockTotalCost = computed(() => components.value.reduce((sum, item) => sum + Number(item.cost ?? 0), 0))
const stockTotalPrice = computed(() => components.value.reduce((sum, item) => sum + Number(item.price ?? 0), 0))
const stockTotalQuantity = computed(() => components.value.reduce((sum, item) => sum + Math.max(0, Number(item.quantity ?? 0)), 0))
const selectedComponents = computed(() => {
  const ids = new Set(selectedComponentIds.value)
  return components.value.filter((item) => ids.has(getComponentId(item)))
})
const pagedComponentIds = computed(() => pagedComponents.value.map(getComponentId).filter(Boolean))
const allPagedComponentsSelected = computed(() => (
  pagedComponentIds.value.length > 0
  && pagedComponentIds.value.every((id) => selectedComponentIds.value.includes(id))
))
const visibleOwnerClients = computed(() => (
  activeWarehouseListMode.value === 'archive'
    ? clients.value
    : clients.value.filter((client) => !client.is_archived)
))
const tsrOptions = computed(() => tsrReferences.value
  .map((item) => ({
    value: String(item.id ?? item.tsr_id ?? ''),
    label: String(item.full_tsr_code ?? ''),
  }))
  .filter((item) => item.value && item.label))
const activeWarehouseFilterCount = computed(() => [
  query.value.trim(),
  ...Object.values(warehouseColumnFilters).map((value) => value.trim()),
].filter(Boolean).length)
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Склад')

function resetMessages() {
  error.value = ''
  successMessage.value = ''
}

function getComponentActions(item: ComponentItem): ActionMenuItem[] {
  if (activeWarehouseListMode.value === 'active') {
    return [
      {
        label: 'Открыть карточку',
        icon: Eye,
        action: () => selectComponent(item),
      },
      {
        label: 'Переместить на Склад',
        icon: PackageOpen,
        disabled: isSaving.value,
        action: () => changeComponentStockState(item, true),
      },
      {
        label: 'Переместить в Списанные комплектующие',
        icon: Archive,
        disabled: isSaving.value,
        action: () => changeComponentArchiveState(item, true),
      },
      {
        label: 'Удалить',
        icon: Trash2,
        danger: true,
        disabled: isSaving.value,
        action: () => removeComponent(item),
      },
    ]
  }

  if (activeWarehouseListMode.value === 'stock') {
    return [
      {
        label: 'Открыть карточку',
        icon: Eye,
        action: () => selectComponent(item),
      },
      {
        label: 'Вернуть в Рабочий склад',
        icon: RotateCcw,
        disabled: isSaving.value,
        action: () => changeComponentStockState(item, false),
      },
      {
        label: 'Переместить в Списанные комплектующие',
        icon: Archive,
        disabled: isSaving.value,
        action: () => changeComponentArchiveState(item, true),
      },
      {
        label: 'Удалить',
        icon: Trash2,
        danger: true,
        disabled: isSaving.value,
        action: () => removeComponent(item),
      },
    ]
  }

  if (item.is_manually_archived && !isComponentOwnerArchived(item)) {
    return [
      {
        label: 'Восстановить',
        icon: RotateCcw,
        disabled: isSaving.value,
        action: () => changeComponentArchiveState(item, false),
      },
    ]
  }

  return [{
    label: 'В архиве вместе с клиентом',
    disabled: true,
    action: () => undefined,
  }]
}

function toNumber(value: CountInput, fallback = 0) {
  const parsed = Number(String(value).trim().replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : fallback
}

function toCount(value: CountInput) {
  return Math.max(0, Math.trunc(toNumber(value, 0)))
}

function toOptionalNumber(value: string) {
  const normalized = value
    .trim()
    .replace(/[\s\u00a0\u202f]/g, '')
    .replace(',', '.')
    .replace(/[^\d.-]/g, '')
  const parsed = Number(normalized)
  return normalized && Number.isFinite(parsed) ? parsed : undefined
}

function optional(value: string) {
  return value.trim() || null
}

function required(value: string, fallback: string) {
  return value.trim() || fallback
}

function formatComponentMoneyField(field: 'unit_cost' | 'unit_price') {
  componentForm[field] = formatMoneyInput(componentForm[field])
}

function getComponentId(item: ComponentItem) {
  return String(item.module_id ?? '')
}

function getComponentName(item: ComponentItem) {
  return item.module_name_index || item.properties || 'Без названия'
}

function getComponentAttributes(item: ComponentItem) {
  return [
    `Размер: ${item.size || '—'}`,
    `Жёсткость: ${item.stiffness || '—'}`,
    `Сторона: ${item.side || '—'}`,
  ].join(' · ')
}

function getClientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ') || 'Без имени'
}

function getClientLabel(clientId?: string | null) {
  if (!clientId) {
    return 'На складе'
  }

  const client = clients.value.find((item) => String(item.client_id) === String(clientId))
  return client ? getClientName(client) : String(clientId)
}

function isComponentOwnerArchived(item: ComponentItem) {
  if (!item.client_id) {
    return false
  }

  return Boolean(
    clients.value.find((client) => String(client.client_id) === String(item.client_id))?.is_archived,
  )
}


function resetComponentForm() {
  Object.assign(componentForm, emptyComponentForm)
  selectedComponent.value = null
  resetMessages()
}

function openNewComponent() {
  resetComponentForm()
  isComponentCardOpen.value = true
}

function closeComponentCard() {
  isComponentCardOpen.value = false
}

function selectComponent(item: ComponentItem) {
  selectedComponent.value = item
  const quantity = Number(item.quantity ?? 1) || 1

  Object.assign(componentForm, {
    tsr_id: String(item.tsr_id ?? item.tsr?.id ?? ''),
    module_name_index: item.module_name_index ?? '',
    supplier: item.supplier ?? '',
    order_date_acc_num: item.order_date_acc_num ?? '-',
    quantity: String(quantity),
    size: item.size ?? '',
    stiffness: item.stiffness ?? '',
    side: item.side ?? '',
    unit_cost: item.cost == null ? '' : formatMoneyInput(Number(item.cost) / quantity),
    unit_price: item.price == null ? '' : formatMoneyInput(Number(item.price) / quantity),
    ordered: String(item.ordered ?? 0),
    recd: String(item.recd ?? 0),
    pending: String(item.pending ?? 0),
    prosthetist_keep: String(item.prosthetist_keep ?? 0),
    properties: item.properties ?? '-',
    client_id: item.client_id ?? '',
    notes: item.notes ?? '',
  })

  isComponentCardOpen.value = true
  resetMessages()
}

function buildComponentPayload(): ComponentCreatePayload {
  return {
    tsr_id: componentForm.tsr_id || null,
    client_id: componentForm.client_id || null,
    module_name_index: componentForm.module_name_index.trim(),
    supplier: componentForm.supplier.trim(),
    order_date_acc_num: required(componentForm.order_date_acc_num, '-'),
    quantity: componentQuantity.value,
    size: optional(componentForm.size),
    stiffness: optional(componentForm.stiffness),
    side: optional(componentForm.side),
    cost: componentTotalCost.value,
    price: componentTotalPrice.value,
    ordered: toCount(componentForm.ordered),
    recd: toCount(componentForm.recd),
    pending: toCount(componentForm.pending),
    prosthetist_keep: toCount(componentForm.prosthetist_keep),
    properties: required(componentForm.properties, '-'),
    notes: optional(componentForm.notes),
  }
}

async function loadData() {
  isLoading.value = true
  error.value = ''

  try {
    components.value = await fetchComponents({
      skip: 0,
      limit: 100000,
      archived: activeWarehouseListMode.value === 'archive',
      in_stock: activeWarehouseListMode.value === 'archive'
        ? undefined
        : activeWarehouseListMode.value === 'stock',
    })
    const availableIds = new Set(components.value.map(getComponentId))
    selectedComponentIds.value = selectedComponentIds.value.filter((id) => availableIds.has(id))
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isLoading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
}

function resetFilters() {
  query.value = ''
  Object.keys(warehouseColumnFilters).forEach((key) => { warehouseColumnFilters[key] = '' })
  warehouseSortKey.value = null
  warehouseSortDirection.value = null
  currentPage.value = 1
}

function switchWarehouseListMode(mode: WarehouseListMode) {
  if (activeWarehouseListMode.value === mode) {
    return
  }

  activeWarehouseListMode.value = mode
  selectedComponentIds.value = []
  currentPage.value = 1
  isComponentCardOpen.value = false
  resetMessages()
  void loadData()
}

async function saveComponent() {
  resetMessages()

  if (!componentForm.module_name_index.trim() || !componentForm.supplier.trim()) {
    error.value = 'Заполни индекс/название и поставщика.'
    return
  }

  isSaving.value = true

  try {
    const payload = buildComponentPayload()
    const wasEditing = isEditingComponent.value
    let saved: ComponentItem
    if (wasEditing && selectedComponent.value) {
      const updatePayload: ComponentUpdatePayload = { ...payload }
      if (String(selectedComponent.value.client_id ?? '') === componentForm.client_id) {
        delete updatePayload.client_id
      }
      saved = await updateComponent(getComponentId(selectedComponent.value), updatePayload)
    } else {
      saved = await createComponent(payload)
    }

    const savedMode: WarehouseListMode = saved.is_archived ? 'archive' : saved.is_in_stock ? 'stock' : 'active'
    if (savedMode === activeWarehouseListMode.value) {
      selectComponent(saved)
    } else {
      closeComponentCard()
      resetComponentForm()
    }
    successMessage.value = wasEditing ? 'Комплектующая обновлена' : 'Комплектующая создана'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function removeComponent(item: ComponentItem) {
  if (!(await confirmAction({
    message: `Удалить комплектующую «${getComponentName(item)}»? Это действие нельзя отменить.`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteComponent(getComponentId(item))
    closeComponentCard()
    successMessage.value = 'Комплектующая удалена'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function changeComponentArchiveState(item: ComponentItem, archive: boolean) {
  const componentId = getComponentId(item)
  const action = archive ? 'Переместить в Списанные комплектующие' : 'восстановить из Списанные комплектующие'

  if (!componentId) {
    return
  }

  if (!(await confirmAction({
    header: archive ? 'Перемещение в Списанные комплектующие' : 'Восстановление',
    message: `${action[0].toUpperCase()}${action.slice(1)} комплектующую «${getComponentName(item)}»?`,
    acceptLabel: archive ? 'В Списанные комплектующие' : 'Восстановить',
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    if (archive) {
      await archiveComponent(componentId)
    } else {
      await restoreComponent(componentId)
    }

    if (selectedComponent.value && getComponentId(selectedComponent.value) === componentId) {
      closeComponentCard()
      resetComponentForm()
    }

    successMessage.value = archive
      ? 'Комплектующая перемещена в Списанные комплектующие'
      : 'Комплектующая восстановлена из Списанные комплектующие'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function changeComponentStockState(item: ComponentItem, moveToStock: boolean) {
  const componentId = getComponentId(item)
  if (!componentId) return

  const target = moveToStock ? 'Склад' : 'Рабочий склад'
  const note = moveToStock ? ' Владелец будет снят, ТСР сохранится.' : ''
  if (!(await confirmAction({
    header: moveToStock ? 'Перемещение на Склад' : 'Возврат в Рабочий склад',
    message: `Переместить комплектующую «${getComponentName(item)}» в «${target}»?${note}`,
    acceptLabel: moveToStock ? 'На Склад' : 'В Рабочий склад',
  }))) return

  isSaving.value = true
  resetMessages()
  try {
    if (moveToStock) {
      await moveComponentToStock(componentId)
    } else {
      await moveComponentToWorkStock(componentId)
    }
    if (selectedComponent.value && getComponentId(selectedComponent.value) === componentId) {
      closeComponentCard()
      resetComponentForm()
    }
    successMessage.value = moveToStock
      ? 'Комплектующая перемещена на Склад'
      : 'Комплектующая возвращена в Рабочий склад'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

function isComponentSelected(item: ComponentItem) {
  return selectedComponentIds.value.includes(getComponentId(item))
}

function toggleComponentSelection(item: ComponentItem, checked: boolean) {
  const id = getComponentId(item)
  if (!id) return
  const ids = new Set(selectedComponentIds.value)
  if (checked) ids.add(id)
  else ids.delete(id)
  selectedComponentIds.value = [...ids]
}

function toggleAllPagedComponents(checked: boolean) {
  const ids = new Set(selectedComponentIds.value)
  for (const id of pagedComponentIds.value) {
    if (checked) ids.add(id)
    else ids.delete(id)
  }
  selectedComponentIds.value = [...ids]
}

function handleToggleAllComponents(event: Event) {
  toggleAllPagedComponents((event.target as HTMLInputElement).checked)
}

function handleToggleComponent(item: ComponentItem, event: Event) {
  toggleComponentSelection(item, (event.target as HTMLInputElement).checked)
}

async function runBulkWarehouseAction(action: WarehouseBulkAction) {
  const items = selectedComponents.value
  if (!items.length) return

  const labels: Record<WarehouseBulkAction, string> = {
    stock: 'переместить на Склад',
    work: 'вернуть в Рабочий склад',
    archive: 'переместить в Списанные комплектующие',
    restore: 'восстановить',
    delete: 'удалить',
  }
  if (!(await confirmAction({
    header: 'Множественная операция',
    message: `${labels[action][0].toUpperCase()}${labels[action].slice(1)} выбранные позиции (${items.length})?`,
    acceptLabel: labels[action],
    danger: action === 'delete',
  }))) return

  isSaving.value = true
  resetMessages()
  const failures: string[] = []
  let completed = 0
  for (const item of items) {
    const id = getComponentId(item)
    try {
      if (action === 'stock') await moveComponentToStock(id)
      else if (action === 'work') await moveComponentToWorkStock(id)
      else if (action === 'archive') await archiveComponent(id)
      else if (action === 'restore') await restoreComponent(id)
      else await deleteComponent(id)
      completed += 1
    } catch (caught) {
      failures.push(`${getComponentName(item)}: ${getApiErrorMessage(caught)}`)
    }
  }

  selectedComponentIds.value = []
  if (completed) successMessage.value = `Операция выполнена для ${completed} поз.`
  if (failures.length) error.value = `Не удалось обработать ${failures.length} поз.: ${failures.join('; ')}`
  await loadData()
  isSaving.value = false
}

function goToPreviousPage() {
  if (!hasPreviousPage.value) {
    return
  }

  currentPage.value -= 1
}

function goToNextPage() {
  if (!hasMore.value) {
    return
  }

  currentPage.value += 1
}

watch(isComponentCardOpen, (isOpen) => {
  window.document.body.classList.toggle('modal-open', isOpen)
})

watch([query, pageLimit, warehouseColumnFilters], () => { currentPage.value = 1 }, { deep: true })

onMounted(async () => {
  const [activeClientResult, archivedClientResult, nameResult, tsrResult] = await Promise.allSettled([
    fetchClients({ limit: 100000, archived: false }),
    fetchClients({ limit: 100000, archived: true }),
    fetchNameIndexReferences(),
    fetchTsrReferences(),
  ])

  const activeClients = activeClientResult.status === 'fulfilled' ? activeClientResult.value : []
  const archivedClients = archivedClientResult.status === 'fulfilled' ? archivedClientResult.value : []
  clients.value = [...activeClients, ...archivedClients]
  nameIndexReferences.value = nameResult.status === 'fulfilled' ? nameResult.value : []
  tsrReferences.value = tsrResult.status === 'fulfilled' ? tsrResult.value : []
  await loadData()
})

onBeforeUnmount(() => {
  window.document.body.classList.remove('modal-open')
})
</script>

<template>
  <section class="page-section entity-workspace-page components-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Материальный учёт</p>
        <h1>Комплектующие</h1>
        <p class="muted page-subtitle">
          Остатки, закупки, себестоимость и распределение по клиентам.
        </p>
      </div>
      <button v-if="activeWarehouseListMode !== 'archive'" class="primary-button" type="button" @click="openNewComponent">
        <Plus :size="16" aria-hidden="true" />
        Добавить комплектующую
      </button>
    </div>

    <div class="tabs" role="tablist" aria-label="Разделы склада">
      <button :class="{ active: activeWarehouseListMode === 'active' }" type="button" @click="switchWarehouseListMode('active')">
        Рабочий склад
      </button>
      <button :class="{ active: activeWarehouseListMode === 'stock' }" type="button" @click="switchWarehouseListMode('stock')">
        Склад
      </button>
      <button :class="{ active: activeWarehouseListMode === 'archive' }" type="button" @click="switchWarehouseListMode('archive')">
        Списанные комплектующие
      </button>
    </div>

    <div v-if="activeWarehouseListMode === 'stock'" class="stock-summary-grid" aria-label="Итоги склада">
      <div class="stock-summary-card">
        <span>Себестоимость на складе</span>
        <strong>{{ formatMoney(stockTotalCost) }}</strong>
      </div>
      <div class="stock-summary-card">
        <span>Цена комплектующих</span>
        <strong>{{ formatMoney(stockTotalPrice) }}</strong>
      </div>
      <div class="stock-summary-card">
        <span>Единиц на складе</span>
        <strong>{{ stockTotalQuantity }}</strong>
      </div>
    </div>

    <form class="toolbar-form warehouse-toolbar" @submit.prevent="applyFilters">
      <div class="toolbar-search-wrap">
        <Search :size="17" aria-hidden="true" />
        <input v-model="query" aria-label="Поиск комплектующей" placeholder="Название, ТСР, поставщик, владелец или примечание" />
      </div>
      <label class="filter-label">
        <span>На странице</span>
        <select v-model.number="pageLimit" @change="applyFilters">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
        </select>
      </label>
      <div class="filter-actions">
        <button class="secondary-button" type="submit" :disabled="isLoading">
          <Search :size="15" aria-hidden="true" />
          Применить
        </button>
        <button v-if="activeWarehouseFilterCount" class="ghost-button" type="button" @click="resetFilters">
          <X :size="15" aria-hidden="true" />
          Сбросить
        </button>
        <span v-if="activeWarehouseFilterCount" class="filter-count">{{ activeWarehouseFilterCount }}</span>
      </div>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

    <div v-if="selectedComponentIds.length" class="bulk-action-bar">
      <strong>Выбрано: {{ selectedComponentIds.length }}</strong>
      <div class="row-actions">
        <button v-if="activeWarehouseListMode === 'active'" class="secondary-button" type="button" :disabled="isSaving" @click="runBulkWarehouseAction('stock')">На Склад</button>
        <button v-if="activeWarehouseListMode === 'stock'" class="secondary-button" type="button" :disabled="isSaving" @click="runBulkWarehouseAction('work')">В Рабочий склад</button>
        <button v-if="activeWarehouseListMode !== 'archive'" class="secondary-button" type="button" :disabled="isSaving" @click="runBulkWarehouseAction('archive')">В Списанные</button>
        <button v-else class="secondary-button" type="button" :disabled="isSaving" @click="runBulkWarehouseAction('restore')">Восстановить</button>
        <button v-if="activeWarehouseListMode !== 'archive'" class="ghost-button danger-button" type="button" :disabled="isSaving" @click="runBulkWarehouseAction('delete')">Удалить</button>
        <button class="ghost-button" type="button" :disabled="isSaving" @click="selectedComponentIds = []">Снять выбор</button>
      </div>
    </div>

    <div class="table-wrap desktop-entity-table">
      <table>
        <thead>
          <tr>
            <th class="selection-cell">
              <input
                type="checkbox"
                aria-label="Выбрать все позиции на странице"
                :checked="allPagedComponentsSelected"
                @change="handleToggleAllComponents"
              />
            </th>
            <SortableFilterHeader label="№" column-key="number" :filterable="false" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" @sort="sortWarehouse" />
            <SortableFilterHeader label="Комплектующая" column-key="name" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.name" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.name = $event" />
            <SortableFilterHeader label="Поставщик" column-key="supplier" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.supplier" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.supplier = $event" />
            <SortableFilterHeader label="Кол-во" column-key="quantity" filter-kind="number" placeholder=">= 1 или 1..10" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.quantity" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.quantity = $event" />
            <SortableFilterHeader label="Себестоимость" column-key="cost" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.cost" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.cost = $event" />
            <SortableFilterHeader label="Цена" column-key="price" filter-kind="number" placeholder="Сумма или диапазон" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.price" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.price = $event" />
            <SortableFilterHeader label="Заказ" column-key="order" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.order" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.order = $event" />
            <SortableFilterHeader label="Владелец" column-key="owner" :sort-key="warehouseSortKey" :sort-direction="warehouseSortDirection" :filter-value="warehouseColumnFilters.owner" @sort="sortWarehouse" @update:filter-value="warehouseColumnFilters.owner = $event" />
            <th aria-label="Действия"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading" class="no-row-action">
            <td colspan="10">Загружаем комплектующие...</td>
          </tr>
          <tr
            v-for="item in pagedComponents"
            v-else
            :key="item.module_id"
            :tabindex="activeWarehouseListMode !== 'archive' ? 0 : undefined"
            :class="{ 'no-row-action': activeWarehouseListMode === 'archive', selected: isComponentSelected(item) }"
            @click="activeWarehouseListMode !== 'archive' && selectComponent(item)"
            @keydown.enter="activeWarehouseListMode !== 'archive' && selectComponent(item)"
          >
            <td class="selection-cell" @click.stop>
              <input
                type="checkbox"
                :aria-label="`Выбрать: ${getComponentName(item)}`"
                :checked="isComponentSelected(item)"
                @change="handleToggleComponent(item, $event)"
              />
            </td>
            <td>{{ warehouseRowNumber(item) }}</td>
            <td class="entity-cell">
              <div class="entity-primary">
                <span class="entity-avatar">ТС</span>
                <span class="entity-copy">
                  <strong>{{ getComponentName(item) }}</strong>
                  <span v-if="activeWarehouseListMode !== 'stock'">{{ item.tsr?.full_tsr_code || 'ТСР не указан' }}</span>
                  <span class="component-attributes">{{ getComponentAttributes(item) }}</span>
                </span>
              </div>
            </td>
            <td>{{ item.supplier }}</td>
            <td>{{ item.quantity }}</td>

            <td class="table-money">
              {{ formatMoney(item.cost) }}
              ({{ formatMoney(Number(item.cost) / Number(item.quantity)) }} /шт.)
            </td>
            <td class="table-money">
              {{ formatMoney(item.price) }}
              ({{ formatMoney(Number(item.price) / Number(item.quantity)) }} /шт.)
            </td>

            <td class="order-status-cell">
              <span>Заказано <strong>{{ item.ordered }}</strong></span>
              <span>Получено <strong>{{ item.recd }}</strong></span>
              <StatusPill
                v-if="Number(item.pending || 0) > 0"
                :label="`Ожидается: ${item.pending}`"
                kind="status"
              />
            </td>
            <td>
              <StatusPill
                :label="item.client_id ? getClientLabel(item.client_id) : 'На складе'"
                :kind="item.client_id ? 'neutral' : 'status'"
              />
            </td>
            <td class="table-actions-cell">
              <ActionMenu :items="getComponentActions(item)" :label="`Действия: ${getComponentName(item)}`" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!isLoading" class="mobile-entity-list">
      <article
        v-for="item in pagedComponents"
        :key="item.module_id"
        class="mobile-entity-card"
        @click="activeWarehouseListMode !== 'archive' && selectComponent(item)"
      >
        <div class="mobile-entity-card-header">
          <div class="entity-primary">
            <span class="entity-avatar">ТС</span>
            <span class="entity-copy">
              <strong>{{ getComponentName(item) }}</strong>
              <span v-if="activeWarehouseListMode !== 'stock'">{{ item.tsr?.full_tsr_code || 'ТСР не указан' }} · {{ item.supplier }}</span>
              <span v-else>{{ item.supplier }}</span>
              <span class="component-attributes">{{ getComponentAttributes(item) }}</span>
            </span>
          </div>
          <ActionMenu :items="getComponentActions(item)" :label="`Действия: ${getComponentName(item)}`" />
        </div>
        <div class="mobile-entity-card-details">
          <span>Количество <strong>{{ item.quantity }}</strong></span>
          <span>Стоимость <strong>{{ formatMoney(item.cost) }}</strong></span>
          <span>Ожидается <strong>{{ item.pending || 0 }}</strong></span>
          <span>Владелец <strong>{{ getClientLabel(item.client_id) }}</strong></span>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!isLoading && filteredComponents.length === 0"
      title="Комплектующие не найдены"
      :description="activeWarehouseFilterCount ? 'Измените или сбросьте фильтры.' : 'Добавьте первую комплектующую на склад.'"
    />

    <div class="pagination-bar">
      <span>Страница {{ currentPage }} · показано {{ pagedComponents.length }} из {{ filteredComponents.length }}</span>
      <div class="row-actions">
        <button class="secondary-button" :disabled="!hasPreviousPage" type="button" @click="goToPreviousPage">
          Назад
        </button>
        <button class="secondary-button" :disabled="!hasMore" type="button" @click="goToNextPage">
          Вперед
        </button>
      </div>
    </div>

    <div v-if="isComponentCardOpen" class="modal-backdrop" @click.self="closeComponentCard">
      <section v-focus-trap class="modal-panel entity-modal component-profile-modal" role="dialog" aria-modal="true" aria-label="Карточка комплектующей">
        <div class="modal-header">
          <div>
            <p class="eyebrow">{{ isEditingComponent ? 'Редактирование' : 'Новая комплектующая' }}</p>
            <h2>{{ selectedComponent ? getComponentName(selectedComponent) : 'Добавить комплектующую' }}</h2>
          </div>
          <div class="row-actions">
            <button
              v-if="selectedComponent && activeWarehouseListMode !== 'archive'"
              class="secondary-button"
              type="button"
              :disabled="isSaving"
              @click="activeWarehouseListMode === 'stock' ? changeComponentStockState(selectedComponent, false) : changeComponentStockState(selectedComponent, true)"
            >
              {{ activeWarehouseListMode === 'stock' ? 'В Рабочий склад' : 'На Склад' }}
            </button>
            <button
              v-if="selectedComponent && activeWarehouseListMode !== 'archive'"
              class="secondary-button"
              type="button"
              :disabled="isSaving"
              @click="changeComponentArchiveState(selectedComponent, true)"
            >
              В Списанные комплектующие
            </button>
            <button class="ghost-button" type="button" @click="closeComponentCard">Закрыть</button>
          </div>
        </div>

        <form class="side-form flat-form" @submit.prevent="saveComponent">
          <div class="form-grid">
            <label>
              ТСР
              <select v-model="componentForm.tsr_id">
                <option value="">Не указан</option>
                <option v-for="option in tsrOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Индекс / название *
              <NameIndexAutocomplete
                v-model="componentForm.module_name_index"
                :options="nameIndexReferences
                  .map((item) => ({ value: String(item.name_index ?? '').trim(), label: String(item.name_index ?? '').trim() }))
                  .filter((option) => option.label)"
                :required="true"
                placeholder="Введите название или индекс"
              />
            </label>
            <label>
              Поставщик *
              <input v-model="componentForm.supplier" required />
            </label>
          </div>

          <div class="form-grid">
            <label>
              Количество
              <input v-model="componentForm.quantity" inputmode="numeric" />
            </label>
            <label>
              Себестоимость за ед.
              <input
                v-model="componentForm.unit_cost"
                inputmode="decimal"
                @blur="formatComponentMoneyField('unit_cost')"
              />
            </label>
            <label>
              Цена за ед.
              <input
                v-model="componentForm.unit_price"
                inputmode="decimal"
                @blur="formatComponentMoneyField('unit_price')"
              />
            </label>
          </div>

          <div class="form-grid">
            <label>
              Заказано
              <input v-model="componentForm.ordered" type="number" min="0" step="1" />
            </label>
            <label>
              Получено
              <input v-model="componentForm.recd" type="number" min="0" step="1" />
            </label>
            <label>
              Ожидается
              <input v-model="componentForm.pending" type="number" min="0" step="1" />
            </label>
            <label>
              У протезиста
              <input v-model="componentForm.prosthetist_keep" type="number" min="0" step="1" />
            </label>
          </div>

          <div class="form-grid">
            <label>
              Номер счёта и дата
              <input v-model="componentForm.order_date_acc_num" />
            </label>
            <label>
              Размер
              <input v-model="componentForm.size" />
            </label>
            <label>
              Жёсткость
              <input v-model="componentForm.stiffness" />
            </label>
            <label>
              Сторона
              <input v-model="componentForm.side" />
            </label>
          </div>

          <label>
            Клиент
            <select v-model="componentForm.client_id">
              <option value="">На складе</option>
              <option v-for="client in visibleOwnerClients" :key="String(client.client_id)" :value="client.client_id">
                {{ getClientName(client) }}
              </option>
            </select>
          </label>
          <label>
            Характеристики
            <input v-model="componentForm.properties" />
          </label>
          <label>
            Заметки
            <textarea v-model="componentForm.notes" rows="3" />
          </label>

          <button class="primary-button" :disabled="isSaving" type="submit">
            {{ isSaving ? 'Сохраняем...' : 'Сохранить комплектующую' }}
          </button>
        </form>
      </section>
    </div>
  </section>
</template>
