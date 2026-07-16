import { defineStore } from 'pinia'

import { fetchMe, login as loginRequest } from '@/shared/api/auth'
import { setAuthToken } from '@/shared/api/http'
import type { LoginPayload, User } from '@/shared/types/auth'

const TOKEN_KEY = 'db_crm_access_token'

interface AuthState {
  token: string | null
  user: User | null
  isBootstrapped: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem(TOKEN_KEY),
    user: null,
    isBootstrapped: false,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.role === 'admin',
  },

  actions: {
    async bootstrap() {
      if (this.isBootstrapped) return

      if (!this.token) {
        this.isBootstrapped = true
        return
      }

      setAuthToken(this.token)

      try {
        this.user = await fetchMe()
      } catch {
        this.logout()
      } finally {
        this.isBootstrapped = true
      }
    },

    async login(payload: LoginPayload) {
      const response = await loginRequest(payload)
      this.token = response.access_token
      localStorage.setItem(TOKEN_KEY, response.access_token)
      setAuthToken(response.access_token)
      this.user = await fetchMe()
      this.isBootstrapped = true
    },

    logout() {
      this.token = null
      this.user = null
      this.isBootstrapped = true
      localStorage.removeItem(TOKEN_KEY)
      setAuthToken(null)
    },
  },
})