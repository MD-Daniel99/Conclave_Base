<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import Skeleton from 'primevue/skeleton'
import {
  ArrowRight,
  FileWarning,
  Handshake,
  Landmark,
  PackageOpen,
  RefreshCw,
  Settings,
  ShieldCheck,
  UserPlus,
  UsersRound,
} from '@lucide/vue'

import { useAuthStore } from '@/app/stores/auth'
import { fetchAgents } from '@/shared/api/agents'
import { fetchRecentAudit } from '@/shared/api/audit'
import { fetchClientContractCoverage } from '@/shared/api/accounting'
import { fetchClients } from '@/shared/api/clients'
import { fetchStockComponentCount } from '@/shared/api/components'
import { getApiErrorMessage } from '@/shared/api/http'
import EmptyState from '@/shared/ui/EmptyState.vue'
import StatusPill from '@/shared/ui/StatusPill.vue'
import {
  formatAuditAction,
  formatAuditActor,
  formatAuditTime,
  summarizeAuditDetails,
} from '@/shared/lib/audit'
import type { Agent, AuditLogItem, Client } from '@/shared/types/entities'

const authStore = useAuthStore()
const recentAudit = ref<AuditLogItem[]>([])
const clients = ref<Client[]>([])
const agents = ref<Agent[]>([])
const stockComponentCount = ref(0)
const clientsWithoutContracts = ref<number | null>(null)
const isLoading = ref(false)
const dashboardError = ref('')

const recentClients = computed(() => [...clients.value]
  .sort((left, right) => String(right.updated_at ?? '').localeCompare(String(left.updated_at ?? '')))
  .slice(0, 5))

const quickActions = computed(() => [
  {
    to: '/clients',
    label: 'Пациенты',
    description: 'Карточки и этапы',
    icon: UsersRound,
  },
  {
    to: '/agents',
    label: 'Агенты',
    description: `${agents.value.length || '—'} партнёров`,
    icon: Handshake,
  },
  {
    to: '/warehouse',
    label: 'Склад',
    description: 'Комплектующие',
    icon: PackageOpen,
  },
  ...(authStore.isAdmin ? [
    {
      to: '/accounting',
      label: 'Бухгалтерия',
      description: 'Расходы и прибыль',
      icon: Landmark,
    },
    {
      to: '/admin/users',
      label: 'Пользователи',
      description: 'Роли и доступ',
      icon: ShieldCheck,
    },
  ] : []),
  {
    to: '/settings',
    label: 'Настройки',
    description: 'Учётная запись',
    icon: Settings,
  },
])

function getClientName(client: Client) {
  return [client.last_name, client.first_name, client.middle_name].filter(Boolean).join(' ') || 'Без имени'
}

function getClientStatus(client: Client) {
  return client.status?.description || client.status_code || 'Без статуса'
}

function getClientStage(client: Client) {
  return client.stage?.description || client.current_stage || 'Без этапа'
}

function getInitials(client: Client) {
  return [client.last_name, client.first_name]
    .filter(Boolean)
    .map((item) => String(item).slice(0, 1))
    .join('')
    .toUpperCase() || 'КЛ'
}

