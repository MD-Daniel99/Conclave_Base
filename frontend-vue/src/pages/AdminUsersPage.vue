<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { useAuthStore } from '@/app/stores/auth'
import { createUser, deleteUser, fetchUsers, updateUser } from '@/shared/api/auth'
import { fetchEntityAudit } from '@/shared/api/audit'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm, useSuccessToast } from '@/shared/composables/useAppFeedback'
import {
  formatAuditAction,
  formatAuditActor,
  formatAuditTime,
  summarizeAuditDetails,
} from '@/shared/lib/audit'
import type { AuditLogItem } from '@/shared/types/entities'
import type { User } from '@/shared/types/auth'

type UserForm = {
  role: 'user' | 'admin'
  is_active: boolean
}

const authStore = useAuthStore()
const users = ref<User[]>([])
const userSearch = ref('')
const selectedUser = ref<User | null>(null)
const userAuditItems = ref<AuditLogItem[]>([])
const isLoading = ref(false)
const isSaving = ref(false)
const isAuditLoading = ref(false)
const auditError = ref('')
const error = ref('')
const successMessage = ref('')
const confirmAction = useAppConfirm()
useSuccessToast(successMessage, 'Пользователи')

const newUser = reactive({
  username: '',
  password: '',
  role: 'user' as 'user' | 'admin',
})

const editForm = reactive<UserForm>({
  role: 'user',
  is_active: true,
})

const isSelfSelected = computed(() => {
  return Boolean(selectedUser.value && authStore.user?.user_id === selectedUser.value.user_id)
})

const visibleUsers = computed(() => {
  const needle = userSearch.value.trim().toLowerCase()

  if (!needle) {
    return users.value
  }

  return users.value.filter((user) => {
    return (
      user.username.toLowerCase().includes(needle) ||
      user.role.toLowerCase().includes(needle)
    )
  })
})

function formatDateTime(value?: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('ru-RU')
}

function resetMessages() {
  error.value = ''
  successMessage.value = ''
}

function fillEditForm(user: User) {
  editForm.role = user.role === 'admin' ? 'admin' : 'user'
  editForm.is_active = Boolean(user.is_active)
}

async function selectUser(user: User) {
  selectedUser.value = user
  fillEditForm(user)
  userAuditItems.value = []
  auditError.value = ''
  resetMessages()
  await loadUserAudit()
}

function resetSelection() {
  selectedUser.value = null
  userAuditItems.value = []
  auditError.value = ''
  editForm.role = 'user'
  editForm.is_active = true
  resetMessages()
}

async function loadUserAudit() {
  if (!selectedUser.value?.user_id) {
    return
  }

  isAuditLoading.value = true
  auditError.value = ''

  try {
    userAuditItems.value = await fetchEntityAudit('user', selectedUser.value.user_id)
  } catch (caughtError) {
    auditError.value = getApiErrorMessage(caughtError)
  } finally {
    isAuditLoading.value = false
  }
}

async function loadUsers() {
  isLoading.value = true
  error.value = ''

  try {
    users.value = await fetchUsers()

    if (selectedUser.value) {
      const freshSelected = users.value.find((user) => user.user_id === selectedUser.value?.user_id)
      if (freshSelected) {
        selectedUser.value = freshSelected
        fillEditForm(freshSelected)
      } else {
        resetSelection()
      }
    }
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isLoading.value = false
  }
}

function validateNewUser() {
  if (!newUser.username.trim()) {
    error.value = 'Введите логин нового пользователя'
    return false
  }

  if (!newUser.password) {
    error.value = 'Введите пароль нового пользователя'
    return false
  }

  if (newUser.password.length < 6) {
    error.value = 'Пароль должен быть не короче 6 символов'
    return false
  }

  return true
}

function validateEditUser() {
  if (!selectedUser.value) {
    error.value = 'Выберите пользователя для редактирования'
    return false
  }

  if (isSelfSelected.value) {
    if (editForm.role !== selectedUser.value.role) {
      error.value = 'Нельзя изменить собственную роль'
      return false
    }

    if (!editForm.is_active) {
      error.value = 'Нельзя заблокировать собственный аккаунт'
      return false
    }
  }

  return true
}

