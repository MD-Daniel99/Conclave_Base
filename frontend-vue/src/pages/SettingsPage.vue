<script setup lang="ts">
import { useAuthStore } from '@/app/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <section class="page-section">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Профиль</p>
        <h1>Настройки</h1>
      </div>
    </div>

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

        <div class="details-grid settings-details-grid">
          <label>
            Логин
            <input :value="authStore.user?.username" readonly />
          </label>
          <label>
            Роль
            <input :value="authStore.user?.role" readonly />
          </label>
          <label>
            ID пользователя
            <input :value="authStore.user?.user_id" readonly />
          </label>
        </div>
      </div>

      <div class="settings-card">
        <p class="eyebrow">Доступ</p>
        <h2>Права пользователя</h2>
        <p class="muted">
          Изменение логина, роли, пароля и активности выполняется администратором в разделе пользователей.
        </p>
      </div>
    </div>
  </section>
</template>
