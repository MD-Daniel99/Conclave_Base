<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Activity,
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from '@lucide/vue'

import { useAuthStore } from '@/app/stores/auth'
import { getApiErrorMessage } from '@/shared/api/http'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
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
    <section class="login-shell" aria-label="Вход в DB CRM">
      <div class="login-showcase">
        <div class="login-brand">
          <span class="brand-mark">DB</span>
          <div>
            <strong>DB CRM</strong>
            <span>Единая рабочая среда</span>
          </div>
        </div>

        <div class="login-copy">
          <p class="eyebrow">Управляйте процессом целиком</p>
          <h2>Все клиенты, документы и комплектующие — в одном ритме.</h2>
          <p>
            Рабочая панель помогает команде видеть актуальный этап каждого клиента,
            контролировать сроки и быстро переходить к нужному действию.
          </p>
        </div>

        <div class="login-benefits" aria-label="Преимущества системы">
          <span class="login-benefit"><Activity :size="15" aria-hidden="true" /> Живые статусы</span>
          <span class="login-benefit"><ShieldCheck :size="15" aria-hidden="true" /> Контроль доступа</span>
          <span class="login-benefit"><LockKeyhole :size="15" aria-hidden="true" /> Защищённые данные</span>
        </div>
      </div>

      <div class="login-panel-wrap">
        <form class="login-panel" @submit.prevent="submit">
          <div class="login-panel-heading">
            <p class="eyebrow">Добро пожаловать</p>
            <h1>Вход в систему</h1>
            <p>Используйте свою рабочую учётную запись.</p>
          </div>

          <label class="login-field">
            Логин
            <UserRound class="login-field-icon" :size="18" aria-hidden="true" />
            <input
              v-model="username"
              autocomplete="username"
              autofocus
              placeholder="Введите логин"
            />
          </label>

          <label class="login-field">
            Пароль
            <LockKeyhole class="login-field-icon" :size="18" aria-hidden="true" />
            <input
              v-model="password"
              autocomplete="current-password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Введите пароль"
            />
            <button
              class="icon-button password-toggle"
              type="button"
              :aria-label="showPassword ? 'Скрыть пароль' : 'Показать пароль'"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" :size="17" aria-hidden="true" />
              <Eye v-else :size="17" aria-hidden="true" />
            </button>
          </label>

          <p v-if="error" class="form-error" role="alert">{{ error }}</p>

          <button
            class="primary-button login-submit"
            :disabled="!canSubmit || isSubmitting"
            type="submit"
          >
            {{ isSubmitting ? 'Проверяем данные...' : 'Войти в систему' }}
            <ArrowRight v-if="!isSubmitting" :size="17" aria-hidden="true" />
          </button>

          <span class="login-security">
            <LockKeyhole :size="13" aria-hidden="true" />
            Данные передаются по защищённому соединению
          </span>
        </form>
      </div>
    </section>
  </main>
</template>