async function submitUser() {
  resetMessages()

  if (!validateNewUser()) {
    return
  }

  isSaving.value = true

  try {
    const created = await createUser({
      username: newUser.username.trim(),
      password: newUser.password,
      role: newUser.role,
    })

    successMessage.value = 'Пользователь создан'
    newUser.username = ''
    newUser.password = ''
    newUser.role = 'user'
    await loadUsers()
    await selectUser(created)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function saveSelectedUser() {
  resetMessages()

  if (!validateEditUser() || !selectedUser.value) {
    return
  }

  isSaving.value = true

  try {
    const payload: Parameters<typeof updateUser>[1] = {}

    if (!isSelfSelected.value) {
      payload.role = editForm.role
      payload.is_active = editForm.is_active
    }

    const updated = await updateUser(selectedUser.value.user_id, payload)
    successMessage.value = 'Пользователь обновлен'

    await loadUsers()
    await selectUser(updated)
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function toggleUser(user: User) {
  if (authStore.user?.user_id === user.user_id) {
    error.value = 'Нельзя заблокировать собственный аккаунт'
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await updateUser(user.user_id, { is_active: !user.is_active })
    successMessage.value = user.is_active ? 'Пользователь заблокирован' : 'Пользователь активирован'
    await loadUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

async function removeUser(user: User) {
  if (authStore.user?.user_id === user.user_id) {
    error.value = 'Нельзя удалить собственный аккаунт'
    return
  }

  if (!(await confirmAction({
    message: `Удалить пользователя «${user.username}»? Это действие нельзя отменить.`,
    danger: true,
  }))) {
    return
  }

  isSaving.value = true
  resetMessages()

  try {
    await deleteUser(user.user_id)
    successMessage.value = 'Пользователь удален'

    if (selectedUser.value?.user_id === user.user_id) {
      resetSelection()
    }

    await loadUsers()
  } catch (caughtError) {
    error.value = getApiErrorMessage(caughtError)
  } finally {
    isSaving.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <section class="page-section users-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Администрирование</p>
        <h1>Управление пользователями</h1>
      </div>
      <div class="row-actions page-heading-actions">
        <input v-model="userSearch" class="toolbar-search-input" placeholder="Поиск пользователя" />
        <button class="secondary-button" type="button" :disabled="isLoading" @click="loadUsers">
          {{ isLoading ? 'Обновляем...' : 'Обновить' }}
        </button>
      </div>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="successMessage" class="form-success">{{ successMessage }}</p>

    <form class="toolbar-form admin-create-toolbar" @submit.prevent="submitUser">
      <input v-model="newUser.username" autocomplete="username" placeholder="Логин *" required />
      <input v-model="newUser.password" autocomplete="new-password" placeholder="Пароль *" required type="password" />
      <select v-model="newUser.role">
        <option value="user">user</option>
        <option value="admin">admin</option>
      </select>
      <button class="primary-button" :disabled="isSaving" type="submit">
        {{ isSaving ? 'Сохраняем...' : 'Создать пользователя' }}
      </button>
    </form>

    <div class="split-view">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Логин</th>
              <th>Роль</th>
              <th>Активен</th>
              <th>Создан</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="isLoading">
              <td colspan="5">Загружаем пользователей...</td>
            </tr>

            <tr
              v-for="user in visibleUsers"
              v-else
              :key="user.user_id"
              :class="{ selected: selectedUser?.user_id === user.user_id }"
            >
              <td>
                <button class="link-button" type="button" @click="selectUser(user)">
                  {{ user.username }}
                </button>
                <span v-if="authStore.user?.user_id === user.user_id" class="badge">вы</span>
              </td>
              <td><span :class="['status-badge', user.role === 'admin' ? 'info' : 'neutral']">{{ user.role }}</span></td>
              <td>
                <span :class="['status-badge', user.is_active ? 'success' : 'danger']">
                  {{ user.is_active ? 'Активен' : 'Заблокирован' }}
                </span>
              </td>
              <td>{{ formatDateTime(user.created_at) }}</td>
              <td class="row-actions">
                <button class="ghost-button" type="button" @click="selectUser(user)">
                  Изм.
                </button>
                <button
                  class="ghost-button"
                  :disabled="isSaving || authStore.user?.user_id === user.user_id"
                  type="button"
                  @click="toggleUser(user)"
                >
                  {{ user.is_active ? 'Блок.' : 'Актив.' }}
                </button>
                <button
                  class="danger-button"
                  :disabled="isSaving || authStore.user?.user_id === user.user_id"
                  type="button"
                  @click="removeUser(user)"
                >
                  Удалить
                </button>
              </td>
            </tr>

            <tr v-if="!isLoading && visibleUsers.length === 0">
              <td colspan="5">Пользователи не найдены.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <aside class="side-form">
        <div class="form-heading">
          <div>
            <p class="eyebrow">Карточка пользователя</p>
            <h2>{{ selectedUser ? selectedUser.username : 'Выберите пользователя' }}</h2>
          </div>
          <button class="ghost-button" type="button" @click="resetSelection">
            Сброс
          </button>
        </div>

        <p v-if="!selectedUser" class="form-hint">
          Выберите пользователя в таблице, чтобы изменить роль или активность.
          Логин и пароль каждый пользователь меняет в собственных настройках.
        </p>

        <form v-else class="flat-form" @submit.prevent="saveSelectedUser">
          <div class="form-grid">
            <label>
              Роль
              <select v-model="editForm.role" :disabled="isSelfSelected">
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </label>

            <label class="checkbox-label user-active-checkbox">
              <input v-model="editForm.is_active" :disabled="isSelfSelected" type="checkbox" />
              Активен
            </label>
          </div>

          <p v-if="isSelfSelected" class="form-hint">
            Собственную роль, блокировку и удаление менять нельзя. Логин и пароль доступны в разделе «Настройки».
          </p>

          <button class="primary-button" type="submit" :disabled="isSaving || isSelfSelected">
            {{ isSaving ? 'Сохраняем...' : 'Сохранить изменения' }}
          </button>

          <button
            class="danger-button"
            type="button"
            :disabled="isSaving || isSelfSelected"
            @click="removeUser(selectedUser)"
          >
            Удалить пользователя
          </button>
        </form>

        <div v-if="selectedUser" class="detail-panel audit-panel">
          <div class="form-heading">
            <div>
              <p class="eyebrow">Контроль версий</p>
              <h2>История изменений</h2>
            </div>
            <button class="ghost-button" type="button" :disabled="isAuditLoading" @click="loadUserAudit">
              Обновить
            </button>
          </div>

          <p v-if="auditError" class="form-error">{{ auditError }}</p>
          <p v-if="isAuditLoading" class="muted">Загружаем историю...</p>

          <div v-else-if="userAuditItems.length" class="audit-timeline">
            <article v-for="item in userAuditItems" :key="item.log_id" class="audit-item">
              <div>
                <strong>{{ formatAuditAction(item) }}</strong>
                <span>{{ formatAuditActor(item) }} · {{ formatAuditTime(item.timestamp) }}</span>
              </div>
              <p>{{ summarizeAuditDetails(item) }}</p>
            </article>
          </div>

          <p v-else class="form-hint">История по пользователю пока пустая.</p>
        </div>
      </aside>
    </div>
  </section>
</template>
