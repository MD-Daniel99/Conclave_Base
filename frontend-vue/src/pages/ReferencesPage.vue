<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/app/stores/auth'
import {
  createNameIndexReference,
  createTsrReference,
  deleteNameIndexReference,
  deleteTsrReference,
  fetchNameIndexReferences,
  fetchTsrReferences,
  updateNameIndexReference,
  updateTsrReference,
} from '@/shared/api/references'
import { getApiErrorMessage } from '@/shared/api/http'
import { useAppConfirm } from '@/shared/composables/useAppFeedback'
import type { ReferenceItem } from '@/shared/types/entities'

type ReferenceTab = 'tsr' | 'components'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const confirmAction = useAppConfirm()

const activeTab = ref<ReferenceTab>('tsr')
const tsrItems = ref<ReferenceItem[]>([])
const componentItems = ref<ReferenceItem[]>([])
const query = ref('')
const draft = ref('')
const editingId = ref<string | number | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')

const canManage = computed(() => authStore.isAdmin)

const items = computed(() => activeTab.value === 'tsr' ? tsrItems.value : componentItems.value)
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase('ru-RU')
  return items.value.filter((item) => !needle || labelOf(item).toLocaleLowerCase('ru-RU').includes(needle))
})

const pageCopy = computed(() => activeTab.value === 'tsr'
  ? {
      eyebrow: 'ТСР',
      title: 'Справочник ТСР',
      description: 'Единый справочник ТСР для карточек пациентов, комплектующих и документов.',
      searchLabel: 'Поиск по коду или названию',
      searchPlaceholder: 'Например: 8-07-14',
      listTitle: 'Записи справочника ТСР',
      editorCreate: 'Добавить ТСР',
      editorEdit: 'Изменить ТСР',
      fieldLabel: 'Полный код и наименование ТСР',
      fieldPlaceholder: 'Код и полное наименование',
      empty: 'По вашему запросу ТСР не найдены.',
      readOnlyHint: 'Просмотр доступен всем пользователям. Изменять справочник ТСР может администратор.',
      footerHint: 'Этот же справочник продолжает работать в карточках пациентов без изменений.',
    }
  : {
      eyebrow: 'Комплектующие',
      title: 'Справочник комплектующих',
      description: 'Каталог названий и индексов комплектующих. Это тот же справочник, который используется в разделе «Комплектующие» карточки пациента.',
      searchLabel: 'Поиск по названию или индексу',
      searchPlaceholder: 'Например: 1C30 или TRIAS',
      listTitle: 'Названия и индексы комплектующих',
      editorCreate: 'Добавить комплектующую',
      editorEdit: 'Изменить запись',
      fieldLabel: 'Название и индекс',
      fieldPlaceholder: 'Например: 1C30 — СТОПА TRIAS',
      empty: 'По вашему запросу комплектующие не найдены.',
      readOnlyHint: 'Просмотр доступен всем пользователям. Изменять справочник комплектующих может администратор.',
      footerHint: 'Новые названия, созданные в карточке пациента, также попадают в этот справочник. Удаление используемой записи сервер не разрешит.',
    },
)

function tabFromRoute(): ReferenceTab {
  return route.name === 'references-components' ? 'components' : 'tsr'
}

function idOf(item: ReferenceItem) {
  return activeTab.value === 'tsr'
    ? item.id ?? item.tsr_id ?? ''
    : item.id ?? item.name_index_id ?? ''
}

function labelOf(item: ReferenceItem) {
  return activeTab.value === 'tsr'
    ? String(item.full_tsr_code ?? '')
    : String(item.name_index ?? item.name ?? '')
}

function resetEditor() {
  draft.value = ''
  editingId.value = null
  error.value = ''
}

function edit(item: ReferenceItem) {
  draft.value = labelOf(item)
  editingId.value = idOf(item)
  error.value = ''
  success.value = ''
}