function formatDate(value?: string | null) {
  if (!value) return 'Не указана'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

async function loadDashboard() {
  isLoading.value = true
  dashboardError.value = ''

  const requests = [
    fetchClients({ limit: 1000, archived: false }),
    fetchAgents({ limit: 1000 }),
    fetchStockComponentCount(),
    fetchClientContractCoverage(),
    authStore.isAdmin ? fetchRecentAudit(12) : Promise.resolve([]),
  ] as const

  const [clientResult, agentResult, stockResult, coverageResult, auditResult] = await Promise.allSettled(requests)

  if (clientResult.status === 'fulfilled') clients.value = clientResult.value
  if (agentResult.status === 'fulfilled') agents.value = agentResult.value
  if (stockResult.status === 'fulfilled') stockComponentCount.value = stockResult.value
  if (coverageResult.status === 'fulfilled') {
    clientsWithoutContracts.value = coverageResult.value.filter((item) => item.requires_contract).length
  }
  if (auditResult.status === 'fulfilled') recentAudit.value = auditResult.value

  const failure = [clientResult, agentResult, stockResult, coverageResult, auditResult]
    .find((result) => result.status === 'rejected')

  if (failure?.status === 'rejected') {
    dashboardError.value = getApiErrorMessage(failure.reason)
  }

  isLoading.value = false
}

onMounted(loadDashboard)
</script>

<template>
  <section class="page-section dashboard-page">
    <div class="page-heading hero-heading">
      <div>
        <p class="eyebrow">Центр управления</p>
        <h1>Здравствуйте, {{ authStore.user?.username }}</h1>
        <p class="muted page-subtitle">
          Главное по пациентам, срокам и складу — без переходов между разделами.
        </p>
      </div>
      <div class="row-actions page-heading-actions">
        <button class="secondary-button" type="button" :disabled="isLoading" @click="loadDashboard">
          <RefreshCw :size="16" :class="{ 'is-spinning': isLoading }" aria-hidden="true" />
          Обновить
        </button>
        <RouterLink class="primary-button" to="/clients">
          <UserPlus :size="16" aria-hidden="true" />
          Новый пациент
        </RouterLink>
      </div>
    </div>

    <p v-if="dashboardError" class="form-error" role="alert">
      Часть показателей временно недоступна: {{ dashboardError }}
    </p>

    <div v-if="isLoading && clients.length === 0" class="metric-grid dashboard-metrics">
      <Skeleton v-for="index in 3" :key="index" height="138px" border-radius="18px" />
    </div>

    <div v-else class="metric-grid dashboard-metrics">
      <article class="metric-card">
        <div class="metric-card-header">
          <span>Активные пациенты</span>
          <span class="metric-icon"><UsersRound :size="19" aria-hidden="true" /></span>
        </div>
        <strong>{{ clients.length }}</strong>
        <span class="metric-trend">Все текущие рабочие карточки</span>
      </article>

      <article class="metric-card metric-card-contracts">
        <div class="metric-card-header">
          <span>Пациентов без договоров</span>
          <span class="metric-icon amber"><FileWarning :size="19" aria-hidden="true" /></span>
        </div>
        <strong>{{ clientsWithoutContracts ?? '—' }}</strong>
        <span class="metric-trend">
          {{ clientsWithoutContracts === null ? 'Показатель временно недоступен' : 'Пациенты, для которых договор ещё не сформирован' }}
        </span>
      </article>

      <article class="metric-card metric-card-stock">
        <div class="metric-card-header">
          <span>Комплектующих на складе</span>
          <span class="metric-icon teal"><PackageOpen :size="19" aria-hidden="true" /></span>
        </div>
        <strong>{{ stockComponentCount }}</strong>
        <span class="metric-trend">Актуальные свободные единицы комплектующих</span>
      </article>
    </div>

    <div class="dashboard-grid">
      <section class="surface-panel dashboard-panel">
        <div class="dashboard-panel-heading">
          <div>
            <h2>Недавно обновлённые пациенты</h2>
            <p>Карточки, в которых были последние изменения</p>
          </div>
          <RouterLink class="ghost-button" to="/clients">
            Все пациенты
            <ArrowRight :size="15" aria-hidden="true" />
          </RouterLink>
        </div>

        <div v-if="recentClients.length" class="dashboard-client-list">
          <RouterLink
            v-for="client in recentClients"
            :key="String(client.client_id)"
            class="dashboard-client-row"
            :to="{ name: 'clients', query: { client_id: client.client_id } }"
          >
            <span class="entity-avatar">{{ getInitials(client) }}</span>
            <span class="entity-copy">
              <strong>{{ getClientName(client) }}</strong>
              <span>Обновлён {{ formatDate(client.updated_at) }}</span>
            </span>
            <StatusPill :label="getClientStatus(client)" kind="status" />
            <StatusPill :label="getClientStage(client)" kind="stage" />
            <ArrowRight class="quick-action-arrow" :size="16" aria-hidden="true" />
          </RouterLink>
        </div>
        <EmptyState
          v-else
          title="Пациентов пока нет"
          description="Создайте первую карточку, чтобы она появилась в рабочем обзоре."
        />
      </section>

      <section class="surface-panel dashboard-panel">
        <div class="dashboard-panel-heading">
          <div>
            <h2>{{ authStore.isAdmin ? 'Последние действия' : 'Быстрый доступ' }}</h2>
            <p>{{ authStore.isAdmin ? 'Изменения в системе' : 'Основные разделы' }}</p>
          </div>
        </div>

        <div v-if="authStore.isAdmin && recentAudit.length" class="audit-timeline dashboard-audit">
          <article v-for="item in recentAudit.slice(0, 6)" :key="item.log_id" class="audit-item">
            <div>
              <strong>{{ formatAuditAction(item) }}</strong>
              <span>{{ formatAuditActor(item) }} · {{ formatAuditTime(item.timestamp) }}</span>
            </div>
            <p>{{ summarizeAuditDetails(item) }}</p>
          </article>
        </div>
        <EmptyState
          v-else-if="authStore.isAdmin"
          title="История пока пустая"
          description="Новые действия появятся здесь автоматически."
        />

        <div v-else class="quick-action-grid">
          <RouterLink v-for="item in quickActions" :key="item.to" class="quick-action-card" :to="item.to">
            <span><component :is="item.icon" :size="18" aria-hidden="true" /></span>
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </span>
            <ArrowRight class="quick-action-arrow" :size="15" aria-hidden="true" />
          </RouterLink>
        </div>
      </section>
    </div>

    <section class="surface-panel dashboard-panel">
      <div class="dashboard-panel-heading">
        <div>
          <h2>Рабочие разделы</h2>
          <p>Быстрый переход к ежедневным операциям</p>
        </div>
      </div>
      <div class="quick-action-grid dashboard-quick-actions">
        <RouterLink v-for="item in quickActions" :key="item.to" class="quick-action-card" :to="item.to">
          <span><component :is="item.icon" :size="18" aria-hidden="true" /></span>
          <span>
            <strong>{{ item.label }}</strong>
            <small>{{ item.description }}</small>
          </span>
          <ArrowRight class="quick-action-arrow" :size="15" aria-hidden="true" />
        </RouterLink>
      </div>
    </section>
  </section>
</template>
