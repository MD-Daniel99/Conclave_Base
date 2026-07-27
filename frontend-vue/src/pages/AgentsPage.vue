<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Eye, Plus, Search, Trash2, X } from '@lucide/vue'

import { fetchClients } from '@/shared/api/clients'
import { fetchEntityAudit } from '@/shared/api/audit'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import ActionMenu, { type ActionMenuItem } from '@/shared/ui/ActionMenu.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'

import {
  fetchAgents,
  createAgent,
  updateAgent,
  deleteAgent,
} from '@/shared/api/agents'
  
import {
  formatAuditAction,
  formatAuditActor,
  formatAuditTime,
  summarizeAuditDetails,
} from '@/shared/lib/audit'

import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  AuditLogItem,
  Client,
} from '@/shared/types/entities'

type AgentForm = {
  last_name: string
  first_name: string
  middle_name: string
  legal_address: string
  actual_address: string
  inn: string
  ogrnip: string
  account_number: string
  correspondent_account: string
  bic: string
}

type AgentTab = 'edit' | 'clients' | 'history'

const emptyForm: AgentForm = {
  last_name: '',
  first_name: '',
  middle_name: '',
  legal_address: '',
  actual_address: '',
  inn: '',
  ogrnip: '',
  account_number: '',
  correspondent_account: '',
  bic: '',
}

const agents = ref<Agent[]>([])
const linkedClients = ref<Client[]>([])
const auditItems = ref<AuditLogItem[]>([])
const query = ref('')
const page = ref(1)
const pageSize = ref(20)
const selectedAgent = ref<Agent | null>(null)
const activeAgentTab = ref<AgentTab>('edit')
const isAgentCardOpen = ref(false)

const form = reactive<AgentForm>({ ...emptyForm })

const isLoading = ref(false)
const isSaving = ref(false)
const isClientsLoading = ref(false)
const isAuditLoading = ref(false)
const error = ref('')
const successMessage = ref('')
const clientsError = ref('')
const auditError = ref('')
let agentSearchTimer: ReturnType<typeof setTimeout> | undefined

const isEditing = computed(() => Boolean(selectedAgent.value?.agent_id))
const isAgentPersisted = computed(() => Boolean(selectedAgent.value && getAgentId(selectedAgent.value)))
const skip = computed(() => (page.value - 1) * pageSize.value)
const canGoBack = computed(() => page.value > 1 && !isLoading.value)
const canGoForward = computed(() => agents.value.length === pageSize.value && !isLoading.value)
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Агенты')

function getAgentId(agent: Agent) {
  return agent.agent_id ? String(agent.agent_id) : ''
}

function getAgentName(agent: Agent) {
  return [agent.last_name, agent.first_name, agent.middle_name]
    .filter(Boolean)
    .join(' ') || 'Без имени'
}

function getAgentInitials(agent: Agent) {
  return [agent.last_name, agent.first_name]
    .filter(Boolean)
    .map((part) => String(part).slice(0, 1))
    .join('')
    .toUpperCase() || 'АГ'
}

function getAgentActions(agent: Agent): ActionMenuItem[] {
  return [
    {
      label: 'Открыть карточку',
      icon: Eye,
      action: () => selectAgent(agent),
    },
    {
      label: 'Удалить',
      icon: Trash2,
      danger: true,
      disabled: isSaving.value,
      action: () => removeAgent(agent),
    },
  ]
}

function getClientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name]
    .filter(Boolean)
    .join(' ') || 'Без имени'
}

function formatDate(value?: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString('ru-RU')
}

