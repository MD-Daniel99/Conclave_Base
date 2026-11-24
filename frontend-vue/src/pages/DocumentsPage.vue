<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DateInput from '@/shared/ui/DateInput.vue'
import MtzSharedFields from '@/shared/ui/MtzSharedFields.vue'
import MtzConclusionSelector from '@/shared/ui/MtzConclusionSelector.vue'
import { fetchClient, fetchClients } from '@/shared/api/clients'
import {
  downloadDocumentBlob,
  fetchClientDocuments,
  fetchContractTemplates,
  fetchMtzTemplates,
  fetchMtzConfig,
  uploadMtzTemplate,
  deleteMtzTemplate,
  downloadMtzTemplate,
  fetchNextContractNumber,
  generateClientContract,
  generateClientMtz,
  type ContractTemplateOption,
  type MtzTemplateOption,
  type MtzConclusionItem,
  type MtzFormConfig,
} from '@/shared/api/documents'
import { getApiErrorMessage } from '@/shared/api/http'
import type { Client, ClientDocument, ContractGenerationPayload } from '@/shared/types/entities'

const route = useRoute()
const router = useRouter()
const clients = ref<Client[]>([])
const selectedClientId = ref('')
const selectedClient = ref<Client | null>(null)
const documents = ref<ClientDocument[]>([])
const activeTab = ref<'contracts' | 'mtz'>('contracts')
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const success = ref('')

const contractTemplates = ref<ContractTemplateOption[]>([])
const contractType = ref('llc_contract')
const dmkDiagnosis = ref('')
const contractPrefix = ref('СД')
const contractNumber = ref('030')
const contractDate = ref(new Date().toISOString().slice(0, 10))
const planDate = ref(new Date().toISOString().slice(0, 10))
const appendixDate = ref(new Date().toISOString().slice(0, 10))
const selectedClientTsrIds = ref<string[]>([])
const selectedModuleIds = ref<string[]>([])

const mtzTemplates = ref<MtzTemplateOption[]>([])
const mtzConfig = ref<MtzFormConfig | null>(null)
const mtzExtraValues = ref<Record<string,string>>({})
const mtzItems = ref<MtzConclusionItem[]>([])
const mtzUploadFile = ref<File | null>(null)
const mtzTemplateBusy = ref(false)
const disabilityGroupReason = ref('')
const diagnoses = ref<string[]>([])
const stumpCondition = ref('Функциональная')
const activityLevel = ref('3-4')
const weightKg = ref('')

function clientId(client: Client) {
  return String(client.client_id ?? '')
}

function clientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ')
}

const sortedClients = computed(() => [...clients.value].sort((a, b) => clientName(a).localeCompare(clientName(b), 'ru')))
watch(contractType, (templateType, previous) => {
  if (templateType === 'dmk_full_package') {
    contractNumber.value = ''
    contractPrefix.value = 'ДМК'
  } else {
    if (previous === 'dmk_full_package') contractPrefix.value = 'СД'
    void fetchNextContractNumber(templateType).then((number) => {
      if (contractType.value === templateType) contractNumber.value = number
    }).catch(() => {})
  }
})

const usesCertificateSelection = computed(() => ['llc_contract', 'zet_contract', 'dmk_full_package'].includes(contractType.value))
const clientTsrItems = computed(() => selectedClient.value?.tsr_items ?? [])
const mtzTsrLabels = computed(() => mtzItems.value.length
  ? mtzItems.value.map(item => mtzTemplates.value.find(t => t.value === item.template_type)?.label ?? '')
  : clientTsrItems.value.map(item => String(item.tsr?.full_tsr_code ?? '')))
const clientModules = computed(() => (selectedClient.value?.modules ?? []).filter((item) => !item.is_archived))
const selectedTsrSet = computed(() => new Set(selectedClientTsrIds.value))

function tsrLabel(item: NonNullable<Client['tsr_items']>[number]) {
  return String(item.tsr?.full_tsr_code || item.tsr_id || 'ТСР')
}

