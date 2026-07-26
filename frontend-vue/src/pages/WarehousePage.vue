<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchClients } from '@/shared/api/clients'
import {
  archiveComponent,
  createComponent,
  deleteComponent,
  fetchComponents,
  restoreComponent,
  updateComponent,
} from '@/shared/api/components'
import { getApiErrorMessage } from '@/shared/api/http'
import { fetchNameIndexReferences, fetchTsrReferences } from '@/shared/api/references'
import { formatMoney, formatMoneyInput } from '@/shared/lib/money'
import type {
  Client,
  ComponentCreatePayload,
  ComponentItem,
  ComponentUpdatePayload,
  ReferenceItem,
} from '@/shared/types/entities'

type CountInput = string | number
type WarehouseListMode = 'active' | 'archive'

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
const supplierQuery = ref('')
const ownerFilter = ref('')
const pageLimit = ref(100)
const currentPage = ref(1)
const hasMore = ref(false)
const activeWarehouseListMode = ref<WarehouseListMode>('active')
const componentForm = reactive<ComponentForm>({ ...emptyComponentForm })
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const successMessage = ref('')

const isEditingComponent = computed(() => Boolean(selectedComponent.value?.module_id))
const currentSkip = computed(() => (currentPage.value - 1) * pageLimit.value)
const hasPreviousPage = computed(() => currentPage.value > 1)
const componentQuantity = computed(() => Math.max(1, Math.trunc(toNumber(componentForm.quantity, 1))))
const componentTotalCost = computed(() => (toOptionalNumber(componentForm.unit_cost) ?? 0) * componentQuantity.value)
const componentTotalPrice = computed(() => (toOptionalNumber(componentForm.unit_price) ?? 0) * componentQuantity.value)
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

