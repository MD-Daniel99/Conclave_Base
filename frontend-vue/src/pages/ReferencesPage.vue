<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/app/stores/auth'
import { getApiErrorMessage } from '@/shared/api/http'

const auth = useAuthStore()
const canEdit = computed(() => auth.isAdmin)

function authToken() {
  const source = auth as unknown as Record<string, unknown>
  const direct = source.token ?? source.accessToken ?? source.access_token
  if (typeof direct === 'string' && direct) return direct
  for (const key of ['token', 'access_token', 'auth_token']) {
    const stored = window.localStorage.getItem(key)
    if (stored) return stored
  }
  return ''
}

type Kind = 'prosthesis' | 'tsr' | 'name_index'
type RefItem = Record<string, unknown>

type Section = {
  kind: Kind
  title: string
  hint: string
  endpoint: string
  valueKey: string
  idKeys: string[]
  createKey: string
}

const sections: Section[] = [
  {
    kind: 'prosthesis',
    title: 'Виды протезов',
    hint: 'Справочник видов протезов, который также остаётся доступен из карточки клиента.',
    endpoint: '/references/prosthesis',
    valueKey: 'name',
    idKeys: ['id', 'prosthesis_id'],
    createKey: 'name',
  },
  {
    kind: 'tsr',
    title: 'Коды ТСР',
    hint: 'Единый список ТСР для карточек клиентов, комплектующих и документов.',
    endpoint: '/references/tsr',
    valueKey: 'full_tsr_code',
    idKeys: ['id', 'tsr_id'],
    createKey: 'full_tsr_code',
  },
  {
    kind: 'name_index',
    title: 'Названия и индексы комплектующих',
    hint: 'Каталог названий/индексов для склада и комплектующих клиента.',
    endpoint: '/references/name_index',
    valueKey: 'name_index',
    idKeys: ['id', 'name_index_id'],
    createKey: 'name_index',
  },
]

const items = reactive<Record<Kind, RefItem[]>>({ prosthesis: [], tsr: [], name_index: [] })
const drafts = reactive<Record<Kind, string>>({ prosthesis: '', tsr: '', name_index: '' })
const searches = reactive<Record<Kind, string>>({ prosthesis: '', tsr: '', name_index: '' })
const editing = reactive<Record<Kind, string>>({ prosthesis: '', tsr: '', name_index: '' })
const editValues = reactive<Record<Kind, string>>({ prosthesis: '', tsr: '', name_index: '' })
const loading = ref(false)
const error = ref('')
const success = ref('')

function headers(json = false): Record<string, string> {
  const token = authToken()
  return {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function api(url: string, init: RequestInit = {}) {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = String(body?.detail ?? detail)
    } catch {
      // Keep HTTP status.
    }
    throw new Error(detail)
  }
  if (response.status === 204) return null
  return await response.json()
}

function idOf(section: Section, item: RefItem) {
  for (const key of section.idKeys) {
    if (item[key]) return String(item[key])
  }
  return ''
}

function valueOf(section: Section, item: RefItem) {
  return String(item[section.valueKey] ?? '')
}

function filtered(section: Section) {
  const needle = searches[section.kind].trim().toLocaleLowerCase('ru-RU')
  return needle
    ? items[section.kind].filter((item) => valueOf(section, item).toLocaleLowerCase('ru-RU').includes(needle))
    : items[section.kind]
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await Promise.all(sections.map((section) => api(section.endpoint, { headers: headers() })))
    sections.forEach((section, index) => { items[section.kind] = Array.isArray(result[index]) ? result[index] : [] })
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

async function create(section: Section) {
  const value = drafts[section.kind].trim()
  if (!value) return
  error.value = ''
  try {
    await api(section.endpoint, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ [section.createKey]: value }),
    })
    drafts[section.kind] = ''
    success.value = 'Запись справочника добавлена.'
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

function startEdit(section: Section, item: RefItem) {
  editing[section.kind] = idOf(section, item)
  editValues[section.kind] = valueOf(section, item)
}

async function saveEdit(section: Section) {
  const id = editing[section.kind]
  const value = editValues[section.kind].trim()
  if (!id || !value) return
  error.value = ''
  try {
    await api(`${section.endpoint}/${id}`, {
      method: 'PUT',
      headers: headers(true),
      body: JSON.stringify({ [section.createKey]: value }),
    })
    editing[section.kind] = ''
    editValues[section.kind] = ''
    success.value = 'Запись справочника обновлена.'
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function remove(section: Section, item: RefItem) {
  const id = idOf(section, item)
  if (!id || !window.confirm(`Удалить «${valueOf(section, item)}»?`)) return
  error.value = ''
  try {
    await api(`${section.endpoint}/${id}`, { method: 'DELETE', headers: headers() })
    success.value = 'Запись справочника удалена.'
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

onMounted(load)
</script>

<template>
  <section class="page-section references-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">Справочники</p>
        <h1>ТСР и комплектующие</h1>
        <p class="page-subtitle">Отдельное рабочее место для справочников. Управление в карточках клиентов сохранено.</p>
      </div>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>
    <p v-if="loading" class="muted">Загружаем справочники…</p>

    <div class="reference-page-grid">
      <article v-for="section in sections" :key="section.kind" class="reference-page-card">
        <div class="reference-page-card-head">
          <div>
            <h2>{{ section.title }}</h2>
            <p class="muted">{{ section.hint }}</p>
          </div>
          <span class="reference-count">{{ items[section.kind].length }}</span>
        </div>

        <input v-model="searches[section.kind]" class="reference-search" placeholder="Поиск по справочнику" />

        <form v-if="canEdit" class="reference-add-row" @submit.prevent="create(section)">
          <input v-model="drafts[section.kind]" placeholder="Новая запись" />
          <button class="primary-button" type="submit" :disabled="!drafts[section.kind].trim()">Добавить</button>
        </form>

        <div class="reference-page-list">
          <div v-for="item in filtered(section)" :key="idOf(section, item)" class="reference-page-row">
            <template v-if="editing[section.kind] === idOf(section, item)">
              <input v-model="editValues[section.kind]" />
              <div class="row-actions">
                <button class="primary-button" type="button" @click="saveEdit(section)">Сохранить</button>
                <button class="ghost-button" type="button" @click="editing[section.kind] = ''">Отмена</button>
              </div>
            </template>
            <template v-else>
              <strong>{{ valueOf(section, item) }}</strong>
              <div v-if="canEdit" class="row-actions">
                <button class="ghost-button" type="button" @click="startEdit(section, item)">Изменить</button>
                <button class="danger-button" type="button" @click="remove(section, item)">Удалить</button>
              </div>
            </template>
          </div>
          <p v-if="filtered(section).length === 0" class="muted">Ничего не найдено.</p>
        </div>
      </article>
    </div>
  </section>
</template>
