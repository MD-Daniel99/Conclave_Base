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
type WarehouseQuantityEntry = { item: ComponentItem; quantity: string }
type ClientTsrItem = NonNullable<Client['tsr_items']>[number]

type ComponentForm = {
  tsr_id: string
  client_tsr_id: string
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
  client_tsr_id: '',
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
const componentCardOperationQuantity = ref('1')
const quantityActionDialog = reactive<{ open: boolean; action: WarehouseBulkAction; entries: WarehouseQuantityEntry[] }>({
  open: false,
  action: 'stock',
  entries: [],
})
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
const selectedComponentAvailableQuantity = computed(() => (
  selectedComponent.value ? getAvailableComponentQuantity(selectedComponent.value) : 1
))
const componentOwnerChanged = computed(() => Boolean(
  selectedComponent.value
  && String(selectedComponent.value.client_id ?? '') !== String(componentForm.client_id ?? ''),
))
const selectedOwnerClient = computed(() => (
  clients.value.find((client) => String(client.client_id) === String(componentForm.client_id)) ?? null
))
const selectedOwnerClientTsrItems = computed<ClientTsrItem[]>(() => (
  [...(selectedOwnerClient.value?.tsr_items ?? [])].sort((left, right) => {
    const leftCreated = String(left.created_at ?? '')
    const rightCreated = String(right.created_at ?? '')
    return leftCreated.localeCompare(rightCreated)
      || String(left.client_tsr_id).localeCompare(String(right.client_tsr_id))
  })
))
const selectedOwnerClientTsr = computed(() => (
  selectedOwnerClientTsrItems.value.find(
    (item) => String(item.client_tsr_id) === String(componentForm.client_tsr_id),
  ) ?? null
))
const componentAssignmentChanged = computed(() => Boolean(
  selectedComponent.value
  && (
    componentOwnerChanged.value
    || (
      componentForm.client_id
      && String(selectedComponent.value.client_tsr_id ?? '') !== String(componentForm.client_tsr_id ?? '')
    )
  ),
))
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
        action: () => requestWarehouseItemAction(item, 'stock'),
      },
      {
        label: 'Переместить в Списанные комплектующие',
        icon: Archive,
        disabled: isSaving.value,
        action: () => requestWarehouseItemAction(item, 'archive'),
      },
      {
        label: 'Удалить',
        icon: Trash2,
        danger: true,
        disabled: isSaving.value,
        action: () => requestWarehouseItemAction(item, 'delete'),
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
        action: () => requestWarehouseItemAction(item, 'work'),
      },
      {
        label: 'Переместить в Списанные комплектующие',
        icon: Archive,
        disabled: isSaving.value,
        action: () => requestWarehouseItemAction(item, 'archive'),
      },
      {
        label: 'Удалить',
        icon: Trash2,
        danger: true,
        disabled: isSaving.value,
        action: () => requestWarehouseItemAction(item, 'delete'),
      },
    ]
  }

  if (item.is_manually_archived && !isComponentOwnerArchived(item)) {
    return [
      {
        label: 'Восстановить',
        icon: RotateCcw,
        disabled: isSaving.value,
        action: () => requestWarehouseItemAction(item, 'restore'),
      },
    ]
  }

  return [{
    label: 'В архиве вместе с клиентом',
    disabled: true,
    action: () => undefined,
  }]
}

function getAvailableComponentQuantity(item: ComponentItem) {
  return Math.max(1, Math.trunc(Number(item.quantity ?? 1) || 1))
}

function getComponentUnitMoney(total: unknown, item: ComponentItem) {
  if (total === null || total === undefined || total === '') return '—'
  return formatMoney(Number(total) / getAvailableComponentQuantity(item))
}

function parseOperationQuantity(value: string | number, item: ComponentItem) {
  const available = getAvailableComponentQuantity(item)
  const parsed = Math.trunc(Number(value))
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > available) {
    throw new Error(`Укажите количество от 1 до ${available}.`)
  }
  return parsed
}

function getWarehouseActionLabel(action: WarehouseBulkAction) {
  const labels: Record<WarehouseBulkAction, string> = {
    stock: 'Переместить на Склад',
    work: 'Вернуть в Рабочий склад',
    archive: 'Переместить в Списанные комплектующие',
    restore: 'Восстановить',
    delete: 'Удалить',
  }
  return labels[action]
}

function setQuantityDialogEntry(entry: WarehouseQuantityEntry, value: string | number) {
  const available = getAvailableComponentQuantity(entry.item)
  const parsed = Math.max(1, Math.min(available, Math.trunc(Number(value) || 1)))
  entry.quantity = String(parsed)
}