function goTab(tab: ReferenceTab) {
  void router.push({ name: tab === 'components' ? 'references-components' : 'references-tsr' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [tsr, components] = await Promise.all([
      fetchTsrReferences(),
      fetchNameIndexReferences(),
    ])
    tsrItems.value = tsr
    componentItems.value = components
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
    if (activeTab.value === 'tsr') {
      if (editingId.value) {
        await updateTsrReference(editingId.value, { full_tsr_code: value })
        success.value = 'ТСР обновлён.'
      } else {
        await createTsrReference({ full_tsr_code: value })
        success.value = 'ТСР добавлен.'
      }
    } else if (editingId.value) {
      await updateNameIndexReference(editingId.value, { name_index: value })
      success.value = 'Запись справочника комплектующих обновлена.'
    } else {
      await createNameIndexReference({ name_index: value })
      success.value = 'Запись добавлена в справочник комплектующих.'
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
  const label = labelOf(item)
  if (!id || !canManage.value) return

  const message = activeTab.value === 'tsr'
    ? `Удалить ТСР «${label}»?`
    : `Удалить «${label}» из справочника комплектующих?`
  if (!(await confirmAction({ message, danger: true }))) return

  saving.value = true
  error.value = ''
  success.value = ''
  try {
    if (activeTab.value === 'tsr') {
      await deleteTsrReference(id)
      success.value = 'ТСР удалён.'
    } else {
      await deleteNameIndexReference(id)
      success.value = 'Запись справочника комплектующих удалена.'
    }
    if (editingId.value === id) resetEditor()
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

watch(
  () => route.name,
  () => {
    activeTab.value = tabFromRoute()
    query.value = ''
    resetEditor()
    success.value = ''
  },
)

onMounted(async () => {
  activeTab.value = tabFromRoute()
  await load()
})
</script>

<template>
  <section class="page-section tsr-reference-page references-workspace-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Справочники</p>
        <h1>Справочники</h1>
        <p class="muted">Единое рабочее место для справочников ТСР и комплектующих. Справочники внутри карточек пациентов сохранены и работают как раньше.</p>
      </div>
    </div>

    <div class="tabs" role="tablist" aria-label="Справочники">
      <button :class="{ active: activeTab === 'tsr' }" type="button" role="tab" :aria-selected="activeTab === 'tsr'" @click="goTab('tsr')">ТСР</button>
      <button :class="{ active: activeTab === 'components' }" type="button" role="tab" :aria-selected="activeTab === 'components'" @click="goTab('components')">Комплектующие</button>
    </div>

    <div class="toolbar-form tsr-reference-toolbar">
      <label>
        {{ pageCopy.searchLabel }}
        <input v-model="query" :placeholder="pageCopy.searchPlaceholder" />
      </label>
      <span class="muted">Найдено: {{ filtered.length }} · всего: {{ items.length }}</span>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>

    <div class="tsr-reference-layout">
      <section class="detail-panel tsr-reference-list">
        <div class="form-heading">
          <div>
            <p class="eyebrow">{{ pageCopy.eyebrow }}</p>
            <h2>{{ pageCopy.listTitle }}</h2>
            <p class="muted">{{ pageCopy.description }}</p>
          </div>
        </div>

        <p v-if="loading" class="muted">Загрузка…</p>
        <div v-else class="tsr-reference-rows">
          <article v-for="item in filtered" :key="String(idOf(item))" class="tsr-reference-row">
            <button class="link-button" type="button" @click="edit(item)">{{ labelOf(item) }}</button>
            <div v-if="canManage" class="row-actions">
              <button class="ghost-button" type="button" :disabled="saving" @click="edit(item)">Изменить</button>
              <button class="danger-button" type="button" :disabled="saving" @click="remove(item)">Удалить</button>
            </div>
          </article>
          <p v-if="!filtered.length" class="form-hint">{{ pageCopy.empty }}</p>
        </div>
      </section>

      <aside class="detail-panel tsr-reference-editor">
        <div class="form-heading">
          <div>
            <p class="eyebrow">{{ editingId ? 'Редактирование' : 'Новая запись' }}</p>
            <h2>{{ editingId ? pageCopy.editorEdit : pageCopy.editorCreate }}</h2>
          </div>
        </div>

        <template v-if="canManage">
          <form class="side-form flat-form" @submit.prevent="save">
            <label>
              {{ pageCopy.fieldLabel }}
              <textarea v-if="activeTab === 'tsr'" v-model="draft" rows="5" :placeholder="pageCopy.fieldPlaceholder" required />
              <input v-else v-model="draft" :placeholder="pageCopy.fieldPlaceholder" required />
            </label>
            <div class="row-actions">
              <button class="primary-button" type="submit" :disabled="saving || !draft.trim()">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</button>
              <button v-if="editingId" class="ghost-button" type="button" :disabled="saving" @click="resetEditor">Отмена</button>
            </div>
          </form>
        </template>
        <p v-else class="form-hint">{{ pageCopy.readOnlyHint }}</p>
        <p class="form-hint">{{ pageCopy.footerHint }}</p>
      </aside>
    </div>
  </section>
</template>
