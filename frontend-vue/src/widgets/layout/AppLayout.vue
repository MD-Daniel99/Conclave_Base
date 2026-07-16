<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const isSidebarCollapsed = ref(localStorage.getItem('db.sidebar.collapsed') === 'true')

const userLabel = computed(() => {
  if (!authStore.user) {
    return ''
  }

  return `${authStore.user.username} · ${authStore.user.role}`
})

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    dashboard: 'Обзор',
    clients: 'Клиенты',
    agents: 'Агенты',
    warehouse: 'Склад',
    accounting: 'Бухгалтерия',
    'admin-users': 'Пользователи',
    settings: 'Настройки',
  }

  return titles[String(route.name ?? '')] ?? 'Рабочая панель'
})

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  localStorage.setItem('db.sidebar.collapsed', String(isSidebarCollapsed.value))
}

function logout() {
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <aside class="sidebar" :aria-label="isSidebarCollapsed ? 'Свернутое меню' : 'Главное меню'">
      <div class="brand">
        <span class="brand-mark">DB</span>
        <div class="brand-text">
          <strong>CRM</strong>
          <small>Рабочая панель</small>
        </div>
      </div>

      <button
        class="sidebar-toggle"
        type="button"
        :aria-label="isSidebarCollapsed ? 'Развернуть боковое меню' : 'Свернуть боковое меню'"
        :title="isSidebarCollapsed ? 'Развернуть меню' : 'Свернуть меню'"
        @click="toggleSidebar"
      >
        {{ isSidebarCollapsed ? '→' : '←' }}
      </button>

      <nav class="nav-list" aria-label="Главное меню">
        <RouterLink to="/" title="Обзор"><span class="nav-icon">⌂</span><span class="nav-text">Обзор</span></RouterLink>
        <RouterLink to="/clients" title="Клиенты"><span class="nav-icon">👥</span><span class="nav-text">Клиенты</span></RouterLink>
        <RouterLink to="/agents" title="Агенты"><span class="nav-icon">🤝</span><span class="nav-text">Агенты</span></RouterLink>
        <RouterLink to="/warehouse" title="Склад"><span class="nav-icon">📦</span><span class="nav-text">Склад</span></RouterLink>
        <RouterLink v-if="authStore.isAdmin" to="/accounting" title="Бухгалтерия"><span class="nav-icon">₽</span><span class="nav-text">Бухгалтерия</span></RouterLink>
        <RouterLink v-if="authStore.isAdmin" to="/admin/users" title="Пользователи"><span class="nav-icon">🛡</span><span class="nav-text">Пользователи</span></RouterLink>
        <RouterLink to="/settings" title="Настройки"><span class="nav-icon">⚙</span><span class="nav-text">Настройки</span></RouterLink>
      </nav>
    </aside>

    <div class="main-column">
      <header class="topbar">
        <div>
          <span class="muted">{{ pageTitle }}</span>
          <strong>{{ userLabel }}</strong>
        </div>
        <div class="row-actions">
          <button class="secondary-button topbar-menu-button" type="button" @click="toggleSidebar">
            {{ isSidebarCollapsed ? 'Показать меню' : 'Скрыть меню' }}
          </button>
          <button class="ghost-button" type="button" @click="logout">Выйти</button>
        </div>
      </header>

      <main class="page-frame">
        <RouterView />
      </main>
    </div>
  </div>
</template>
