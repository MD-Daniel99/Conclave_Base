import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'
import LoginPage from '@/pages/LoginPage.vue'

const AppLayout = () => import('@/widgets/layout/AppLayout.vue')
const DashboardPage = () => import('@/pages/DashboardPage.vue')
const ClientsPage = () => import('@/pages/ClientsPage.vue')
const AgentsPage = () => import('@/pages/AgentsPage.vue')
const WarehousePage = () => import('@/pages/WarehousePage.vue')
const AccountingPage = () => import('@/pages/AccountingPage.vue')
const DocumentsPage = () => import('@/pages/DocumentsPage.vue')
const TsrReferencesPage = () => import('@/pages/TsrReferencesPage.vue')
const AdminUsersPage = () => import('@/pages/AdminUsersPage.vue')
const SettingsPage = () => import('@/pages/SettingsPage.vue')

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
          path: 'documents',
          redirect: { name: 'documents-contracts' },
        },
        {
          path: 'documents/contracts',
          name: 'documents-contracts',
          component: DocumentsPage,
        },
        {
          path: 'documents/mtz',
          name: 'documents-mtz',
          component: DocumentsPage,
        },
        {
          path: 'tsr-references',
          name: 'tsr-references',
          component: TsrReferencesPage,
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

