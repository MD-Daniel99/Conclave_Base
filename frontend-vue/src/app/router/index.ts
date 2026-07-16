import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'
import AppLayout from '@/widgets/layout/AppLayout.vue'
import LoginPage from '@/pages/LoginPage.vue'
import DashboardPage from '@/pages/DashboardPage.vue'
import ClientsPage from '@/pages/ClientsPage.vue'
import AgentsPage from '@/pages/AgentsPage.vue'
import WarehousePage from '@/pages/WarehousePage.vue'
import AccountingPage from '@/pages/AccountingPage.vue'
import AdminUsersPage from '@/pages/AdminUsersPage.vue'
import SettingsPage from '@/pages/SettingsPage.vue'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { public: true },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardPage,
        },
        {
          path: 'clients',
          name: 'clients',
          component: ClientsPage,
        },
        {
          path: 'agents',
          name: 'agents',
          component: AgentsPage,
        },
        {
          path: 'warehouse',
          name: 'warehouse',
          component: WarehousePage,
        },
        {
          path: 'accounting',
          name: 'accounting',
          component: AccountingPage,
          meta: { requiresAdmin: true },
        },
        {
          path: 'admin/users',
          name: 'admin-users',
          component: AdminUsersPage,
          meta: { requiresAdmin: true },
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsPage,
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  await authStore.bootstrap()

  if (to.meta.public) {
    if (authStore.isAuthenticated && to.name === 'login') {
      return { name: 'dashboard' }
    }

    return true
  }

  if (!authStore.isAuthenticated) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: 'dashboard' }
  }

  return true
})
