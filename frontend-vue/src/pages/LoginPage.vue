<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/app/stores/auth'
import { getApiErrorMessage } from '@/shared/api/http'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const isSubmitting = ref(false)

const canSubmit = computed(() => username.value.trim().length > 0 && password.value.length > 0)

async function submit() {
  if (!canSubmit.value || isSubmitting.value) {
    return
  }

  error.value = ''
  isSubmitting.value = true

  try {
    await authStore.login({
      username: username.value.trim(),
      password: password.value,
    })

    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <form class="login-panel" @submit.prevent="submit">
      <div>
        <p class="eyebrow">DB CRM</p>
        <h1>Вход в систему</h1>
      </div>

      <label>
        Логин
        <input v-model="username" autocomplete="username" autofocus />
      </label>

      <label>
        Пароль
        <input v-model="password" autocomplete="current-password" type="password" />
      </label>

      <p v-if="error" class="form-error">{{ error }}</p>

      <button class="primary-button" :disabled="!canSubmit || isSubmitting" type="submit">
        {{ isSubmitting ? 'Входим...' : 'Войти' }}
      </button>
    </form>
  </main>
</template>