function closeQuantityActionDialog() {
  quantityActionDialog.open = false
  quantityActionDialog.entries = []
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

function getClientTsrId(item: ClientTsrItem) {
  return String(item.tsr_id ?? item.tsr?.id ?? item.tsr?.tsr_id ?? '')
}

function formatClientTsrDate(value?: string | null) {
  if (!value) return 'дата не указана'
  const [year, month, day] = String(value).slice(0, 10).split('-')
  if (!year || !month || !day) return String(value)
  return `${day}.${month}.${year}`
}

function getClientTsrOptionLabel(item: ClientTsrItem) {
  const code = String(item.tsr?.full_tsr_code ?? 'ТСР без кода')
  const details = [`пробитие ${formatClientTsrDate(item.check_date)}`]
  if (item.certificate_price != null && String(item.certificate_price).trim()) {
    details.push(`сертификат ${formatMoney(Number(item.certificate_price))}`)
  }
  return `${code} · ${details.join(' · ')}`
}

function applyClientTsrSelection(item: ClientTsrItem) {
  componentForm.client_tsr_id = String(item.client_tsr_id)
  const tsrId = getClientTsrId(item)
  if (tsrId) componentForm.tsr_id = tsrId
}

function handleComponentOwnerChange() {
  componentForm.client_tsr_id = ''
  if (!componentForm.client_id) return

  const options = selectedOwnerClientTsrItems.value
  const matchingCurrentTsr = componentForm.tsr_id
    ? options.filter((item) => getClientTsrId(item) === componentForm.tsr_id)
    : []

  if (matchingCurrentTsr.length === 1) {
    applyClientTsrSelection(matchingCurrentTsr[0])
  } else if (!componentForm.tsr_id && options.length === 1) {
    applyClientTsrSelection(options[0])
  }
}

function handleComponentClientTsrChange() {
  const assignment = selectedOwnerClientTsr.value
  if (!assignment) return
  const tsrId = getClientTsrId(assignment)
  if (tsrId) componentForm.tsr_id = tsrId
}

function handleComponentTsrChange() {
  const assignment = selectedOwnerClientTsr.value
  if (assignment && getClientTsrId(assignment) !== componentForm.tsr_id) {
    componentForm.client_tsr_id = ''
  }
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
  componentCardOperationQuantity.value = '1'
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
  componentCardOperationQuantity.value = '1'
  const quantity = Number(item.quantity ?? 1) || 1

  Object.assign(componentForm, {
    tsr_id: String(item.tsr_id ?? item.tsr?.id ?? ''),
    client_tsr_id: String(item.client_tsr_id ?? ''),
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
    client_tsr_id: componentForm.client_id && componentForm.client_tsr_id
      ? componentForm.client_tsr_id
      : null,
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

  if (
    componentForm.client_id
    && selectedOwnerClientTsrItems.value.length > 0
    && !componentForm.client_tsr_id
  ) {
    error.value = 'Выберите ТСР пациента для привязки комплектующей.'
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
      let operationQuantity: number | undefined
      if (componentAssignmentChanged.value) {
        operationQuantity = parseOperationQuantity(componentCardOperationQuantity.value, selectedComponent.value)
      }
      saved = await updateComponent(getComponentId(selectedComponent.value), updatePayload, operationQuantity)
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

async function performWarehouseItemAction(item: ComponentItem, action: WarehouseBulkAction, quantity: number) {
  const id = getComponentId(item)
  if (!id) return

  if (action === 'stock') await moveComponentToStock(id, quantity)
  else if (action === 'work') await moveComponentToWorkStock(id, quantity)
  else if (action === 'archive') await archiveComponent(id, quantity)
  else if (action === 'restore') await restoreComponent(id, quantity)
  else await deleteComponent(id, quantity)
}

async function executeSingleWarehouseAction(item: ComponentItem, action: WarehouseBulkAction, quantity = 1) {
  const label = getWarehouseActionLabel(action)
  const suffix = quantity > 1 ? ` (${quantity} шт.)` : ''
  if (!(await confirmAction({
    header: label,
    message: `${label} «${getComponentName(item)}»${suffix}?`,
    acceptLabel: label,
    danger: action === 'delete',
  }))) return

  isSaving.value = true
  resetMessages()
  try {
    await performWarehouseItemAction(item, action, quantity)
    if (selectedComponent.value && getComponentId(selectedComponent.value) === getComponentId(item)) {
      closeComponentCard()
      resetComponentForm()
    }
    successMessage.value = `${label}: ${quantity} шт.`
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

function requestWarehouseItemAction(item: ComponentItem, action: WarehouseBulkAction) {
  const available = getAvailableComponentQuantity(item)
  if (available <= 1) {
    void executeSingleWarehouseAction(item, action, 1)
    return
  }

  quantityActionDialog.action = action
  quantityActionDialog.entries = [{ item, quantity: '1' }]
  quantityActionDialog.open = true
}

async function executeWarehouseQuantityDialog() {
  const action = quantityActionDialog.action
  const entries = [...quantityActionDialog.entries]
  if (!entries.length) return

  const requests: Array<{ item: ComponentItem; quantity: number }> = []
  try {
    for (const entry of entries) {
      requests.push({ item: entry.item, quantity: parseOperationQuantity(entry.quantity, entry.item) })
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Проверьте количество для операции.'
    return
  }

  closeQuantityActionDialog()
  isSaving.value = true
  resetMessages()
  const failures: string[] = []
  let completedUnits = 0

  for (const request of requests) {
    try {
      await performWarehouseItemAction(request.item, action, request.quantity)
      completedUnits += request.quantity
    } catch (caught) {
      failures.push(`${getComponentName(request.item)}: ${getApiErrorMessage(caught)}`)
    }
  }

  selectedComponentIds.value = []
  if (selectedComponent.value && requests.some((entry) => getComponentId(entry.item) === getComponentId(selectedComponent.value!))) {
    closeComponentCard()
    resetComponentForm()
  }
  if (completedUnits) successMessage.value = `${getWarehouseActionLabel(action)}: ${completedUnits} шт.`
  if (failures.length) error.value = `Не удалось обработать ${failures.length} поз.: ${failures.join('; ')}`
  await loadData()
  isSaving.value = false
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

  if (items.some((item) => getAvailableComponentQuantity(item) > 1)) {
    quantityActionDialog.action = action
    quantityActionDialog.entries = items.map((item) => ({ item, quantity: '1' }))
    quantityActionDialog.open = true
    return
  }

  if (!(await confirmAction({
    header: 'Множественная операция',
    message: `${getWarehouseActionLabel(action)} выбранные позиции (${items.length})?`,
    acceptLabel: getWarehouseActionLabel(action),
    danger: action === 'delete',
  }))) return

  quantityActionDialog.action = action
  quantityActionDialog.entries = items.map((item) => ({ item, quantity: '1' }))
  await executeWarehouseQuantityDialog()
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

watch([isComponentCardOpen, () => quantityActionDialog.open], ([isCardOpen, isQuantityOpen]) => {
  window.document.body.classList.toggle('modal-open', isCardOpen || isQuantityOpen)
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
              <span>{{ formatMoney(item.cost) }}</span>
              <small v-if="getAvailableComponentQuantity(item) > 1" class="table-money-unit">
                ({{ getComponentUnitMoney(item.cost, item) }} / шт.)
              </small>
            </td>
            <td class="table-money">
              <span>{{ formatMoney(item.price) }}</span>
              <small v-if="getAvailableComponentQuantity(item) > 1" class="table-money-unit">
                ({{ getComponentUnitMoney(item.price, item) }} / шт.)
              </small>
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
              @click="requestWarehouseItemAction(selectedComponent, activeWarehouseListMode === 'stock' ? 'work' : 'stock')"
            >
              {{ activeWarehouseListMode === 'stock' ? 'В Рабочий склад' : 'На Склад' }}
            </button>
            <button
              v-if="selectedComponent && activeWarehouseListMode !== 'archive'"
              class="secondary-button"
              type="button"
              :disabled="isSaving"
              @click="requestWarehouseItemAction(selectedComponent, 'archive')"
            >
              В Списанные комплектующие
            </button>
            <button
              v-if="selectedComponent && activeWarehouseListMode !== 'archive'"
              class="ghost-button danger-button"
              type="button"
              :disabled="isSaving"
              @click="requestWarehouseItemAction(selectedComponent, 'delete')"
            >
              Удалить
            </button>
            <button class="ghost-button" type="button" @click="closeComponentCard">Закрыть</button>
          </div>
        </div>

        <form class="side-form flat-form" @submit.prevent="saveComponent">
          <div class="form-grid">
            <label>
              ТСР комплектующей
              <select v-model="componentForm.tsr_id" @change="handleComponentTsrChange">
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

          <section class="warehouse-client-assignment-panel" aria-label="Привязка комплектующей к пациенту">
            <div class="warehouse-client-assignment-heading">
              <div>
                <strong>Привязка к пациенту</strong>
                <span>Выберите пациента и, если у него есть ТСР, конкретную карточку ТСР.</span>
              </div>
              <span v-if="componentForm.client_id" class="warehouse-client-assignment-status">Пациент выбран</span>
            </div>

            <div class="warehouse-client-assignment-grid">
              <label>
                Клиент
                <select v-model="componentForm.client_id" @change="handleComponentOwnerChange">
                  <option value="">На складе</option>
                  <option v-for="client in visibleOwnerClients" :key="String(client.client_id)" :value="client.client_id">
                    {{ getClientName(client) }}
                  </option>
                </select>
              </label>

              <label v-if="componentForm.client_id && selectedOwnerClientTsrItems.length">
                ТСР пациента *
                <select v-model="componentForm.client_tsr_id" required @change="handleComponentClientTsrChange">
                  <option value="">Выберите ТСР пациента</option>
                  <option
                    v-for="item in selectedOwnerClientTsrItems"
                    :key="String(item.client_tsr_id)"
                    :value="item.client_tsr_id"
                  >
                    {{ getClientTsrOptionLabel(item) }}
                  </option>
                </select>
                <small class="form-hint">При одинаковых кодах ориентируйтесь на дату пробития и стоимость сертификата.</small>
              </label>

              <div v-else-if="componentForm.client_id" class="warehouse-client-tsr-empty">
                <span>ТСР пациента</span>
                <strong>У пациента пока нет ТСР</strong>
                <small>Комплектующую можно сохранить за пациентом без выбора конкретной карточки ТСР.</small>
              </div>
            </div>

            <div v-if="selectedOwnerClientTsr" class="warehouse-client-tsr-context" aria-live="polite">
              <span>Выбранный ТСР</span>
              <strong>{{ selectedOwnerClientTsr.tsr?.full_tsr_code || 'ТСР без кода' }}</strong>
              <div>
                <span>Дата пробития: {{ formatClientTsrDate(selectedOwnerClientTsr.check_date) }}</span>
                <span v-if="selectedOwnerClientTsr.certificate_price != null && String(selectedOwnerClientTsr.certificate_price).trim()">
                  Сертификат: {{ formatMoney(Number(selectedOwnerClientTsr.certificate_price)) }}
                </span>
              </div>
            </div>

            <label v-if="selectedComponent && componentAssignmentChanged && selectedComponentAvailableQuantity > 1" class="operation-quantity-field warehouse-client-quantity-field">
              Количество для назначения
              <div class="inline-quantity-picker">
                <input
                  v-model="componentCardOperationQuantity"
                  type="number"
                  min="1"
                  :max="selectedComponentAvailableQuantity"
                  step="1"
                />
                <button class="ghost-button" type="button" @click="componentCardOperationQuantity = '1'">1</button>
                <button class="ghost-button" type="button" @click="componentCardOperationQuantity = String(selectedComponentAvailableQuantity)">Все</button>
                <span class="muted">из {{ selectedComponentAvailableQuantity }} шт.</span>
              </div>
              <small class="form-hint">Остаток сохранит текущего владельца и прежнюю привязку к ТСР.</small>
            </label>
          </section>
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

    <div v-if="quantityActionDialog.open" class="modal-backdrop" @click.self="closeQuantityActionDialog">
      <section v-focus-trap class="modal-panel quantity-operation-modal" role="dialog" aria-modal="true" aria-label="Количество комплектующих для операции">
        <div class="modal-header">
          <div>
            <p class="eyebrow">Операция с комплектующими</p>
            <h2>{{ getWarehouseActionLabel(quantityActionDialog.action) }}</h2>
            <p class="muted">Для каждой позиции укажите, сколько одинаковых единиц обработать. Остаток останется в текущем состоянии.</p>
          </div>
          <button class="ghost-button" type="button" @click="closeQuantityActionDialog">Закрыть</button>
        </div>

        <div class="quantity-operation-list">
          <div v-for="entry in quantityActionDialog.entries" :key="getComponentId(entry.item)" class="quantity-operation-row">
            <div>
              <strong>{{ getComponentName(entry.item) }}</strong>
              <span class="muted">{{ getComponentAttributes(entry.item) }} · доступно {{ getAvailableComponentQuantity(entry.item) }} шт.</span>
            </div>
            <div class="quantity-operation-picker">
              <button class="ghost-button" type="button" @click="setQuantityDialogEntry(entry, 1)">1</button>
              <input
                v-model="entry.quantity"
                type="number"
                min="1"
                :max="getAvailableComponentQuantity(entry.item)"
                step="1"
                aria-label="Количество для операции"
              />
              <button class="ghost-button" type="button" @click="setQuantityDialogEntry(entry, getAvailableComponentQuantity(entry.item))">Все</button>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeQuantityActionDialog">Отмена</button>
          <button
            :class="quantityActionDialog.action === 'delete' ? 'danger-button' : 'primary-button'"
            type="button"
            :disabled="isSaving"
            @click="executeWarehouseQuantityDialog"
          >
            {{ getWarehouseActionLabel(quantityActionDialog.action) }}
          </button>
        </div>
      </section>
    </div>
  </section>
</template>