function modulesForTsr(clientTsrId: string) {
  return clientModules.value.filter((item) => String(item.client_tsr_id ?? '') === clientTsrId)
}

function latestPassport() {
  const passports = selectedClient.value?.passports ?? []
  return [...passports].sort((a, b) => Number(b.version ?? 0) - Number(a.version ?? 0))[0]
}

const mtzAutoData = computed(() => ({
  fullName: selectedClient.value ? clientName(selectedClient.value) : '—',
  birthDate: String(latestPassport()?.birth_date ?? '').slice(0, 10) || '—',
  phone: String(selectedClient.value?.phones?.[0]?.number ?? '') || '—',
}))

const isMtzTemplatesSubpage = computed(() => route.name === 'documents-mtz-templates')
function goMtzSubpage(templates: boolean) {
  void router.push({ name: templates ? 'documents-mtz-templates' : 'documents-mtz',
    query: selectedClientId.value ? { client_id: selectedClientId.value } : undefined })
}
function mtzFileChange(event: Event) {
  mtzUploadFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}
async function addMtzTemplates() {
  resetMessages()
  if (!mtzUploadFile.value) { error.value = 'Выберите DOCX.'; return }
  mtzTemplateBusy.value = true
  try {
    const added = await uploadMtzTemplate(mtzUploadFile.value)
    mtzTemplates.value = await fetchMtzTemplates()
    mtzUploadFile.value = null
    success.value = added.length ? `Добавлено заключений: ${added.length}` : 'Такие заключения уже есть в библиотеке.'
  } catch (caught) { error.value = getApiErrorMessage(caught) }
  finally { mtzTemplateBusy.value = false }
}
async function saveMtzTemplate(key: string) {
  resetMessages()
  try {
    const blob = await downloadMtzTemplate(key)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `mtz_conclusion_${key}.docx`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    // Revoke later because browsers may not have started reading the blob yet.
    setTimeout(() => URL.revokeObjectURL(url), 15000)
  } catch (caught) { error.value = getApiErrorMessage(caught) }
}
async function removeMtzTemplate(key: string) {
  resetMessages()
  if (!window.confirm('Убрать это заключение из списка? Ранее созданные документы сохранятся.')) return
  mtzTemplateBusy.value = true
  try {
    await deleteMtzTemplate(key)
    mtzTemplates.value = await fetchMtzTemplates()
    mtzItems.value = mtzItems.value.filter(item => item.template_type !== key)
    success.value = 'Шаблон исключён из выбора.'
  } catch (caught) { error.value = getApiErrorMessage(caught) }
  finally { mtzTemplateBusy.value = false }
}

function tabFromRoute() {
  if (route.name === 'documents-mtz' || route.name === 'documents-mtz-templates') return 'mtz' as const
  if (route.name === 'documents-contracts') return 'contracts' as const
  return String(route.query.tab || '').toLowerCase() === 'mtz' ? 'mtz' as const : 'contracts' as const
}

function goTab(tab: 'contracts' | 'mtz') {
  activeTab.value = tab
  void router.push({
    name: tab === 'mtz' ? 'documents-mtz' : 'documents-contracts',
    query: selectedClientId.value ? { client_id: selectedClientId.value } : undefined,
  })
}

function resetMessages() {
  error.value = ''
  success.value = ''
}

async function loadClient() {
  resetMessages()
  selectedClient.value = null
  documents.value = []
  selectedClientTsrIds.value = []
  selectedModuleIds.value = []
  dmkDiagnosis.value = ''
  disabilityGroupReason.value = ''
  diagnoses.value = []
  mtzExtraValues.value = {}
  mtzItems.value = []
  weightKg.value = ''
  if (!selectedClientId.value) return

  isLoading.value = true
  try {
    const [client, docs] = await Promise.all([
      fetchClient(selectedClientId.value),
      fetchClientDocuments(selectedClientId.value),
    ])
    selectedClient.value = client
    documents.value = docs
    selectedClientTsrIds.value = (client.tsr_items ?? []).map((item) => String(item.client_tsr_id ?? '')).filter(Boolean)
    selectedModuleIds.value = (client.modules ?? []).filter((item) => !item.is_archived).map((item) => String(item.module_id ?? '')).filter(Boolean)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isLoading.value = false
  }
}

