<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import Drawer from 'primevue/drawer'
import Menu from 'primevue/menu'
import {
  ChevronDown,
  FileText,
  Handshake,
  Landmark,
  ListTree,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  PackageOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
} from '@lucide/vue'

import { useAuthStore } from '@/app/stores/auth'
import { touchPresence } from '@/shared/api/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const isSidebarCollapsed = ref(localStorage.getItem('db.sidebar.collapsed') === 'true')
const isMobileMenuOpen = ref(false)
const profileMenu = ref<InstanceType<typeof Menu> | null>(null)
let presenceTimer: number | undefined

type NavigationItem = {
  to: string
  label: string
  icon: Component
  adminOnly?: boolean
  children?: Array<{ to: string; label: string }>
}

const allNavigationItems: NavigationItem[] = [
  { to: '/', label: 'Обзор', icon: LayoutDashboard },
  { to: '/clients', label: 'Пациенты', icon: UsersRound },
  { to: '/agents', label: 'Агенты', icon: Handshake },
  { to: '/warehouse', label: 'Склад', icon: PackageOpen },
  {
    to: '/documents/contracts',
    label: 'Документы',
    icon: FileText,
    children: [
      { to: '/documents/contracts', label: 'Договоры' },
      { to: '/documents/mtz', label: 'МТЗ' },
    ],
  },
  { to: '/tsr-references', label: 'Справочник ТСР', icon: ListTree },
  { to: '/accounting', label: 'Бухгалтерия', icon: Landmark, adminOnly: true },
  { to: '/admin/users', label: 'Пользователи', icon: ShieldCheck, adminOnly: true },
  { to: '/settings', label: 'Настройки', icon: Settings },
]

const navigationItems = computed(() => allNavigationItems.filter((item) => !item.adminOnly || authStore.isAdmin))

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    dashboard: 'Обзор',
    clients: 'Клиенты',
    agents: 'Агенты',
    warehouse: 'Склад',
    'documents-contracts': 'Документы · Договоры',
    'documents-mtz': 'Документы · МТЗ',
    'tsr-references': 'Справочник ТСР',
    accounting: 'Бухгалтерия',
    'admin-users': 'Пользователи',
    settings: 'Настройки',
  }

  return titles[String(route.name ?? '')] ?? 'Рабочая панель'
})

const roleLabel = computed(() => authStore.isAdmin ? 'Администратор' : 'Сотрудник')
const userInitials = computed(() => {
  const value = authStore.user?.username?.trim() || 'DB'
  return value.slice(0, 2).toUpperCase()
})
const currentDate = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
}).format(new Date())

const profileActions = computed(() => [
  {
    label: 'Настройки профиля',
    command: () => router.push({ name: 'settings' }),
  },
  {
    separator: true,
  },
  {
    label: 'Выйти из системы',
    class: 'danger-menu-item',
    command: logout,
  },
])

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  localStorage.setItem('db.sidebar.collapsed', String(isSidebarCollapsed.value))
}

function toggleProfileMenu(event: Event) {
  profileMenu.value?.toggle(event)
}

async function refreshPresence() {
  if (!authStore.isAuthenticated) return
  try {
    await touchPresence()
  } catch {
    // Presence is auxiliary and must never interrupt the application.
  }
}

onMounted(() => {
  void refreshPresence()
  presenceTimer = window.setInterval(() => { void refreshPresence() }, 30_000)
})

onBeforeUnmount(() => {
  if (presenceTimer) window.clearInterval(presenceTimer)
})

function logout() {
  authStore.logout()
  router.push({ name: 'login' })
}

