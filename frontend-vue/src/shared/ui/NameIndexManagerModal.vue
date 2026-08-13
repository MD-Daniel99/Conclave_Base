<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getApiErrorMessage } from '@/shared/api/http'
import {
  createNameIndexReference,
  deleteNameIndexReference,
  updateNameIndexReference,
} from '@/shared/api/references'
import { useAppConfirm } from '@/shared/composables/useAppFeedback'
import type { ReferenceItem } from '@/shared/types/entities'

const props = defineProps<{ open: boolean; items: ReferenceItem[]; canManage: boolean }>()
const emit = defineEmits<{ close: []; refresh: [] }>()
const query = ref('')
const draft = ref('')
const editingId = ref<string | number | null>(null)
const saving = ref(false)
const error = ref('')
const success = ref('')
const confirmAction = useAppConfirm()

const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('ru-RU')
  if (!needle) return props.items
  return props.items.filter((item) => labelOf(item).toLocaleLowerCase('ru-RU').includes(needle))
})

function idOf(item: ReferenceItem) { return item.id ?? item.name_index_id ?? '' }
function labelOf(item: ReferenceItem) { return String(item.name_index ?? item.name ?? '') }
function resetForm() { draft.value = ''; editingId.value = null; error.value = ''; success.value = '' }
function edit(item: ReferenceItem) { editingId.value = idOf(item); draft.value = labelOf(item); error.value = ''; success.value = '' }

async function save() {
  const value = draft.value.trim()
  if (!value || !props.canManage) return
  saving.value = true; error.value = ''; success.value = ''
  try {
    if (editingId.value) {
      await updateNameIndexReference(editingId.value, { name_index: value })
      success.value = 'Запись справочника обновлена.'
    } else {
      await createNameIndexReference({ name_index: value })
      success.value = 'Запись добавлена в справочник.'
    }
    draft.value = ''; editingId.value = null; emit('refresh')
  } catch (e) { error.value = getApiErrorMessage(e) }
  finally { saving.value = false }
}

async function remove(item: ReferenceItem) {
  const id = idOf(item); if (!id || !props.canManage) return
  if (!(await confirmAction({ message: `Удалить «${labelOf(item)}» из справочника комплектующих?`, danger: true }))) return
  saving.value = true; error.value = ''; success.value = ''
  try { await deleteNameIndexReference(id); success.value = 'Запись удалена.'; emit('refresh') }
  catch (e) { error.value = getApiErrorMessage(e) }
  finally { saving.value = false }
}

watch(() => props.open, (value) => { if (value) { query.value = ''; resetForm() } })
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop reference-manager-backdrop" @click.self="emit('close')" @keydown.esc.window="emit('close')">
      <section class="modal-panel reference-manager-modal" role="dialog" aria-modal="true" aria-label="Справочник комплектующих" @click.stop>
        <div class="modal-header">
          <div><p class="eyebrow">Справочник</p><h2>Комплектующие</h2></div>
          <button class="ghost-button" type="button" :disabled="saving" @click="emit('close')">Закрыть</button>
        </div>
        <p v-if="error" class="form-error">{{ error }}</p><p v-if="success" class="form-success">{{ success }}</p>
        <form v-if="canManage" class="reference-editor" @submit.prevent="save">
          <label>Название и индекс<input v-model="draft" placeholder="Например: 1C30 — СТОПА TRIAS" required /></label>
          <div class="row-actions reference-editor-actions">
            <button class="primary-button" type="submit" :disabled="saving || !draft.trim()">{{ saving ? 'Сохраняем...' : editingId ? 'Сохранить' : 'Добавить' }}</button>
            <button v-if="editingId" class="ghost-button" type="button" :disabled="saving" @click="resetForm">Отмена</button>
          </div>
        </form>
        <div class="reference-search-row"><input v-model="query" placeholder="Поиск по названию или индексу" /><span class="muted">{{ filtered.length }} из {{ items.length }}</span></div>
        <div class="reference-list" role="list">
          <article v-for="item in filtered" :key="String(idOf(item) || labelOf(item))" class="reference-list-item" role="listitem">
            <div><strong>{{ labelOf(item) }}</strong></div>
            <div v-if="canManage" class="row-actions"><button class="ghost-button" type="button" :disabled="saving" @click="edit(item)">Изм.</button><button class="danger-button" type="button" :disabled="saving" @click="remove(item)">Удалить</button></div>
          </article>
          <p v-if="!filtered.length" class="empty-state">Записей не найдено.</p>
        </div>
        <p class="form-hint">Новые названия автоматически попадают сюда при создании комплектующей. Удаление используемой записи сервер не разрешит.</p>
      </section>
    </div>
  </Teleport>
</template>
