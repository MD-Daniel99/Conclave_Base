<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DateInput from '@/shared/ui/DateInput.vue'
import { fetchClient, fetchClients } from '@/shared/api/clients'
import {
  downloadDocumentBlob,
  fetchClientDocuments,
  fetchContractTemplates,
  fetchMtzTemplates,
  fetchNextContractNumber,
  generateClientContract,
  generateClientMtz,
  type ContractTemplateOption,
  type MtzTemplateOption,
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
const contractPrefix = ref('СД')
const contractNumber = ref('001')
const contractDate = ref(new Date().toISOString().slice(0, 10))
const planDate = ref(new Date().toISOString().slice(0, 10))
const appendixDate = ref(new Date().toISOString().slice(0, 10))
const selectedClientTsrIds = ref<string[]>([])
const selectedModuleIds = ref<string[]>([])

const mtzTemplates = ref<MtzTemplateOption[]>([])
const mtzType = ref('mtz_8_1_07_14')
const mtzNumber = ref('')
const mtzDate = ref(new Date().toISOString().slice(0, 10))
const disabilityGroupReason = ref('')
const certificateReference = ref('')
const diagnosis = ref('')
const amputationLevel = ref('')
const weightKg = ref('')

function clientId(client: Client) {
  return String(client.client_id ?? '')
}

function clientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ')
}

const sortedClients = computed(() => [...clients.value].sort((a, b) => clientName(a).localeCompare(clientName(b), 'ru')))
const isLlcContract = computed(() => contractType.value === 'llc_contract')
const clientTsrItems = computed(() => selectedClient.value?.tsr_items ?? [])
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

const selectedMtzTemplate = computed(() => mtzTemplates.value.find((item) => item.value === mtzType.value))

function tabFromRoute() {
  if (route.name === 'documents-mtz') return 'mtz' as const
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
  if (!contractPrefix.value.trim() || !/^\d+$/.test(contractNumber.value.trim())) {
    error.value = 'Укажите буквенную часть и числовой номер договора.'
    return
  }
  if (isLlcContract.value && selectedClientTsrIds.value.length === 0) {
    error.value = 'Для договора ООО выберите хотя бы один ТСР пациента.'
    return
  }

  isSaving.value = true
  try {
    const selectedTsr = clientTsrItems.value.filter((item) => selectedTsrSet.value.has(String(item.client_tsr_id ?? '')))
    const payload: ContractGenerationPayload = {
      template_type: contractType.value,
      document_number: `${contractPrefix.value.trim().toUpperCase()}/${contractNumber.value.trim()}`,
      document_number_prefix: contractPrefix.value.trim().toUpperCase(),
      document_number_suffix: contractNumber.value.trim(),
      document_date: contractDate.value,
      plan_date: isLlcContract.value ? planDate.value : contractDate.value,
      appendix_number: '1',
      appendix_date: isLlcContract.value ? appendixDate.value : contractDate.value,
      selected_client_tsr_ids: isLlcContract.value ? selectedClientTsrIds.value : [],
      selected_tsr_ids: isLlcContract.value
        ? [...new Set(selectedTsr.map((item) => String(item.tsr_id ?? '')).filter(Boolean))]
        : [],
      selected_module_ids: isLlcContract.value ? selectedModuleIds.value : [],
    }
    await generateClientContract(selectedClientId.value, payload)
    success.value = 'Договор сформирован. Скачать его можно в списке документов ниже.'
    documents.value = await fetchClientDocuments(selectedClientId.value)
    contractNumber.value = await fetchNextContractNumber()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    isSaving.value = false
  }
}

