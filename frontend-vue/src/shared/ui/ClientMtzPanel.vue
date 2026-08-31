<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/app/stores/auth'
import { getApiErrorMessage } from '@/shared/api/http'

const props = defineProps<{
  clientId: string
}>()

const emit = defineEmits<{
  generated: []
}>()

const auth = useAuthStore()
const templates = ref<Array<{ key: string; label: string; tsr_code: string }>>([])
const templateKey = ref('mtz_8_1_07_14')
const amputationLevel = ref('')
const patientWeightKg = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

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

function authHeaders(json = false): Record<string, string> {
  const token = authToken()
  return {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function apiJson<T>(url: string, init: RequestInit = {}): Promise<T> {
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
  return await response.json() as T
}

async function loadTemplates() {
  try {
    templates.value = await apiJson('/documents/mtz/templates', { headers: authHeaders() })
    if (templates.value.length && !templates.value.some((item) => item.key === templateKey.value)) {
      templateKey.value = templates.value[0].key
    }
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function generate() {
  error.value = ''
  success.value = ''
  const weight = Number(patientWeightKg.value.replace(',', '.'))
  if (!amputationLevel.value.trim()) {
    error.value = 'Укажите уровень ампутации.'
    return
  }
  if (!Number.isFinite(weight) || weight <= 0) {
    error.value = 'Укажите корректный вес пациента.'
    return
  }

  loading.value = true
  try {
    await apiJson(`/documents/clients/${props.clientId}/generate_mtz`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        template_key: templateKey.value,
        amputation_level: amputationLevel.value.trim(),
        patient_weight_kg: weight,
      }),
    })
    success.value = 'МТЗ сформировано и добавлено в документы клиента.'
    emit('generated')
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

onMounted(loadTemplates)
</script>

<template>
  <section class="document-subsection mtz-panel">
    <div class="document-subsection-heading">
      <div>
        <p class="eyebrow">МТЗ</p>
        <h3>Автозаполнение медико-технического заключения</h3>
      </div>
    </div>
    <p class="form-hint">
      ФИО, дата рождения, группа/причина инвалидности, справка, диагноз и телефон берутся из карточки клиента.
      Вручную заполняются только уровень ампутации и вес пациента.
    </p>

    <div class="form-grid">
      <label>
        Шаблон / ТСР
        <select v-model="templateKey">
          <option v-for="item in templates" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select>
      </label>
      <label>
        Уровень ампутации
        <input v-model="amputationLevel" placeholder="Например: верхняя треть голени" />
      </label>
      <label>
        Вес пациента (кг)
        <input v-model="patientWeightKg" inputmode="decimal" placeholder="Например: 78" />
      </label>
    </div>

    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="success" class="form-success">{{ success }}</p>
    <button class="primary-button" type="button" :disabled="loading || !clientId" @click="generate">
      {{ loading ? 'Формируем МТЗ…' : 'Сформировать МТЗ' }}
    </button>
  </section>
</template>
