<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import Drawer from 'primevue/drawer'
import Menu from 'primevue/menu'
import {
  Bell,
  CalendarDays,
  CheckCheck,
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
import { fetchTaskNotifications, markAllTaskNotificationsRead, markTaskNotificationRead, type TaskNotification } from '@/shared/api/tasks'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const isSidebarCollapsed = ref(localStorage.getItem('db.sidebar.collapsed') === 'true')
const isMobileMenuOpen = ref(false)
const profileMenu = ref<InstanceType<typeof Menu> | null>(null)
let presenceTimer: number | undefined
let notificationTimer: number | undefined
const notifications = ref<TaskNotification[]>([])
const isNotificationsOpen = ref(false)
const notificationsLoading = ref(false)
const unreadNotifications = computed(() => notifications.value.filter((item) => !item.read_at).length)

type NavigationItem = {
  to: string
  label: string
  icon: Component
  adminOnly?: boolean
  children?: Array<{ to: string; label: string }>
}

const allNavigationItems: NavigationItem[] = [
  { to: '/', label: 'Обзор', icon: LayoutDashboard },
  { to: '/calendar', label: 'Календарь', icon: CalendarDays },
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
  {
    to: '/references/tsr',
    label: 'Справочники',
    icon: ListTree,
    children: [
      { to: '/references/tsr', label: 'ТСР' },
      { to: '/references/components', label: 'Комплектующие' },
    ],
  },
  { to: '/accounting', label: 'Бухгалтерия', icon: Landmark, adminOnly: true },
  { to: '/admin/users', label: 'Пользователи', icon: ShieldCheck, adminOnly: true },
  { to: '/settings', label: 'Настройки', icon: Settings },
]

const navigationItems = computed(() => allNavigationItems.filter((item) => !item.adminOnly || authStore.isAdmin))

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    dashboard: 'Обзор',
    calendar: 'Календарь и задачи',
    clients: 'Клиенты',
    agents: 'Агенты',
    warehouse: 'Склад',
    'documents-contracts': 'Документы · Договоры',
    'documents-mtz': 'Документы · МТЗ',
    'references-tsr': 'Справочники · ТСР',
    'references-components': 'Справочники · Комплектующие',
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

async function refreshNotifications(silent = true) {
  if (!authStore.isAuthenticated) return
  if (!silent) notificationsLoading.value = true
  try {
    notifications.value = await fetchTaskNotifications(false, 30)
  } catch {
    // Notifications are auxiliary and must never interrupt navigation.
  } finally {
    if (!silent) notificationsLoading.value = false
  }
}

async function toggleNotifications() {
  isNotificationsOpen.value = !isNotificationsOpen.value
  if (isNotificationsOpen.value) await refreshNotifications(false)
}

async function openNotification(item: TaskNotification) {
  if (!item.read_at) {
    try {
      await markTaskNotificationRead(item.notification_id)
      item.read_at = new Date().toISOString()
    } catch {
      // Navigation to the task is still useful even when marking failed.
    }
  }
  isNotificationsOpen.value = false
  await router.push({ name: 'calendar', query: { task: item.task_id } })
}

async function markAllNotifications() {
  try {
    await markAllTaskNotificationsRead()
    const now = new Date().toISOString()
    notifications.value = notifications.value.map((item) => ({ ...item, read_at: item.read_at ?? now }))
  } catch {
    // Keep the panel functional; the next poll will retry naturally.
  }
}

function notificationTime(value: string) {
  const date = new Date(value)
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return 'только что'
  if (diff < 3_600_000) return `${Math.max(1, Math.floor(diff / 60_000))} мин. назад`
  if (diff < 86_400_000) return `${Math.max(1, Math.floor(diff / 3_600_000))} ч. назад`
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}

function onAppVisibilityChange() {
  if (document.visibilityState === 'visible') {
    void refreshPresence()
    void refreshNotifications()
  }
}

function onNotificationOutsidePointerDown(event: PointerEvent) {
  if (!isNotificationsOpen.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('.task-notification-wrap')) return
  isNotificationsOpen.value = false
}

onMounted(() => {
  void refreshPresence()
  void refreshNotifications()
  presenceTimer = window.setInterval(() => { void refreshPresence() }, 30_000)
  notificationTimer = window.setInterval(() => { void refreshNotifications() }, 20_000)
  document.addEventListener('visibilitychange', onAppVisibilityChange)
  document.addEventListener('pointerdown', onNotificationOutsidePointerDown)
})

onBeforeUnmount(() => {
  if (presenceTimer) window.clearInterval(presenceTimer)
  if (notificationTimer) window.clearInterval(notificationTimer)
  document.removeEventListener('visibilitychange', onAppVisibilityChange)
  document.removeEventListener('pointerdown', onNotificationOutsidePointerDown)
})

function logout() {
  authStore.logout()
  router.push({ name: 'login' })
}

watch(
  () => route.fullPath,
  () => {
    isMobileMenuOpen.value = false
    isNotificationsOpen.value = false
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
          <div class="task-notification-wrap">
            <button
              class="task-notification-button"
              type="button"
              :aria-label="unreadNotifications ? `Уведомления: ${unreadNotifications} новых` : 'Уведомления'"
              :aria-expanded="isNotificationsOpen"
              @click="toggleNotifications"
            >
              <Bell :size="19" aria-hidden="true" />
              <span v-if="unreadNotifications" class="task-notification-badge">{{ unreadNotifications > 99 ? '99+' : unreadNotifications }}</span>
            </button>
            <div v-if="isNotificationsOpen" class="task-notification-panel">
              <header class="task-notification-header">
                <div>
                  <strong>Уведомления</strong>
                  <span>{{ unreadNotifications ? `${unreadNotifications} непрочитанных` : 'Всё просмотрено' }}</span>
                </div>
                <button v-if="unreadNotifications" type="button" title="Прочитать все" @click="markAllNotifications"><CheckCheck :size="17" /></button>
              </header>
              <div class="task-notification-list">
                <button
                  v-for="item in notifications"
                  :key="item.notification_id"
                  type="button"
                  class="task-notification-item"
                  :class="{ unread: !item.read_at, overdue: item.kind === 'overdue' }"
                  @click="openNotification(item)"
                >
                  <span class="task-notification-dot"></span>
                  <span class="task-notification-copy">
                    <strong>{{ item.title }}</strong>
                    <span>{{ item.body || item.task_title }}</span>
                    <small>{{ notificationTime(item.created_at) }}</small>
                  </span>
                </button>
                <div v-if="!notifications.length && !notificationsLoading" class="task-notification-empty">
                  <Bell :size="25" />
                  <span>Новых уведомлений нет</span>
                </div>
                <div v-if="notificationsLoading && !notifications.length" class="task-notification-empty">Загрузка…</div>
              </div>
              <RouterLink class="task-notification-footer" to="/calendar" @click="isNotificationsOpen = false">Открыть календарь</RouterLink>
            </div>
          </div>
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