async function generateMtz() {
  resetMessages()
  if (!selectedClientId.value) { error.value = 'Выберите пациента.'; return }
  const required = [mtzNumber.value, mtzDate.value, disabilityGroupReason.value, certificateReference.value, diagnosis.value, amputationLevel.value, weightKg.value]
  if (required.some((value) => !String(value).trim())) {
    error.value = 'Заполните номер/дату МТЗ и все ручные поля.'
    return
  }

  isSaving.value = true
  try {
    await generateClientMtz(selectedClientId.value, {
      template_type: mtzType.value,
      mtz_number: mtzNumber.value.trim(),
      document_date: mtzDate.value,
      disability_group_reason: disabilityGroupReason.value.trim(),
      certificate_reference: certificateReference.value.trim(),
      diagnosis: diagnosis.value.trim(),
      amputation_level: amputationLevel.value.trim(),
      weight_kg: weightKg.value.trim(),
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
    const [active, archived, templates, mtzOptions, nextNumber] = await Promise.all([
      fetchClients({ limit: 100000, archived: false }),
      fetchClients({ limit: 100000, archived: true }),
      fetchContractTemplates(),
      fetchMtzTemplates(),
      fetchNextContractNumber(),
    ])
    const unique = new Map<string, Client>()
    ;[...active, ...archived].forEach((client) => unique.set(clientId(client), client))
    clients.value = [...unique.values()]
    contractTemplates.value = templates
    mtzTemplates.value = mtzOptions
    contractNumber.value = nextNumber
    if (templates[0] && !templates.some((item) => item.value === contractType.value)) contractType.value = templates[0].value
    if (mtzOptions[0]) mtzType.value = mtzOptions[0].value
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

    <div class="toolbar-form documents-client-picker">
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

    <template v-if="selectedClient && activeTab === 'contracts'">
      <form class="detail-panel documents-generator" @submit.prevent="generateContract">
        <div class="form-heading">
          <div><p class="eyebrow">Договоры</p><h2>Сформировать договор</h2></div>
        </div>
        <div class="form-grid documents-form-grid">
          <label>Шаблон<select v-model="contractType"><option v-for="item in contractTemplates" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>Буквы номера<input v-model="contractPrefix" maxlength="8" /></label>
          <label>Номер<input v-model="contractNumber" inputmode="numeric" /></label>
          <label>Дата документа<DateInput v-model="contractDate" /></label>
          <label v-if="isLlcContract">Дата плана / ТЗ<DateInput v-model="planDate" /></label>
          <label v-if="isLlcContract">Дата приложений / акта<DateInput v-model="appendixDate" /></label>
        </div>

        <div v-if="isLlcContract" class="documents-tsr-selector">
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

    <template v-if="selectedClient && activeTab === 'mtz'">
      <div class="documents-mtz-layout">
        <form class="detail-panel documents-generator" @submit.prevent="generateMtz">
          <div class="form-heading">
            <div><p class="eyebrow">МТЗ</p><h2>Сформировать заключение</h2></div>
          </div>
          <div class="form-grid documents-form-grid">
            <label class="documents-wide-field">Шаблон / ТСР<select v-model="mtzType"><option v-for="item in mtzTemplates" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <label>Номер МТЗ<input v-model="mtzNumber" placeholder="Например: 124/26" /></label>
            <label class="mtz-date-field">Дата МТЗ<DateInput v-model="mtzDate" aria-label="Дата МТЗ" /></label>
            <label class="documents-wide-field documents-mtz-disability-field">Группа и причина инвалидности<input v-model="disabilityGroupReason" /></label>
            <label class="documents-wide-field">Справка<input v-model="certificateReference" /></label>
            <label class="documents-wide-field">Диагноз<textarea v-model="diagnosis" rows="3" /></label>
            <label>Уровень ампутации<input v-model="amputationLevel" /></label>
            <label>Вес пациента (кг)<input v-model="weightKg" inputmode="decimal" /></label>
          </div>
          <button class="primary-button" type="submit" :disabled="isSaving">{{ isSaving ? 'Формируем…' : 'Сформировать МТЗ' }}</button>
        </form>

        <aside class="detail-panel documents-autofill-preview">
          <div class="form-heading"><div><p class="eyebrow">Автозаполнение</p><h2>Данные пациента</h2></div></div>
          <dl>
            <div><dt>ФИО</dt><dd>{{ mtzAutoData.fullName }}</dd></div>
            <div><dt>Дата рождения</dt><dd>{{ mtzAutoData.birthDate }}</dd></div>
            <div><dt>Телефон</dt><dd>{{ mtzAutoData.phone }}</dd></div>
            <div><dt>ТСР</dt><dd>{{ selectedMtzTemplate?.tsr_code ?? '—' }}</dd></div>
          </dl>
          <p class="form-hint">Группа/причина инвалидности, справка, диагноз, уровень ампутации и вес вводятся только здесь и не сохраняются в карточку пациента.</p>
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