function onTsrToggle(clientTsrId: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  toggleTsr(clientTsrId, checked)
}

function toggleTsr(clientTsrId: string, checked: boolean) {
  if (checked) {
    if (!selectedClientTsrIds.value.includes(clientTsrId)) selectedClientTsrIds.value.push(clientTsrId)
    modulesForTsr(clientTsrId).forEach((item) => {
      const id = String(item.module_id ?? '')
      if (id && !selectedModuleIds.value.includes(id)) selectedModuleIds.value.push(id)
    })
  } else {
    selectedClientTsrIds.value = selectedClientTsrIds.value.filter((id) => id !== clientTsrId)
    const moduleIds = new Set(modulesForTsr(clientTsrId).map((item) => String(item.module_id ?? '')))
    selectedModuleIds.value = selectedModuleIds.value.filter((id) => !moduleIds.has(id))
  }
}

async function download(document: ClientDocument) {
  if (!document.document_id) return
  try {
    const { blob, contentDisposition } = await downloadDocumentBlob(String(document.document_id))
    const match = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(contentDisposition)
    const filename = match ? decodeURIComponent(match[1]) : document.filename
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = filename || document.filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function generateContract() {
  resetMessages()
  if (!selectedClientId.value) { error.value = 'Выберите пациента.'; return }
  const isDmkFullPackage = contractType.value === 'dmk_full_package'
  if (!contractNumber.value.trim() || (!isDmkFullPackage && (!contractPrefix.value.trim() || !/^\d+$/.test(contractNumber.value.trim())))) {
    error.value = isDmkFullPackage
      ? 'Введите номер договора ИП ДМК вручную (например, 13072026/1).'
      : 'Укажите буквенную часть и числовой номер договора.'
    return
  }
  if (contractType.value === 'dmk_full_package' && !dmkDiagnosis.value.trim()) {
    error.value = 'Для полного комплекта ИП ДМК вручную укажите диагноз.'
    return
  }
  if (usesCertificateSelection.value && selectedClientTsrIds.value.length === 0) {
    error.value = 'Для договора выберите хотя бы один ТСР пациента.'
    return
  }

  isSaving.value = true
  try {
    const selectedTsr = clientTsrItems.value.filter((item) => selectedTsrSet.value.has(String(item.client_tsr_id ?? '')))
    const payload: ContractGenerationPayload = {
      template_type: contractType.value,
      ...(contractType.value === 'dmk_full_package' ? { diagnosis: dmkDiagnosis.value.trim() } : {}),
      document_number: isDmkFullPackage
        ? contractNumber.value.trim()
        : `${contractPrefix.value.trim().toUpperCase()}/${contractNumber.value.trim()}`,
      document_number_prefix: isDmkFullPackage ? '' : contractPrefix.value.trim().toUpperCase(),
      document_number_suffix: contractNumber.value.trim(),
      document_date: contractDate.value,
      plan_date: usesCertificateSelection.value ? planDate.value : contractDate.value,
      appendix_number: '1',
      appendix_date: usesCertificateSelection.value ? appendixDate.value : contractDate.value,
      selected_client_tsr_ids: usesCertificateSelection.value ? selectedClientTsrIds.value : [],
      selected_tsr_ids: usesCertificateSelection.value
        ? [...new Set(selectedTsr.map((item) => String(item.tsr_id ?? '')).filter(Boolean))]
        : [],
      selected_module_ids: usesCertificateSelection.value ? selectedModuleIds.value : [],
    }
    await generateClientContract(selectedClientId.value, payload)
    success.value = 'Договор сформирован. Скачать его можно в списке документов ниже.'
    if (contractType.value === 'dmk_full_package') dmkDiagnosis.value = ''
    documents.value = await fetchClientDocuments(selectedClientId.value)
    if (contractType.value !== 'dmk_full_package') contractNumber.value = await fetchNextContractNumber(contractType.value)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function generateMtz() {
  resetMessages()
  if (!selectedClientId.value) { error.value = 'Выберите пациента.'; return }
  if (!disabilityGroupReason.value || !diagnoses.value.length || !mtzItems.value.length || mtzItems.value.some(item => !item.amputation_level.trim()) || !weightKg.value.trim()) {
    error.value = 'Заполните причину инвалидности, диагноз, уровень ампутации и вес.'
    return
  }
  if (!selectedClient.value?.mse_reference?.trim()) {
    error.value = 'Сначала заполните справку МСЭ в личных документах пациента.'
    return
  }

  isSaving.value = true
  try {
    await generateClientMtz(selectedClientId.value, {
      items: mtzItems.value,
      disability_group_reason: disabilityGroupReason.value,
      diagnoses: diagnoses.value,
      stump_condition: stumpCondition.value,
      activity_level: activityLevel.value,
      weight_kg: weightKg.value.trim(),
      extra_fields: mtzExtraValues.value,
    })
    success.value = 'МТЗ сформировано. Скачать его можно в списке документов ниже.'
    documents.value = await fetchClientDocuments(selectedClientId.value)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

watch(selectedClientId, () => { void loadClient() })
watch(
  () => route.name,
  () => {
    activeTab.value = tabFromRoute()
  },
)
watch(
  () => route.query.client_id,
  (clientId) => {
    const value = String(clientId || '')
    if (value && value !== selectedClientId.value) selectedClientId.value = value
  },
)

onMounted(async () => {
  isLoading.value = true
  try {
    const [active, archived, templates, mtzOptions, mtzFields, nextNumber] = await Promise.all([
      fetchClients({ limit: 100000, archived: false }),
      fetchClients({ limit: 100000, archived: true }),
      fetchContractTemplates(),
      fetchMtzTemplates(),
      fetchMtzConfig(),
      fetchNextContractNumber(contractType.value),
    ])
    const unique = new Map<string, Client>()
    ;[...active, ...archived].forEach((client) => unique.set(clientId(client), client))
    clients.value = [...unique.values()]
    contractTemplates.value = templates
    mtzTemplates.value = mtzOptions
    mtzConfig.value = mtzFields
    const stumpOptions=mtzFields.manual.stump_condition?.options ?? []
    const activityOptions=mtzFields.manual.activity_level?.options ?? []
    if (stumpOptions.length && !stumpOptions.includes(stumpCondition.value)) stumpCondition.value=stumpOptions[0]
    if (activityOptions.length && !activityOptions.includes(activityLevel.value)) activityLevel.value=activityOptions[0]
    if (contractType.value !== 'dmk_full_package') contractNumber.value = nextNumber
    if (templates[0] && !templates.some((item) => item.value === contractType.value)) contractType.value = templates[0].value

    activeTab.value = tabFromRoute()
    const requestedClientId = String(route.query.client_id || '')
    if (requestedClientId && clients.value.some((client) => clientId(client) === requestedClientId)) {
      selectedClientId.value = requestedClientId
    }
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <section class="page-section documents-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Документы</p>
        <h1>Автозаполнение документов</h1>
        <p class="muted">Единая страница для договоров и медико-технических заключений.</p>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button :class="{ active: activeTab === 'contracts' }" type="button" @click="goTab('contracts')">Договоры</button>
      <button :class="{ active: activeTab === 'mtz' }" type="button" @click="goTab('mtz')">МТЗ</button>
    </div>

    <div v-if="activeTab === 'mtz'" class="tabs" role="tablist">
      <button type="button" :class="{ active: !isMtzTemplatesSubpage }" @click="goMtzSubpage(false)">Сформировать МТЗ</button>
      <button type="button" :class="{ active: isMtzTemplatesSubpage }" @click="goMtzSubpage(true)">Библиотека ТСР</button>
      <button type="button" @click="router.push({name:'documents-mtz-designer'})">Конструктор МТЗ</button>
    </div>

    <div v-if="!isMtzTemplatesSubpage" class="toolbar-form documents-client-picker">
      <label>
        Пациент
        <select v-model="selectedClientId">
          <option value="">Выберите пациента</option>
          <option v-for="client in sortedClients" :key="clientId(client)" :value="clientId(client)">
            {{ clientName(client) }}
          </option>
        </select>
      </label>
      <span v-if="selectedClient" class="muted">ID: {{ selectedClient.external_id ?? '—' }}</span>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>
    <p v-if="isLoading" class="muted">Загрузка…</p>

    <section v-if="activeTab === 'mtz' && isMtzTemplatesSubpage" class="detail-panel" style="display:grid;gap:16px">
      <div class="form-heading"><div><p class="eyebrow">Библиотека МТЗ</p><h2>Заключения ТСР</h2></div></div>
      <p class="form-hint">Загрузите DOCX. Программа выделит блоки с кодом ТСР и таблицей «Уровень ампутации» и добавит их для выбора. Старые шапки, реквизиты пациента и подписи в новые заключения не переносятся. Проверьте содержание перед применением к пациенту.</p>
      <form class="toolbar-form" @submit.prevent="addMtzTemplates">
        <label>DOCX с заключением или несколькими заключениями
          <input type="file" accept=".docx" @change="mtzFileChange" />
        </label>
        <button class="primary-button" type="submit" :disabled="mtzTemplateBusy || !mtzUploadFile">{{ mtzTemplateBusy ? 'Обрабатываем…' : 'Загрузить и разметить' }}</button>
      </form>
      <p class="form-hint">Всего шаблонов: {{ mtzTemplates.length }}. Встроенные шаблоны защищены от удаления; загруженные сотрудниками можно исключать из каталога.</p>
      <div class="documents-file-list">
        <div v-for="item in mtzTemplates" :key="item.value" class="documents-file-row">
          <span><strong>{{ item.label }}</strong><small>{{ item.tsr_code }} · {{ item.builtin ? 'Встроенный' : 'Добавлен сотрудником' }}</small></span>
          <span style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="secondary-button" type="button" @click="saveMtzTemplate(item.value)">Скачать заключение</button>
            <button v-if="!item.builtin" class="secondary-button" type="button" :disabled="mtzTemplateBusy" @click="removeMtzTemplate(item.value)">Удалить из списка</button>
          </span>
        </div>
      </div>
    </section>

    <template v-if="selectedClient && activeTab === 'contracts'">
      <form class="detail-panel documents-generator" @submit.prevent="generateContract">
        <div class="form-heading">
          <div><p class="eyebrow">Договоры</p><h2>Сформировать договор</h2></div>
        </div>
        <div class="form-grid documents-form-grid">
          <label>Шаблон<select v-model="contractType"><option v-for="item in contractTemplates" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label v-if="contractType !== 'dmk_full_package'">Буквы номера<input v-model="contractPrefix" maxlength="8" /></label>
          <label>{{ contractType === 'dmk_full_package' ? 'Номер договора (вручную)' : 'Номер' }}<input v-model="contractNumber" :inputmode="contractType === 'dmk_full_package' ? 'text' : 'numeric'" :placeholder="contractType === 'dmk_full_package' ? 'Например: 13072026/1' : 'Номер договора'" /></label>
          <label class="documents-contract-date-field">Дата документа<DateInput v-model="contractDate" /></label>
          <label v-if="usesCertificateSelection" class="documents-contract-date-field">Дата плана / ТЗ<DateInput v-model="planDate" /></label>
          <label v-if="usesCertificateSelection" class="documents-contract-date-field">Дата приложений / акта<DateInput v-model="appendixDate" /></label>
          <label v-if="contractType === 'dmk_full_package'" class="documents-wide-field documents-contract-diagnosis-field">
            Диагноз (формулировка для договора ИП ДМК)
            <textarea v-model="dmkDiagnosis" rows="2" maxlength="1000" required placeholder="Например: нижних конечностей"></textarea>
            <span class="muted">Введите вручную для этого договора; формулировка подставляется после слов «протез» и «протеза».</span>
          </label>
        </div>

        <div v-if="usesCertificateSelection" class="documents-tsr-selector">
          <div class="form-heading compact-heading">
            <div><p class="eyebrow">Состав договора</p><h3>ТСР и комплектующие</h3></div>
          </div>
          <p v-if="!clientTsrItems.length" class="form-hint">У пациента пока нет прикреплённых ТСР.</p>
          <article v-for="item in clientTsrItems" :key="item.client_tsr_id" class="documents-tsr-card">
            <label class="checkbox-label">
              <input
                type="checkbox"
                :checked="selectedTsrSet.has(String(item.client_tsr_id))"
                @change="onTsrToggle(String(item.client_tsr_id), $event)"
              />
              <strong>{{ tsrLabel(item) }}</strong>
            </label>
            <div v-if="modulesForTsr(String(item.client_tsr_id)).length" class="documents-component-list">
              <label v-for="component in modulesForTsr(String(item.client_tsr_id))" :key="component.module_id" class="checkbox-label">
                <input v-model="selectedModuleIds" type="checkbox" :value="String(component.module_id)" />
                <span>{{ component.module_name_index }} · {{ component.quantity ?? 1 }} шт.</span>
              </label>
            </div>
          </article>
        </div>

        <button class="primary-button" type="submit" :disabled="isSaving">{{ isSaving ? 'Формируем…' : 'Сформировать договор' }}</button>
      </form>
    </template>

    <template v-if="selectedClient && activeTab === 'mtz' && !isMtzTemplatesSubpage">
      <div class="documents-mtz-layout">
        <form class="detail-panel documents-generator" @submit.prevent="generateMtz">
          <div class="form-heading">
            <div><p class="eyebrow">МТЗ</p><h2>Сформировать заключение</h2></div>
          </div>
          <div class="mtz-workspace">
            <MtzConclusionSelector v-model="mtzItems" :templates="mtzTemplates" :config="mtzConfig" />
            <MtzSharedFields :config="mtzConfig" :reason="disabilityGroupReason" :diagnoses="diagnoses"
              :stump="stumpCondition" :activity="activityLevel" :weight="weightKg"
              :mse="selectedClient?.mse_reference ?? ''" :tsr-labels="mtzTsrLabels" :extra-values="mtzExtraValues"
              @update:reason="disabilityGroupReason=$event" @update:diagnoses="diagnoses=$event"
              @update:stump="stumpCondition=$event" @update:activity="activityLevel=$event"
              @update:weight="weightKg=$event" @update:extra-values="mtzExtraValues=$event" />
          </div>
          <button class="primary-button" type="submit" :disabled="isSaving">{{ isSaving ? 'Формируем…' : 'Сформировать МТЗ' }}</button>
        </form>

        <aside class="detail-panel documents-autofill-preview">
          <div class="form-heading"><div><p class="eyebrow">Автозаполнение</p><h2>Данные пациента</h2></div></div>
          <dl>
            <div><dt>ФИО</dt><dd>{{ mtzAutoData.fullName }}</dd></div>
            <div><dt>Дата рождения</dt><dd>{{ mtzAutoData.birthDate }}</dd></div>
            <div><dt>Телефон</dt><dd>{{ mtzAutoData.phone }}</dd></div>
            <div><dt>Заключений ТСР</dt><dd>{{ mtzItems.length }}</dd></div>
          </dl>
          <p class="form-hint">Номер и дата МТЗ остаются пустыми для заполнения после печати. Справка МСЭ хранится в личных документах пациента.</p>
        </aside>
      </div>
    </template>

    <section v-if="selectedClient && documents.length" class="detail-panel documents-history">
      <div class="form-heading"><div><p class="eyebrow">Документы пациента</p><h2>Последние файлы</h2></div></div>
      <div class="documents-file-list">
        <button v-for="document in documents.slice(0, 12)" :key="document.document_id" class="documents-file-row" type="button" @click="download(document)">
          <span><strong>{{ document.filename }}</strong><small>{{ document.document_type || 'Файл' }} · {{ document.document_number || 'без номера' }}</small></span>
          <span>Скачать</span>
        </button>
      </div>
    </section>
  </section>
</template>