function resetMessages() {
  error.value = ''
  successMessage.value = ''
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

function getReferenceValue(item: ReferenceItem) {
  return String(item.name_index ?? item.name ?? item.description ?? '')
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
    tsr_id: componentForm.tsr_id,
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
    const data = await fetchComponents({
      skip: currentSkip.value,
      limit: pageLimit.value + 1,
      q: query.value.trim() || undefined,
      supplier: supplierQuery.value.trim() || undefined,
      client_id: ownerFilter.value && ownerFilter.value !== '__stock__' ? ownerFilter.value : undefined,
      unassigned: ownerFilter.value === '__stock__' || undefined,
      archived: activeWarehouseListMode.value === 'archive',
    })

    hasMore.value = data.length > pageLimit.value
    components.value = data.slice(0, pageLimit.value)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
    hasMore.value = false
  } finally {
    isLoading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  void loadData()
}

function switchWarehouseListMode(mode: WarehouseListMode) {
  if (activeWarehouseListMode.value === mode) {
    return
  }

  activeWarehouseListMode.value = mode
  currentPage.value = 1
  ownerFilter.value = ''
  isComponentCardOpen.value = false
  resetMessages()
  void loadData()
}

async function saveComponent() {
  resetMessages()

  if (!componentForm.tsr_id) {
    error.value = 'Выбери ТСР для комплектующей.'
    return
  }

  if (!componentForm.module_name_index.trim() || !componentForm.supplier.trim()) {
    error.value = 'Заполни индекс/название и поставщика.'
    return
  }

  isSaving.value = true

  try {
    const payload = buildComponentPayload()
    const wasEditing = isEditingComponent.value
    const saved = wasEditing && selectedComponent.value
      ? await updateComponent(getComponentId(selectedComponent.value), payload as ComponentUpdatePayload)
      : await createComponent(payload)

    selectComponent(saved)
    successMessage.value = wasEditing ? 'Комплектующая обновлена' : 'Комплектующая создана'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function removeComponent(item: ComponentItem) {
  if (!window.confirm(`Удалить комплектующую «${getComponentName(item)}»?`)) {
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
  const action = archive ? 'переместить в архив' : 'восстановить из архива'

  if (!componentId || !window.confirm(
    `${action[0].toUpperCase()}${action.slice(1)} комплектующую «${getComponentName(item)}»?`,
  )) {
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
      ? 'Комплектующая перемещена в архив'
      : 'Комплектующая восстановлена из архива'
    await loadData()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

function goToPreviousPage() {
  if (!hasPreviousPage.value) {
    return
  }

  currentPage.value -= 1
  void loadData()
}

function goToNextPage() {
  if (!hasMore.value) {
    return
  }

  currentPage.value += 1
  void loadData()
}

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
</script>

<template>
  <section class="page-section">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Склад</p>
        <h1>Комплектующие</h1>
      </div>
      <button v-if="activeWarehouseListMode === 'active'" class="primary-button" type="button" @click="openNewComponent">
        Добавить комплектующую
      </button>
    </div>

    <div class="tabs" role="tablist" aria-label="Разделы склада">
      <button :class="{ active: activeWarehouseListMode === 'active' }" type="button" @click="switchWarehouseListMode('active')">
        Рабочий склад
      </button>
      <button :class="{ active: activeWarehouseListMode === 'archive' }" type="button" @click="switchWarehouseListMode('archive')">
        Архив
      </button>
    </div>

    <form class="toolbar-form warehouse-toolbar" @submit.prevent="applyFilters">
      <input v-model="query" placeholder="Индекс или название" />
      <input v-model="supplierQuery" placeholder="Поставщик" />
      <select v-model="ownerFilter">
        <option value="">Все владельцы</option>
        <option v-if="activeWarehouseListMode === 'active'" value="__stock__">На складе</option>
        <option v-for="client in visibleOwnerClients" :key="String(client.client_id)" :value="client.client_id">
          {{ getClientName(client) }}
        </option>
      </select>
      <label class="compact-field">
        На странице
        <select v-model.number="pageLimit" @change="applyFilters">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
        </select>
      </label>
      <button class="secondary-button" type="submit">Найти</button>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>№</th>
            <th>Индекс / название</th>
            <th>ТСР</th>
            <th>Поставщик</th>
            <th>Кол-во</th>
            <th>Себестоимость</th>
            <th>Цена</th>
            <th>Заказано</th>
            <th>Получено</th>
            <th>Ожидается</th>
            <th>Владелец</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="isLoading">
            <td colspan="12">Загружаем комплектующие...</td>
          </tr>
          <tr v-for="(item, index) in components" v-else :key="item.module_id">
            <td>{{ currentSkip + index + 1 }}</td>
            <td>
              <button
                v-if="activeWarehouseListMode === 'active'"
                class="link-button"
                type="button"
                @click="selectComponent(item)"
              >
                {{ getComponentName(item) }}
              </button>
              <span v-else>{{ getComponentName(item) }}</span>
            </td>
            <td>{{ item.tsr?.full_tsr_code || '—' }}</td>
            <td>{{ item.supplier }}</td>
            <td>{{ item.quantity }}</td>
            <td class="table-money">{{ formatMoney(item.cost) }}</td>
            <td class="table-money">{{ formatMoney(item.price) }}</td>
            <td>{{ item.ordered }}</td>
            <td>{{ item.recd }}</td>
            <td>{{ item.pending }}</td>
            <td>{{ getClientLabel(item.client_id) }}</td>
            <td class="row-actions">
              <template v-if="activeWarehouseListMode === 'active'">
                <button class="ghost-button" type="button" @click="selectComponent(item)">Открыть</button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="isSaving"
                  @click="changeComponentArchiveState(item, true)"
                >
                  В архив
                </button>
                <button class="danger-button" type="button" @click="removeComponent(item)">Удалить</button>
              </template>
              <button
                v-else-if="item.is_manually_archived && !isComponentOwnerArchived(item)"
                class="secondary-button"
                type="button"
                :disabled="isSaving"
                @click="changeComponentArchiveState(item, false)"
              >
                Восстановить
              </button>
              <span v-else class="muted">В архиве вместе с клиентом</span>
            </td>
          </tr>
          <tr v-if="!isLoading && components.length === 0">
            <td colspan="12">Комплектующие не найдены.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination-bar">
      <span>Страница {{ currentPage }}</span>
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
      <section class="modal-panel">
        <div class="modal-header">
          <div>
            <p class="eyebrow">{{ isEditingComponent ? 'Редактирование' : 'Новая комплектующая' }}</p>
            <h2>{{ selectedComponent ? getComponentName(selectedComponent) : 'Добавить комплектующую' }}</h2>
          </div>
          <div class="row-actions">
            <button
              v-if="selectedComponent && activeWarehouseListMode === 'active'"
              class="secondary-button"
              type="button"
              :disabled="isSaving"
              @click="changeComponentArchiveState(selectedComponent, true)"
            >
              В архив
            </button>
            <button class="ghost-button" type="button" @click="closeComponentCard">Закрыть</button>
          </div>
        </div>

        <form class="side-form flat-form" @submit.prevent="saveComponent">
          <div class="form-grid">
            <label>
              ТСР *
              <select v-model="componentForm.tsr_id" required>
                <option value="">Выбери ТСР</option>
                <option v-for="option in tsrOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              Индекс / название *
              <input v-model="componentForm.module_name_index" list="component-index-list" required />
              <datalist id="component-index-list">
                <option
                  v-for="item in nameIndexReferences"
                  :key="String(item.id ?? item.name_index_id)"
                  :value="getReferenceValue(item)"
                />
              </datalist>
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
