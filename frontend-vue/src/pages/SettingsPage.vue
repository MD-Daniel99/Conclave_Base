<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { useAuthStore } from '@/app/stores/auth'
import { updateUser } from '@/shared/api/auth'
import { getApiErrorMessage } from '@/shared/api/http'
import { useSuccessToast } from '@/shared/composables/useAppFeedback'

const authStore = useAuthStore()
const isSaving = ref(false)
const error = ref('')
const successMessage = ref('')
useSuccessToast(successMessage, 'Настройки')
const accountForm = reactive({
  username: '',
  password: '',
  passwordConfirmation: '',
})

const hasAccountChanges = computed(() => (
  accountForm.username.trim() !== String(authStore.user?.username ?? '')
  || Boolean(accountForm.password)
))

function syncAccountForm() {
  accountForm.username = String(authStore.user?.username ?? '')
  accountForm.password = ''
  accountForm.passwordConfirmation = ''
}

async function saveAccount() {
  error.value = ''
  successMessage.value = ''

  const currentUser = authStore.user
  if (!currentUser?.user_id) {
    error.value = 'Не удалось определить текущего пользователя.'
    return
  }

  const username = accountForm.username.trim()
  if (!username) {
    error.value = 'Логин не может быть пустым.'
    return
  }

  if (accountForm.password && accountForm.password.length < 6) {
    error.value = 'Новый пароль должен быть не короче 6 символов.'
    return
  }

  if (accountForm.password !== accountForm.passwordConfirmation) {
    error.value = 'Пароли не совпадают.'
    return
  }

  if (!hasAccountChanges.value) {
    successMessage.value = 'Изменений для сохранения нет.'
    return
  }

  const payload: Parameters<typeof updateUser>[1] = {}
  if (username !== currentUser.username) {
    payload.username = username
  }
  if (accountForm.password) {
    payload.password = accountForm.password
  }

  isSaving.value = true
  try {
    const updated = await updateUser(currentUser.user_id, payload)
    authStore.user = updated
    syncAccountForm()
    successMessage.value = 'Логин и пароль сохранены.'
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

watch(
  () => authStore.user?.username,
  syncAccountForm,
  { immediate: true },
)
</script>

<template>
  <section class="page-section settings-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Профиль</p>
        <h1>Настройки</h1>
      </div>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

    <div class="settings-grid">
      <div class="settings-card">
        <div class="form-heading">
          <div>
            <p class="eyebrow">Учетная запись</p>
            <h2>{{ authStore.user?.username || 'Пользователь' }}</h2>
          </div>
          <span :class="['status-badge', authStore.user?.is_active ? 'success' : 'danger']">
            {{ authStore.user?.is_active ? 'Активен' : 'Заблокирован' }}
          </span>
        </div>

        <form class="flat-form" @submit.prevent="saveAccount">
          <div class="details-grid settings-details-grid">
            <label>
              Логин
              <input v-model="accountForm.username" autocomplete="username" required />
            </label>
            <label>
              Роль
              <input :value="authStore.user?.role" readonly />
            </label>
          </div>

          <div class="form-grid">
            <label>
              Новый пароль
              <input
                v-model="accountForm.password"
                autocomplete="new-password"
                placeholder="Оставьте пустым, чтобы не менять"
                type="password"
              />
            </label>
            <label>
              Повторите новый пароль
              <input
                v-model="accountForm.passwordConfirmation"
                autocomplete="new-password"
                placeholder="Повторите пароль"
                type="password"
              />
            </label>
          </div>

          <p class="form-hint">Пароль должен содержать не менее 6 символов.</p>
          <button class="primary-button" type="submit" :disabled="isSaving || !hasAccountChanges">
            {{ isSaving ? 'Сохраняем...' : 'Сохранить логин и пароль' }}
          </button>
        </form>
      </div>

      <div class="settings-card">
        <p class="eyebrow">Доступ</p>
        <h2>Права пользователя</h2>
        <p class="muted">
          Роль и активность учетной записи меняет администратор в разделе «Пользователи».
          Логин и пароль доступны только владельцу этой учетной записи в настройках.
        </p>
      </div>
    </div>
  </section>
</template>
