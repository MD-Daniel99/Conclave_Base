<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { formatMoney, formatMoneyInput } from '@/shared/lib/money'
import { fetchClients } from '@/shared/api/clients'
import { createComponent, deleteComponent, fetchComponents, updateComponent } from '@/shared/api/components'
import { getApiErrorMessage } from '@/shared/api/http'
import { createModule, deleteModule, fetchModules, updateModule } from '@/shared/api/modules'
import { fetchNameIndexReferences, fetchTsrReferences } from '@/shared/api/references'
import type {
  Client,
  ModuleComponentItem,
  ModuleComponentPayload,
  ModuleCreatePayload,
  ModuleItem,
  ModuleUpdatePayload,
  ReferenceItem,
} from '@/shared/types/entities'

type WarehouseTab = 'modules' | 'components'
type ModuleForm = {
  tsr_id: string; module_name_index: string; supplier: string; ordered: string; order_date_acc_num: string
  quantity: string; size: string; stiffness: string; side: string; unit_cost: string; unit_price: string
  recd: string; pending: string; prosthetist_keep: string; properties: string; client_id: string; notes: string
}
type ComponentForm = {
  component_index: string; module_id: string; supplier: string; quantity: string; cost: string; price: string
  ordered: string; received: string; pending: string; notes: string
}

const emptyModuleForm: ModuleForm = {
  tsr_id: '', module_name_index: '', supplier: '', ordered: '0', order_date_acc_num: '-', quantity: '1',
  size: '', stiffness: '', side: '', unit_cost: '', unit_price: '', recd: '0', pending: '0',
  prosthetist_keep: '0', properties: '-', client_id: '', notes: '',
}
const emptyComponentForm: ComponentForm = {
  component_index: '', module_id: '', supplier: '', quantity: '1', cost: '', price: '', ordered: '0',
  received: '0', pending: '0', notes: '',
}

const activeTab = ref<WarehouseTab>('modules')
const modules = ref<ModuleItem[]>([])
const components = ref<ModuleComponentItem[]>([])
const moduleOptions = ref<ModuleItem[]>([])
const allComponents = ref<ModuleComponentItem[]>([])
const clients = ref<Client[]>([])
const nameIndexReferences = ref<ReferenceItem[]>([])
const tsrReferences = ref<ReferenceItem[]>([])
const selectedModule = ref<ModuleItem | null>(null)
const selectedComponent = ref<ModuleComponentItem | null>(null)
const isModuleCardOpen = ref(false)
const isComponentCardOpen = ref(false)
const query = ref('')
const supplierQuery = ref('')
const ownerFilter = ref('')
const moduleFilter = ref('')
const pageLimit = ref(100)
const currentPage = ref(1)
const hasMore = ref(false)
const moduleForm = reactive<ModuleForm>({ ...emptyModuleForm })
const componentForm = reactive<ComponentForm>({ ...emptyComponentForm })
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const successMessage = ref('')

const isEditingModule = computed(() => Boolean(selectedModule.value?.module_id))
const isEditingComponent = computed(() => Boolean(selectedComponent.value?.component_id))
const currentSkip = computed(() => (currentPage.value - 1) * pageLimit.value)
const hasPreviousPage = computed(() => currentPage.value > 1)
const moduleQuantity = computed(() => Math.max(1, Math.trunc(toNumber(moduleForm.quantity, 1))))
const moduleTotalCost = computed(() => (toOptionalNumber(moduleForm.unit_cost) ?? 0) * moduleQuantity.value)
const moduleTotalPrice = computed(() => (toOptionalNumber(moduleForm.unit_price) ?? 0) * moduleQuantity.value)
const selectedModuleComponents = computed(() => {
  const id = selectedModule.value?.module_id
  return id ? allComponents.value.filter((item) => item.module_id === id) : []
})
const tsrOptions = computed(() => tsrReferences.value.map((item) => ({
  value: String(item.id ?? item.tsr_id ?? ''),
  label: String(item.full_tsr_code ?? ''),
})).filter((item) => item.value && item.label))

