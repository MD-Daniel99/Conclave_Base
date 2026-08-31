<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/app/stores/auth'
import {
  createTsrReference,
  deleteTsrReference,
  fetchTsrReferences,
  updateTsrReference,
} from '@/shared/api/references'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm } from '@/shared/composables/useAppFeedback'
import type { ReferenceItem } from '@/shared/types/entities'

const authStore = useAuthStore()
const confirmAction = useAppConfirm()
const items = ref<ReferenceItem[]>([])
const query = ref('')
const draft = ref('')
const editingId = ref<string | number | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')

const canManage = computed(() => authStore.isAdmin)
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('ru-RU')
  return items.value.filter((item) => !needle || labelOf(item).toLocaleLowerCase('ru-RU').includes(needle))
})

function idOf(item: ReferenceItem) {
  return item.id ?? item.tsr_id ?? ''
}

function labelOf(item: ReferenceItem) {
  return String(item.full_tsr_code ?? '')
}

function resetEditor() {
  draft.value = ''
  editingId.value = null
}

function edit(item: ReferenceItem) {
  draft.value = labelOf(item)
  editingId.value = idOf(item)
  error.value = ''
  success.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = await fetchTsrReferences()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

async function save() {
  const value = draft.value.trim()
  if (!value || !canManage.value) return
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    if (editingId.value) {
      await updateTsrReference(editingId.value, { full_tsr_code: value })
      success.value = 'ТСР обновлён.'
    } else {
      await createTsrReference({ full_tsr_code: value })
      success.value = 'ТСР добавлен.'
    }
    resetEditor()
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

async function remove(item: ReferenceItem) {
  const id = idOf(item)
  if (!id || !canManage.value) return
  if (!(await confirmAction({ message: `Удалить ТСР «${labelOf(item)}»?`, danger: true }))) return
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    await deleteTsrReference(id)
    success.value = 'ТСР удалён.'
    if (editingId.value === id) resetEditor()
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page-section tsr-reference-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Справочники</p>
        <h1>Справочник ТСР</h1>
        <p class="muted">Отдельное рабочее место для просмотра и редактирования ТСР. Справочник в карточке пациента продолжает работать как раньше.</p>
      </div>
    </div>

    <div class="toolbar-form tsr-reference-toolbar">
      <label>
        Поиск по коду или названию
        <input v-model="query" placeholder="Например: 8-07-14" />
      </label>
      <span class="muted">Найдено: {{ filtered.length }} · всего: {{ items.length }}</span>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>

    <div class="tsr-reference-layout">
      <section class="detail-panel tsr-reference-list">
        <div class="form-heading"><div><p class="eyebrow">ТСР</p><h2>Записи справочника</h2></div></div>
        <p v-if="loading" class="muted">Загрузка…</p>
        <div v-else class="tsr-reference-rows">
          <article v-for="item in filtered" :key="String(idOf(item))" class="tsr-reference-row">
            <button class="link-button" type="button" @click="edit(item)">{{ labelOf(item) }}</button>
            <div v-if="canManage" class="row-actions">
              <button class="ghost-button" type="button" @click="edit(item)">Изменить</button>
              <button class="danger-button" type="button" :disabled="saving" @click="remove(item)">Удалить</button>
            </div>
          </article>
          <p v-if="!filtered.length" class="form-hint">По вашему запросу записей нет.</p>
        </div>
      </section>

      <aside class="detail-panel tsr-reference-editor">
        <div class="form-heading">
          <div><p class="eyebrow">{{ editingId ? 'Редактирование' : 'Новая запись' }}</p><h2>{{ editingId ? 'Изменить ТСР' : 'Добавить ТСР' }}</h2></div>
        </div>
        <template v-if="canManage">
          <form class="side-form flat-form" @submit.prevent="save">
            <label>
              Полный код и наименование ТСР
              <textarea v-model="draft" rows="5" placeholder="Код и полное наименование" required />
            </label>
            <div class="row-actions">
              <button class="primary-button" type="submit" :disabled="saving || !draft.trim()">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</button>
              <button v-if="editingId" class="ghost-button" type="button" @click="resetEditor">Отмена</button>
            </div>
          </form>
        </template>
        <p v-else class="form-hint">Просмотр доступен всем пользователям. Изменять справочник может администратор.</p>
      </aside>
    </div>
  </section>
</template>