watch(
  () => route.fullPath,
  () => {
    isMobileMenuOpen.value = false
  },
)
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <aside class="sidebar" :aria-label="isSidebarCollapsed ? 'Свернутое меню' : 'Главное меню'">
      <div class="brand">
        <span class="brand-mark">DB</span>
        <div class="brand-text">
          <strong>DB CRM</strong>
          <small>Управление клиентами</small>
        </div>
      </div>

      <button
        class="sidebar-toggle"
        type="button"
        :aria-label="isSidebarCollapsed ? 'Развернуть боковое меню' : 'Свернуть боковое меню'"
        :title="isSidebarCollapsed ? 'Развернуть меню' : 'Свернуть меню'"
        @click="toggleSidebar"
      >
        <PanelLeftOpen v-if="isSidebarCollapsed" :size="15" aria-hidden="true" />
        <PanelLeftClose v-else :size="15" aria-hidden="true" />
      </button>

      <p class="sidebar-section-label">Рабочая область</p>
      <nav class="nav-list" aria-label="Главное меню">
        <template v-for="item in navigationItems" :key="item.to">
          <RouterLink
            v-tooltip.right="isSidebarCollapsed ? item.label : ''"
            :to="item.to"
            :title="isSidebarCollapsed ? item.label : undefined"
            :class="{ 'nav-parent-active': item.children?.some((child) => route.path === child.to) }"
          >
            <span class="nav-icon"><component :is="item.icon" :size="18" aria-hidden="true" /></span>
            <span class="nav-text">{{ item.label }}</span>
          </RouterLink>
          <div v-if="item.children?.length && !isSidebarCollapsed" class="nav-subitems" aria-label="Подразделы документов">
            <RouterLink v-for="child in item.children" :key="child.to" :to="child.to" class="nav-subitem">
              <span class="nav-subitem-dot" aria-hidden="true"></span>
              <span>{{ child.label }}</span>
            </RouterLink>
          </div>
        </template>
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-profile">
          <span class="user-avatar">{{ userInitials }}</span>
          <div class="sidebar-profile-copy">
            <strong>{{ authStore.user?.username }}</strong>
            <span>{{ roleLabel }}</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="main-column">
      <header class="topbar">
        <div class="topbar-title">
          <button
            class="icon-button mobile-menu-button"
            type="button"
            aria-label="Открыть меню"
            @click="isMobileMenuOpen = true"
          >
            <MenuIcon :size="19" aria-hidden="true" />
          </button>
          <div>
            <p class="topbar-kicker">Рабочее пространство</p>
            <h1>{{ pageTitle }}</h1>
          </div>
        </div>

        <div class="topbar-context">
          <span class="topbar-date">{{ currentDate }}</span>
          <button
            class="topbar-profile-button"
            type="button"
            aria-label="Открыть меню профиля"
            aria-haspopup="menu"
            @click="toggleProfileMenu"
          >
            <span class="user-avatar">{{ userInitials }}</span>
            <span class="topbar-profile-copy">
              <strong>{{ authStore.user?.username }}</strong>
              <span>{{ roleLabel }}</span>
            </span>
            <ChevronDown :size="15" aria-hidden="true" />
          </button>
          <Menu ref="profileMenu" :model="profileActions" popup class="app-action-menu" />
        </div>
      </header>

      <main class="page-frame">
        <RouterView />
      </main>
    </div>
  </div>

  <Drawer
    v-model:visible="isMobileMenuOpen"
    position="left"
    class="mobile-nav-drawer"
    :show-close-icon="false"
  >
    <template #header>
      <div class="brand">
        <span class="brand-mark">DB</span>
        <div class="brand-text">
          <strong>DB CRM</strong>
          <small>Управление клиентами</small>
        </div>
      </div>
      <button
        class="icon-button mobile-drawer-close"
        type="button"
        aria-label="Закрыть меню"
        @click="isMobileMenuOpen = false"
      >
        <X :size="18" aria-hidden="true" />
      </button>
    </template>

    <p class="sidebar-section-label">Рабочая область</p>
    <nav class="nav-list" aria-label="Мобильное меню">
      <template v-for="item in navigationItems" :key="item.to">
        <RouterLink :to="item.to" @click="isMobileMenuOpen = false">
          <span class="nav-icon"><component :is="item.icon" :size="18" aria-hidden="true" /></span>
          <span class="nav-text">{{ item.label }}</span>
        </RouterLink>
        <div v-if="item.children?.length" class="nav-subitems mobile-nav-subitems">
          <RouterLink v-for="child in item.children" :key="child.to" :to="child.to" class="nav-subitem" @click="isMobileMenuOpen = false">
            <span class="nav-subitem-dot" aria-hidden="true"></span>
            <span>{{ child.label }}</span>
          </RouterLink>
        </div>
      </template>
    </nav>

    <div class="sidebar-footer">
      <div class="sidebar-profile">
        <span class="user-avatar"><UserRound :size="17" aria-hidden="true" /></span>
        <div class="sidebar-profile-copy">
          <strong>{{ authStore.user?.username }}</strong>
          <span>{{ roleLabel }}</span>
        </div>
      </div>
      <button class="ghost-button" type="button" @click="logout">
        <LogOut :size="17" aria-hidden="true" />
        Выйти
      </button>
    </div>
  </Drawer>
</template>

