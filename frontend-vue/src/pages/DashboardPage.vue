<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'
import { fetchRecentAudit } from '@/shared/api/audit'
import { getApiErrorMessage } from '@/shared/api/http'
import {
  formatAuditAction,
  formatAuditActor,
  formatAuditTime,
  summarizeAuditDetails,
} from '@/shared/lib/audit'
import type { AuditLogItem } from '@/shared/types/entities'

const authStore = useAuthStore()
const recentAudit = ref<AuditLogItem[]>([])
const isAuditLoading = ref(false)
const auditError = ref('')

async function loadRecentAudit() {
  if (!authStore.isAdmin) {
    return
  }

  isAuditLoading.value = true
  auditError.value = ''

  try {
    recentAudit.value = await fetchRecentAudit(20)
  } catch (caughtError) {
    auditError.value = getApiErrorMessage(caughtError)
  } finally {
    isAuditLoading.value = false
  }
}

onMounted(loadRecentAudit)
</script>

<template>
  <section class="page-section">
    <div class="page-heading hero-heading">
      <div>
        <p class="eyebrow">Обзор</p>
        <h1>Рабочая панель</h1>
        <p class="muted page-subtitle">Быстрый доступ к основным разделам и последним изменениям системы.</p>
      </div>
    </div>

    <div class="metric-grid">
      <div class="metric-card profile-metric-card">
        <span>Пользователь</span>
        <strong>{{ authStore.user?.username }}</strong>
      </div>
      <div class="metric-card profile-metric-card">
        <span>Роль</span>
        <strong>{{ authStore.user?.role }}</strong>
      </div>
      <div class="metric-card profile-metric-card">
        <span>Статус</span>
        <strong>
          <span :class="['status-badge', authStore.user?.is_active ? 'success' : 'danger']">
            {{ authStore.user?.is_active ? 'Активен' : 'Заблокирован' }}
          </span>
        </strong>
      </div>
    </div>

    <section class="page-section">
      <div class="form-heading">
        <div>
          <p class="eyebrow">Навигация</p>
          <h2>Разделы приложения</h2>
        </div>
      </div>

      <div class="quick-action-grid">
        <RouterLink class="quick-action-card" to="/clients">
          <span>👥</span>
          <strong>Клиенты</strong>
          <small>Карточки клиентов, телефоны, документы, договоры, комплектующие и история изменений.</small>
        </RouterLink>
        <RouterLink class="quick-action-card" to="/agents">
          <span>🤝</span>
          <strong>Агенты</strong>
          <small>Партнёры, реквизиты, связанные клиенты и история работы по агенту.</small>
        </RouterLink>
        <RouterLink class="quick-action-card" to="/warehouse">
          <span>📦</span>
          <strong>Склад</strong>
          <small>Учёт комплектующих, поставщиков, себестоимости и привязки к клиентам.</small>
        </RouterLink>
        <RouterLink v-if="authStore.isAdmin" class="quick-action-card" to="/accounting">
          <span>₽</span>
          <strong>Бухгалтерия</strong>
          <small>Расчёт прибыли, расходов, налогов, эквайринга и дополнительных полей.</small>
        </RouterLink>
        <RouterLink v-if="authStore.isAdmin" class="quick-action-card" to="/admin/users">
          <span>🛡</span>
          <strong>Пользователи</strong>
          <small>Создание пользователей, роли, блокировка и история изменений.</small>
        </RouterLink>
        <RouterLink class="quick-action-card" to="/settings">
          <span>⚙</span>
          <strong>Настройки</strong>
          <small>Изменение собственного логина и пароля, информация о роли и состоянии учетной записи.</small>
        </RouterLink>
      </div>
    </section>

    <section v-if="authStore.isAdmin" class="page-section">
      <div class="form-heading">
        <div>
          <p class="eyebrow">Контроль изменений</p>
          <h2>Последние действия</h2>
        </div>
        <button class="secondary-button" type="button" :disabled="isAuditLoading" @click="loadRecentAudit">
          {{ isAuditLoading ? 'Обновляем...' : 'Обновить' }}
        </button>
      </div>

      <p v-if="auditError" class="form-error">{{ auditError }}</p>
      <div v-if="isAuditLoading" class="loading-state">Загружаем историю...</div>

      <div v-else-if="recentAudit.length" class="audit-timeline audit-timeline-card">
        <article v-for="item in recentAudit" :key="item.log_id" class="audit-item">
          <div>
            <strong>{{ formatAuditAction(item) }}</strong>
            <span>{{ formatAuditActor(item) }} · {{ formatAuditTime(item.timestamp) }}</span>
          </div>
          <p>{{ summarizeAuditDetails(item) }}</p>
        </article>
      </div>

      <p v-else class="empty-state">История изменений пока пустая.</p>
    </section>
  </section>
</template>