function cleanOptional(value: string) {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function normalizeDigits(value: string) {
  return value.replace(/\D/g, '')
}

function resetMessages() {
  error.value = ''
  successMessage.value = ''
}

function clearAgentRelatedState() {
  linkedClients.value = []
  auditItems.value = []
  clientsError.value = ''
  auditError.value = ''
  activeAgentTab.value = 'edit'
}

function resetForm() {
  Object.assign(form, emptyForm)
  selectedAgent.value = null
  clearAgentRelatedState()
  resetMessages()
}

function openNewAgent() {
  resetForm()
  isAgentCardOpen.value = true
}

function closeAgentCard() {
  if (isSaving.value) {
    return
  }

  isAgentCardOpen.value = false
  resetForm()
}

function fillFormFromAgent(agent: Agent) {
  form.last_name = agent.last_name ?? ''
  form.first_name = agent.first_name ?? ''
  form.middle_name = agent.middle_name ?? ''
  form.legal_address = agent.legal_address ?? ''
  form.actual_address = agent.actual_address ?? ''
  form.inn = agent.inn ?? ''
  form.ogrnip = agent.ogrnip ?? ''
  form.account_number = agent.account_number ?? ''
  form.correspondent_account = agent.correspondent_account ?? ''
  form.bic = agent.bic ?? ''
}

async function selectAgent(agent: Agent) {
  selectedAgent.value = agent
  fillFormFromAgent(agent)
  clearAgentRelatedState()
  resetMessages()
  isAgentCardOpen.value = true
}

function validateDigits(label: string, value: string, allowedLengths: number[]) {
  const trimmed = value.trim()

  if (!trimmed) {
    return true
  }

  const digits = normalizeDigits(trimmed)
  if (digits !== trimmed || !allowedLengths.includes(digits.length)) {
    error.value = `${label}: укажите только цифры, длина ${allowedLengths.join(' или ')}`
    return false
  }

  return true
}

function validateAccount(label: string, value: string) {
  const trimmed = value.trim()

  if (!trimmed) {
    return true
  }

  const digits = normalizeDigits(trimmed)
  if (digits !== trimmed || digits.length < 20 || digits.length > 34) {
    error.value = `${label}: укажите только цифры, длина от 20 до 34`
    return false
  }

  return true
}

function validateForm() {
  if (!form.last_name.trim()) {
    error.value = 'Заполните фамилию агента'
    return false
  }

  if (!form.first_name.trim()) {
    error.value = 'Заполните имя агента'
    return false
  }

  return (
    validateDigits('ИНН', form.inn, [10, 12]) &&
    validateDigits('ОГРНИП', form.ogrnip, [15]) &&
    validateDigits('БИК', form.bic, [9]) &&
    validateAccount('Расчетный счет', form.account_number) &&
    validateAccount('Корреспондентский счет', form.correspondent_account)
  )
}

function buildCreatePayload(): AgentCreate {
  return {
    last_name: form.last_name.trim(),
    first_name: form.first_name.trim(),
    middle_name: cleanOptional(form.middle_name),
    legal_address: cleanOptional(form.legal_address),
    actual_address: cleanOptional(form.actual_address),
    inn: cleanOptional(form.inn),
    ogrnip: cleanOptional(form.ogrnip),
    account_number: cleanOptional(form.account_number),
    correspondent_account: cleanOptional(form.correspondent_account),
    bic: cleanOptional(form.bic),
  } satisfies AgentCreate
}

function buildUpdatePayload(): AgentUpdate {
  return {
    last_name: form.last_name.trim(),
    first_name: form.first_name.trim(),
    middle_name: cleanOptional(form.middle_name),
    legal_address: cleanOptional(form.legal_address),
    actual_address: cleanOptional(form.actual_address),
    inn: cleanOptional(form.inn),
    ogrnip: cleanOptional(form.ogrnip),
    account_number: cleanOptional(form.account_number),
    correspondent_account: cleanOptional(form.correspondent_account),
    bic: cleanOptional(form.bic),
  } satisfies AgentUpdate
}

async function loadAgents() {
  isLoading.value = true
  error.value = ''

  try {
    agents.value = await fetchAgents({
      skip: skip.value,
      limit: pageSize.value,
      q: query.value.trim() || undefined,
    })
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

async function searchAgents() {
  page.value = 1
  await loadAgents()
}

async function resetAgentSearch() {
  query.value = ''
  page.value = 1
  await loadAgents()
}

async function changePageSize() {
  page.value = 1
  await loadAgents()
}

async function previousPage() {
  if (!canGoBack.value) {
    return
  }

  page.value -= 1
  await loadAgents()
}

async function nextPage() {
  if (!canGoForward.value) {
    return
  }

  page.value += 1
  await loadAgents()
}

async function loadLinkedClients() {
  if (!selectedAgent.value) {
    return
  }

  const agentId = getAgentId(selectedAgent.value)
  if (!agentId) {
    clientsError.value = 'Не удалось определить ID агента'
    return
  }

  isClientsLoading.value = true
  clientsError.value = ''

  try {
    linkedClients.value = await fetchClients({
      limit: 1000,
      agent_id: agentId,
    })
  } catch (caughtError) {
    clientsError.value = getApiErrorMessage(caughtError)
  } finally {
    isClientsLoading.value = false
  }
}

async function loadAgentAudit() {
  if (!selectedAgent.value) {
    return
  }

  const agentId = getAgentId(selectedAgent.value)
  if (!agentId) {
    auditError.value = 'Не удалось определить ID агента'
    return
  }

  isAuditLoading.value = true
  auditError.value = ''

  try {
    auditItems.value = await fetchEntityAudit('agent', agentId)
  } catch (caughtError) {
    auditError.value = getApiErrorMessage(caughtError)
  } finally {
    isAuditLoading.value = false
  }
}

async function setAgentTab(tab: AgentTab) {
  if (tab !== 'edit' && !isAgentPersisted.value) {
    return
  }

  activeAgentTab.value = tab

  if (tab === 'clients' && linkedClients.value.length === 0) {
    await loadLinkedClients()
  }

  if (tab === 'history' && auditItems.value.length === 0) {
    await loadAgentAudit()
  }
}

async function saveAgent() {
  resetMessages()

  if (!validateForm()) {
    return
  }

  isSaving.value = true

  try {
    if (isEditing.value && selectedAgent.value) {
      const agentId = getAgentId(selectedAgent.value)
      const updatedAgent = await updateAgent(agentId, buildUpdatePayload())

      selectedAgent.value = updatedAgent
      fillFormFromAgent(updatedAgent)
      successMessage.value = 'Агент обновлен'
    } else {
      const createdAgent = await createAgent(buildCreatePayload())

      selectedAgent.value = createdAgent
      fillFormFromAgent(createdAgent)
      successMessage.value = 'Агент создан'
    }

    await loadAgents()

    if (activeAgentTab.value === 'clients') {
      await loadLinkedClients()
    }

    if (activeAgentTab.value === 'history') {
      await loadAgentAudit()
    }
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeAgent(agent: Agent) {
  const agentId = getAgentId(agent)

  if (!agentId) {
    error.value = 'Не удалось определить ID агента'
    return
  }

  if (!(await confirmAction({
    message: `Удалить агента «${getAgentName(agent)}»? Это действие нельзя отменить.`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteAgent(agentId)
    successMessage.value = 'Агент удален'

    if (selectedAgent.value && getAgentId(selectedAgent.value) === agentId) {
      closeAgentCard()
    }

    await loadAgents()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

watch(query, () => {
  window.clearTimeout(agentSearchTimer)
  agentSearchTimer = window.setTimeout(() => {
    void searchAgents()
  }, 380)
})

onMounted(loadAgents)

onBeforeUnmount(() => {
  window.clearTimeout(agentSearchTimer)
})
</script>

<template>
  <section class="page-section entity-workspace-page agents-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Партнёрская сеть</p>
        <h1>Агенты</h1>
        <p class="muted page-subtitle">
          Реквизиты партнёров, связанные клиенты и история взаимодействия.
        </p>
      </div>
      <button class="primary-button" type="button" @click="openNewAgent">
        <Plus :size="16" aria-hidden="true" />
        Создать агента
      </button>
    </div>

    <form class="toolbar-form agents-toolbar" @submit.prevent="searchAgents">
      <div class="toolbar-search-wrap">
        <Search :size="17" aria-hidden="true" />
        <input v-model="query" aria-label="Поиск агента" placeholder="ФИО агента или связанного клиента" />
      </div>
      <div class="filter-actions">
        <button class="secondary-button" type="submit" :disabled="isLoading">
          <Search :size="15" aria-hidden="true" />
          Найти
        </button>
        <button v-if="query" class="ghost-button" type="button" @click="resetAgentSearch">
          <X :size="15" aria-hidden="true" />
          Сбросить
        </button>
      </div>
    </form>

    <p v-if="error && !isAgentCardOpen" class="form-error">{{ error }}</p>
    <p v-if="successMessage && !isAgentCardOpen" class="form-success">{{ successMessage }}</p>

    <div class="table-wrap desktop-entity-table">
      <table>
        <thead>
          <tr>
            <th>№</th>
            <th>Агент</th>
            <th>ИНН</th>
            <th>ОГРНИП</th>
            <th>БИК</th>
            <th>Расчетный счет</th>
            <th aria-label="Действия"></th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="isLoading" class="no-row-action">
            <td colspan="7">Загружаем агентов...</td>
          </tr>

          <tr
            v-for="(agent, index) in agents"
            v-else
            :key="getAgentId(agent)"
            :class="{ selected: selectedAgent && getAgentId(selectedAgent) === getAgentId(agent) }"
            tabindex="0"
            @click="selectAgent(agent)"
            @keydown.enter="selectAgent(agent)"
          >
            <td>{{ skip + index + 1 }}</td>

            <td class="entity-cell">
              <div class="entity-primary">
                <span class="entity-avatar">{{ getAgentInitials(agent) }}</span>
                <span class="entity-copy">
                  <strong>{{ getAgentName(agent) }}</strong>
                  <span>Партнёр</span>
                </span>
              </div>
            </td>

            <td>{{ agent.inn || '-' }}</td>
            <td>{{ agent.ogrnip || '-' }}</td>
            <td>{{ agent.bic || '-' }}</td>
            <td>{{ agent.account_number || '-' }}</td>

            <td class="table-actions-cell">
              <ActionMenu :items="getAgentActions(agent)" :label="`Действия: ${getAgentName(agent)}`" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!isLoading" class="mobile-entity-list">
      <article
        v-for="agent in agents"
        :key="getAgentId(agent)"
        class="mobile-entity-card"
        @click="selectAgent(agent)"
      >
        <div class="mobile-entity-card-header">
          <div class="entity-primary">
            <span class="entity-avatar">{{ getAgentInitials(agent) }}</span>
            <span class="entity-copy">
              <strong>{{ getAgentName(agent) }}</strong>
              <span>ИНН {{ agent.inn || 'не указан' }}</span>
            </span>
          </div>
          <ActionMenu :items="getAgentActions(agent)" :label="`Действия: ${getAgentName(agent)}`" />
        </div>
        <div class="mobile-entity-card-details">
          <span>ОГРНИП <strong>{{ agent.ogrnip || '—' }}</strong></span>
          <span>БИК <strong>{{ agent.bic || '—' }}</strong></span>
          <span>Расчётный счёт <strong>{{ agent.account_number || '—' }}</strong></span>
        </div>
      </article>
    </div>

    <EmptyState
      v-if="!isLoading && agents.length === 0"
      title="Агенты не найдены"
      :description="query ? 'Измените поисковый запрос или сбросьте его.' : 'Создайте первую карточку агента.'"
    />

    <div class="pagination-bar" aria-label="Пагинация агентов">
      <span>
        Страница {{ page }} · показано {{ agents.length }} · записи
        {{ agents.length === 0 ? 0 : skip + 1 }}–{{ skip + agents.length }}
      </span>

      <div class="row-actions">
        <label class="compact-label">
          На странице
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </label>

        <button class="secondary-button" type="button" :disabled="!canGoBack" @click="previousPage">
          Назад
        </button>
        <button class="secondary-button" type="button" :disabled="!canGoForward" @click="nextPage">
          Вперед
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="isAgentCardOpen" class="modal-backdrop client-card-backdrop" @click.self="closeAgentCard" @keydown.esc.window="closeAgentCard">
        <section v-focus-trap class="modal-panel client-modal client-modal-panel entity-modal agent-profile-modal" role="dialog" aria-modal="true" aria-label="Карточка агента" :aria-busy="isSaving" @click.stop>
          <div class="modal-header">
            <div>
              <p class="eyebrow">{{ isEditing ? 'Карточка агента' : 'Новый агент' }}</p>
              <h2>{{ isEditing && selectedAgent ? getAgentName(selectedAgent) : 'Создать агента' }}</h2>
            </div>
            <div class="row-actions">
              <button class="ghost-button" type="button" :disabled="isSaving" @click="closeAgentCard">Закрыть</button>
            </div>
          </div>

          <div class="tabs" role="tablist" aria-label="Карточка агента">
            <button
              type="button"
              :class="{ active: activeAgentTab === 'edit' }"
              @click="setAgentTab('edit')"
            >
              Данные агента
            </button>
            <button
              type="button"
              :class="{ active: activeAgentTab === 'clients' }"
              :disabled="!isAgentPersisted"
              @click="setAgentTab('clients')"
            >
              Связанные клиенты
            </button>
            <button
              type="button"
              :class="{ active: activeAgentTab === 'history' }"
              :disabled="!isAgentPersisted"
              @click="setAgentTab('history')"
            >
              История
            </button>
          </div>

          <p v-if="error" class="form-error">{{ error }}</p>
          <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

          <form v-if="activeAgentTab === 'edit'" class="detail-panel" @submit.prevent="saveAgent">
            <div class="form-grid">
              <label>
                Фамилия *
                <input v-model="form.last_name" required />
              </label>

              <label>
                Имя *
                <input v-model="form.first_name" required />
              </label>

              <label>
                Отчество
                <input v-model="form.middle_name" />
              </label>
            </div>

            <label>
              Юридический адрес
              <textarea v-model="form.legal_address" rows="3" />
            </label>

            <label>
              Фактический адрес
              <textarea v-model="form.actual_address" rows="3" />
            </label>

            <div class="form-grid">
              <label>
                ИНН
                <input v-model="form.inn" autocomplete="off" inputmode="numeric" maxlength="12" />
              </label>

              <label>
                ОГРНИП
                <input v-model="form.ogrnip" autocomplete="off" inputmode="numeric" maxlength="15" />
              </label>

              <label>
                БИК
                <input v-model="form.bic" autocomplete="off" inputmode="numeric" maxlength="9" />
              </label>
            </div>

            <div class="form-grid">
              <label>
                Расчетный счет
                <input v-model="form.account_number" autocomplete="off" inputmode="numeric" maxlength="34" />
              </label>

              <label>
                Корреспондентский счет
                <input v-model="form.correspondent_account" autocomplete="off" inputmode="numeric" maxlength="34" />
              </label>
            </div>

            <button class="primary-button" type="submit" :disabled="isSaving">
              {{ isSaving ? 'Сохраняем...' : isEditing ? 'Сохранить изменения' : 'Создать агента' }}
            </button>
          </form>

          <div v-else-if="activeAgentTab === 'clients'" class="detail-panel">
            <p v-if="clientsError" class="form-error">{{ clientsError }}</p>
            <p v-if="isClientsLoading" class="muted">Загружаем связанных клиентов...</p>

            <div v-else-if="linkedClients.length" class="list-stack">
              <article v-for="client in linkedClients" :key="client.client_id" class="list-row">
                <div>
                  <strong>{{ getClientName(client) }}</strong>
                  <span>
                    {{ client.status?.description || client.status_code || 'Без статуса' }} ·
                    {{ client.stage?.description || client.current_stage || 'Без этапа' }}
                  </span>
                  <span>Повторное обращение: {{ formatDate(client.deadline) }}</span>
                </div>
              </article>
            </div>

            <p v-else class="form-hint">У этого агента пока нет связанных клиентов.</p>

            <button class="secondary-button" type="button" :disabled="isClientsLoading" @click="loadLinkedClients">
              Обновить список
            </button>
          </div>

          <div v-else class="detail-panel">
            <p v-if="auditError" class="form-error">{{ auditError }}</p>
            <p v-if="isAuditLoading" class="muted">Загружаем историю...</p>

            <div v-else-if="auditItems.length" class="audit-timeline">
              <article v-for="item in auditItems" :key="item.log_id" class="audit-item">
                <div>
                  <strong>{{ formatAuditAction(item) }}</strong>
                  <span>{{ formatAuditActor(item) }} · {{ formatAuditTime(item.timestamp) }}</span>
                </div>
                <p>{{ summarizeAuditDetails(item) }}</p>
              </article>
            </div>

            <p v-else class="form-hint">История по агенту пока пустая.</p>

            <button class="secondary-button" type="button" :disabled="isAuditLoading" @click="loadAgentAudit">
              Обновить историю
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </section>
</template>