function resetMessages() { error.value = ''; successMessage.value = '' }
function toNumber(value: string, fallback = 0) { const n = Number(value.trim().replace(',', '.')); return Number.isFinite(n) ? n : fallback }
function toCount(value: string) { return Math.max(0, Math.trunc(toNumber(value, 0))) }
function toOptionalNumber(value: string) {
  const normalized = value.trim().replace(/[\s\u00a0\u202f]/g, '').replace(',', '.').replace(/[^\d.-]/g, '')
  const n = Number(normalized); return normalized && Number.isFinite(n) ? n : undefined
}
function optional(value: string) { return value.trim() || null }
function required(value: string, fallback: string) { return value.trim() || fallback }
function formatModuleMoneyField(field: 'unit_cost' | 'unit_price') { moduleForm[field] = formatMoneyInput(moduleForm[field]) }
function formatComponentMoneyField(field: 'cost' | 'price') { componentForm[field] = formatMoneyInput(componentForm[field]) }
function getModuleId(item: ModuleItem) { return String(item.module_id ?? '') }
function getModuleName(item: ModuleItem) { return item.module_name_index || item.properties || 'Без названия' }
function getClientName(client: Client) { return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ') || 'Без имени' }
function getClientLabel(clientId?: string | null) {
  if (!clientId) return 'На складе'
  const client = clients.value.find((item) => item.client_id === clientId)
  return client ? getClientName(client) : clientId
}
function getComponentClient(item: ModuleComponentItem) {
  const client = item.module?.client
  return client
    ? [client.last_name, client.first_name].filter(Boolean).join(' ') || 'Без имени'
    : getClientLabel(item.module?.client_id)
}
function getReferenceValue(item: ReferenceItem) { return String(item.name_index ?? item.name ?? item.description ?? '') }

function resetModuleForm() { Object.assign(moduleForm, emptyModuleForm); selectedModule.value = null; resetMessages() }
function resetComponentForm() { Object.assign(componentForm, emptyComponentForm); selectedComponent.value = null; resetMessages() }
function openNewModule() { resetModuleForm(); isModuleCardOpen.value = true }
function openNewComponent(moduleId = '') { resetComponentForm(); componentForm.module_id = moduleId; isComponentCardOpen.value = true }
function closeCards() { isModuleCardOpen.value = false; isComponentCardOpen.value = false }

function selectModule(item: ModuleItem) {
  selectedModule.value = item
  const quantity = Number(item.quantity ?? 1) || 1
  Object.assign(moduleForm, {
    tsr_id: String(item.tsr_id ?? item.tsr?.id ?? ''), module_name_index: item.module_name_index ?? '',
    supplier: item.supplier ?? '', ordered: String(item.ordered ?? 0), order_date_acc_num: item.order_date_acc_num ?? '',
    quantity: String(quantity), size: item.size ?? '', stiffness: item.stiffness ?? '', side: item.side ?? '',
    unit_cost: item.cost ? String(Number(item.cost) / quantity) : '', unit_price: item.price ? String(Number(item.price) / quantity) : '',
    recd: String(item.recd ?? 0), pending: String(item.pending ?? 0), prosthetist_keep: String(item.prosthetist_keep ?? 0),
    properties: item.properties ?? '', client_id: item.client_id ?? '', notes: item.notes ?? '',
  })
  isModuleCardOpen.value = true; resetMessages()
}

function selectComponent(item: ModuleComponentItem) {
  selectedComponent.value = item
  Object.assign(componentForm, {
    component_index: item.component_index, module_id: item.module_id ?? '', supplier: item.supplier,
    quantity: String(item.quantity ?? 1), cost: String(item.cost ?? ''), price: String(item.price ?? ''),
    ordered: item.ordered ?? '0', received: item.received ?? '0', pending: item.pending ?? '0', notes: item.notes ?? '',
  })
  isComponentCardOpen.value = true; resetMessages()
}

function buildModulePayload(): ModuleCreatePayload {
  return {
    tsr_id: moduleForm.tsr_id, client_id: moduleForm.client_id || null,
    module_name_index: moduleForm.module_name_index.trim(), supplier: moduleForm.supplier.trim(),
    ordered: toCount(moduleForm.ordered), order_date_acc_num: required(moduleForm.order_date_acc_num, '-'),
    quantity: moduleQuantity.value, size: optional(moduleForm.size), stiffness: optional(moduleForm.stiffness), side: optional(moduleForm.side),
    cost: moduleTotalCost.value, price: moduleTotalPrice.value, recd: toCount(moduleForm.recd),
    pending: toCount(moduleForm.pending), prosthetist_keep: toCount(moduleForm.prosthetist_keep),
    properties: required(moduleForm.properties, '-'), notes: optional(moduleForm.notes),
  }
}
function buildComponentPayload(): ModuleComponentPayload {
  return {
    component_index: componentForm.component_index.trim(), module_id: componentForm.module_id || null,
    supplier: componentForm.supplier.trim(), quantity: Math.max(1, Math.trunc(toNumber(componentForm.quantity, 1))),
    cost: toOptionalNumber(componentForm.cost) ?? 0, price: toOptionalNumber(componentForm.price) ?? 0,
    ordered: required(componentForm.ordered, '0'), received: required(componentForm.received, '0'),
    pending: required(componentForm.pending, '0'), notes: optional(componentForm.notes),
  }
}

async function loadData() {
  isLoading.value = true; error.value = ''
  try {
    if (activeTab.value === 'modules') {
      const data = await fetchModules({
        skip: currentSkip.value, limit: pageLimit.value + 1, q: query.value.trim() || undefined,
        supplier: supplierQuery.value.trim() || undefined,
        client_id: ownerFilter.value && ownerFilter.value !== '__stock__' ? ownerFilter.value : undefined,
        unassigned: ownerFilter.value === '__stock__' || undefined,
      })
      hasMore.value = data.length > pageLimit.value; modules.value = data.slice(0, pageLimit.value)
    } else {
      const data = await fetchComponents({
        skip: currentSkip.value, limit: pageLimit.value + 1, q: query.value.trim() || undefined,
        supplier: supplierQuery.value.trim() || undefined,
        module_id: moduleFilter.value && moduleFilter.value !== '__stock__' ? moduleFilter.value : undefined,
        unassigned: moduleFilter.value === '__stock__' || undefined,
      })
      hasMore.value = data.length > pageLimit.value; components.value = data.slice(0, pageLimit.value)
    }
  } catch (caught) { error.value = getApiErrorMessage(caught); hasMore.value = false } finally { isLoading.value = false }
}
function applyFilters() { currentPage.value = 1; void loadData() }
async function switchTab(tab: WarehouseTab) { activeTab.value = tab; currentPage.value = 1; query.value = ''; supplierQuery.value = ''; await loadData() }

async function saveModule() {
  resetMessages()
  if (!moduleForm.tsr_id) { error.value = 'Выбери ТСР для модуля.'; return }
  if (!moduleForm.module_name_index.trim() || !moduleForm.supplier.trim()) { error.value = 'Заполни индекс и поставщика.'; return }
  isSaving.value = true
  try {
    const payload = buildModulePayload()
    const wasEditing = isEditingModule.value
    const saved = wasEditing && selectedModule.value
      ? await updateModule(getModuleId(selectedModule.value), payload as ModuleUpdatePayload)
      : await createModule(payload)
    selectModule(saved); successMessage.value = wasEditing ? 'Модуль обновлен' : 'Модуль создан'
    await Promise.all([loadData(), loadAllComponents(), loadAllModules()])
  } catch (caught) { error.value = getApiErrorMessage(caught) } finally { isSaving.value = false }
}

async function saveComponent() {
  resetMessages()
  if (!componentForm.component_index.trim() || !componentForm.supplier.trim()) { error.value = 'Заполни индекс и поставщика.'; return }
  isSaving.value = true
  try {
    const payload = buildComponentPayload()
    const wasEditing = isEditingComponent.value
    const saved = wasEditing && selectedComponent.value
      ? await updateComponent(selectedComponent.value.component_id, payload)
      : await createComponent(payload)
    selectComponent(saved); successMessage.value = wasEditing ? 'Комплектующая обновлена' : 'Комплектующая создана'
    await Promise.all([loadData(), loadAllComponents(), loadAllModules()])
  } catch (caught) { error.value = getApiErrorMessage(caught) } finally { isSaving.value = false }
}

async function removeModule(item: ModuleItem) {
  if (!window.confirm(`Удалить модуль «${getModuleName(item)}»? Комплектующие останутся на складе.`)) return
  isSaving.value = true
  try { await deleteModule(getModuleId(item)); closeCards(); successMessage.value = 'Модуль удален'; await Promise.all([loadData(), loadAllComponents(), loadAllModules()]) }
  catch (caught) { error.value = getApiErrorMessage(caught) } finally { isSaving.value = false }
}
async function removeComponent(item: ModuleComponentItem) {
  if (!window.confirm(`Удалить комплектующую «${item.component_index}»?`)) return
  isSaving.value = true
  try { await deleteComponent(item.component_id); closeCards(); successMessage.value = 'Комплектующая удалена'; await Promise.all([loadData(), loadAllComponents()]) }
  catch (caught) { error.value = getApiErrorMessage(caught) } finally { isSaving.value = false }
}

async function loadAllModules() { moduleOptions.value = await fetchModules({ limit: 100000 }) }
async function loadAllComponents() { allComponents.value = await fetchComponents({ limit: 100000 }) }

onMounted(async () => {
  const [clientResult, nameResult, tsrResult] = await Promise.allSettled([
    fetchClients({ limit: 100000 }), fetchNameIndexReferences(), fetchTsrReferences(),
  ])
  clients.value = clientResult.status === 'fulfilled' ? clientResult.value : []
  nameIndexReferences.value = nameResult.status === 'fulfilled' ? nameResult.value : []
  tsrReferences.value = tsrResult.status === 'fulfilled' ? tsrResult.value : []
  await Promise.all([loadAllModules(), loadAllComponents()])
  await loadData()
})
</script>

<template>
  <section class="page-section">
    <div class="page-heading">
      <div><p class="eyebrow">Склад</p><h1>{{ activeTab === 'modules' ? 'Модули' : 'Комплектующие' }}</h1></div>
      <button class="primary-button" type="button" @click="activeTab === 'modules' ? openNewModule() : openNewComponent()">
        {{ activeTab === 'modules' ? 'Создать модуль' : 'Добавить комплектующую' }}
      </button>
    </div>

    <div class="tabs" role="tablist">
      <button :class="{ active: activeTab === 'modules' }" type="button" @click="switchTab('modules')">Модули</button>
      <button :class="{ active: activeTab === 'components' }" type="button" @click="switchTab('components')">Комплектующие</button>
    </div>

    <form class="toolbar-form warehouse-toolbar" @submit.prevent="applyFilters">
      <input v-model="query" placeholder="Индекс или название" />
      <input v-model="supplierQuery" placeholder="Поставщик" />
      <select v-if="activeTab === 'modules'" v-model="ownerFilter"><option value="">Все владельцы</option><option value="__stock__">На складе</option><option v-for="client in clients" :key="String(client.client_id)" :value="client.client_id">{{ getClientName(client) }}</option></select>
      <select v-else v-model="moduleFilter"><option value="">Все модули</option><option value="__stock__">Без модуля</option><option v-for="item in moduleOptions" :key="item.module_id" :value="item.module_id">{{ getModuleName(item) }}</option></select>
      <select v-model.number="pageLimit"><option :value="25">25</option><option :value="50">50</option><option :value="100">100</option><option :value="200">200</option></select>
      <button class="secondary-button" type="submit">Найти</button>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p><p v-if="successMessage" class="form-success">{{ successMessage }}</p>
    <div class="table-wrap warehouse-table-wrap">
      <table v-if="activeTab === 'modules'" class="warehouse-table">
        <thead><tr><th>№</th><th>Индекс</th><th>ТСР</th><th>Поставщик</th><th>Кол-во</th><th>Себестоимость</th><th>Цена</th><th>Заказано</th><th>Получено</th><th>Ожидается</th><th>У протезиста</th><th>Клиент</th><th></th></tr></thead>
        <tbody><tr v-if="isLoading"><td colspan="13">Загружаем...</td></tr><tr v-for="(item, index) in modules" v-else :key="item.module_id"><td>{{ currentSkip + index + 1 }}</td><td><button class="link-button" type="button" @click="selectModule(item)">{{ getModuleName(item) }}</button></td><td>{{ item.tsr?.full_tsr_code || '—' }}</td><td>{{ item.supplier }}</td><td>{{ item.quantity }}</td><td class="money-cell">{{ formatMoney(item.cost) }}</td><td class="money-cell">{{ formatMoney(item.price) }}</td><td class="count-cell">{{ item.ordered }}</td><td class="count-cell">{{ item.recd }}</td><td class="count-cell">{{ item.pending }}</td><td class="count-cell">{{ item.prosthetist_keep }}</td><td>{{ getClientLabel(item.client_id) }}</td><td class="row-actions"><button class="ghost-button" type="button" @click="selectModule(item)">Открыть</button><button class="danger-button" type="button" @click="removeModule(item)">Удалить</button></td></tr><tr v-if="!isLoading && modules.length === 0"><td colspan="13">Модули не найдены.</td></tr></tbody>
      </table>
      <table v-else>
        <thead><tr><th>№</th><th>Индекс</th><th>Модуль</th><th>Поставщик</th><th>Кол-во</th><th>Себестоимость</th><th>Цена</th><th>Заказано</th><th>Получено</th><th>Ожидается</th><th>Клиент</th><th></th></tr></thead>
        <tbody><tr v-if="isLoading"><td colspan="12">Загружаем...</td></tr><tr v-for="(item, index) in components" v-else :key="item.component_id"><td>{{ currentSkip + index + 1 }}</td><td><button class="link-button" type="button" @click="selectComponent(item)">{{ item.component_index }}</button></td><td>{{ item.module?.module_name_index || 'На складе' }}</td><td>{{ item.supplier }}</td><td>{{ item.quantity }}</td><td>{{ formatMoney(item.cost) }}</td><td>{{ formatMoney(item.price) }}</td><td>{{ item.ordered }}</td><td>{{ item.received }}</td><td>{{ item.pending }}</td><td>{{ getComponentClient(item) }}</td><td class="row-actions"><button class="ghost-button" type="button" @click="selectComponent(item)">Открыть</button><button class="danger-button" type="button" @click="removeComponent(item)">Удалить</button></td></tr><tr v-if="!isLoading && components.length === 0"><td colspan="12">Комплектующие не найдены.</td></tr></tbody>
      </table>
    </div>
    <div class="pagination-bar"><span>Страница {{ currentPage }}</span><div class="row-actions"><button class="secondary-button" :disabled="!hasPreviousPage" type="button" @click="currentPage -= 1; loadData()">Назад</button><button class="secondary-button" :disabled="!hasMore" type="button" @click="currentPage += 1; loadData()">Вперед</button></div></div>

    <div v-if="isModuleCardOpen" class="modal-backdrop" @click.self="closeCards"><section class="modal-panel"><div class="modal-header"><div><p class="eyebrow">{{ isEditingModule ? 'Редактирование' : 'Новый модуль' }}</p><h2>{{ selectedModule ? getModuleName(selectedModule) : 'Создать модуль' }}</h2></div><button class="ghost-button" type="button" @click="closeCards">Закрыть</button></div>
      <form class="side-form flat-form" @submit.prevent="saveModule">
        <div class="form-grid"><label>ТСР *<select v-model="moduleForm.tsr_id" required><option value="">Выбери ТСР</option><option v-for="option in tsrOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label><label>Индекс / название *<input v-model="moduleForm.module_name_index" list="module-index-list" required /><datalist id="module-index-list"><option v-for="item in nameIndexReferences" :key="String(item.id)" :value="getReferenceValue(item)" /></datalist></label><label>Поставщик *<input v-model="moduleForm.supplier" required /></label></div>
        <div class="form-grid"><label>Количество<input v-model="moduleForm.quantity" inputmode="numeric" /></label><label>Себестоимость за ед.<input v-model="moduleForm.unit_cost" inputmode="decimal" @blur="formatModuleMoneyField('unit_cost')" /></label><label>Цена за ед.<input v-model="moduleForm.unit_price" inputmode="decimal" @blur="formatModuleMoneyField('unit_price')" /></label></div>
        <div class="form-grid"><label>Заказано<input v-model="moduleForm.ordered" type="number" min="0" step="1" /></label><label>Получено<input v-model="moduleForm.recd" type="number" min="0" step="1" /></label><label>Ожидается<input v-model="moduleForm.pending" type="number" min="0" step="1" /></label></div>
        <div class="form-grid"><label>Счет и дата<input v-model="moduleForm.order_date_acc_num" /></label><label>Размер<input v-model="moduleForm.size" /></label><label>Жесткость<input v-model="moduleForm.stiffness" /></label><label>Сторона<input v-model="moduleForm.side" /></label></div>
        <label>Клиент<select v-model="moduleForm.client_id"><option value="">На складе</option><option v-for="client in clients" :key="client.client_id" :value="client.client_id">{{ getClientName(client) }}</option></select></label><label>Характеристики<input v-model="moduleForm.properties" /></label><label>У протезиста<input v-model="moduleForm.prosthetist_keep" type="number" min="0" step="1" /></label><label>Заметки<textarea v-model="moduleForm.notes" rows="3" /></label>
        <button class="primary-button" :disabled="isSaving" type="submit">Сохранить модуль</button>
      </form>
      <div v-if="isEditingModule" class="detail-panel"><div class="form-heading"><h2>Комплектующие модуля</h2><button class="secondary-button" type="button" @click="openNewComponent(selectedModule ? getModuleId(selectedModule) : '')">Добавить</button></div><div class="list-stack"><div v-for="item in selectedModuleComponents" :key="item.component_id" class="list-row"><div><strong>{{ item.component_index }}</strong><span>{{ item.supplier }} · {{ item.quantity }} шт. · {{ formatMoney(item.cost) }}</span></div><button class="ghost-button" type="button" @click="selectComponent(item)">Открыть</button></div><p v-if="selectedModuleComponents.length === 0" class="muted">Комплектующие не привязаны.</p></div></div>
    </section></div>

    <div v-if="isComponentCardOpen" class="modal-backdrop" @click.self="closeCards"><section class="modal-panel"><div class="modal-header"><div><p class="eyebrow">{{ isEditingComponent ? 'Редактирование' : 'Новая комплектующая' }}</p><h2>{{ selectedComponent?.component_index || 'Добавить комплектующую' }}</h2></div><button class="ghost-button" type="button" @click="closeCards">Закрыть</button></div>
      <form class="side-form flat-form" @submit.prevent="saveComponent"><div class="form-grid"><label>Индекс *<input v-model="componentForm.component_index" required /></label><label>Модуль<select v-model="componentForm.module_id"><option value="">На складе / без модуля</option><option v-for="item in moduleOptions" :key="item.module_id" :value="item.module_id">{{ getModuleName(item) }}</option></select></label><label>Поставщик *<input v-model="componentForm.supplier" required /></label></div><div class="form-grid"><label>Кол-во<input v-model="componentForm.quantity" inputmode="numeric" /></label><label>Себестоимость<input v-model="componentForm.cost" inputmode="decimal" @blur="formatComponentMoneyField('cost')" /></label><label>Цена<input v-model="componentForm.price" inputmode="decimal" @blur="formatComponentMoneyField('price')" /></label></div><div class="form-grid"><label>Заказано<input v-model="componentForm.ordered" /></label><label>Получено<input v-model="componentForm.received" /></label><label>Ожидается<input v-model="componentForm.pending" /></label></div><label>Заметки<textarea v-model="componentForm.notes" rows="3" /></label><button class="primary-button" :disabled="isSaving" type="submit">Сохранить комплектующую</button></form>
    </section></div>
  </section>
</template>
