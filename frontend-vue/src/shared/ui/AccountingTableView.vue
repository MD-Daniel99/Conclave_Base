<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  title: string
  count: number
  pageCount: number
}>()

const fullscreen = ref(false)
const openButton = ref<HTMLButtonElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const viewElement = ref<HTMLElement | null>(null)
let previousBodyOverflow = ''

async function openFullscreen() {
  if (fullscreen.value) return
  previousBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  fullscreen.value = true
  await nextTick()
  closeButton.value?.focus()
}

async function closeFullscreen() {
  if (!fullscreen.value) return
  fullscreen.value = false
  document.body.style.overflow = previousBodyOverflow
  await nextTick()
  openButton.value?.focus()
}

function onKeydown(event: KeyboardEvent) {
  if (!fullscreen.value) return
  // Editing an expense uses its own modal. Do not intercept its keyboard events.
  if (document.querySelector('.accounting-expense-modal')) return
  if (event.key === 'Escape') {
    event.preventDefault()
    void closeFullscreen()
    return
  }
  if (event.key !== 'Tab' || !viewElement.value) return
  const focusable = Array.from(viewElement.value.querySelectorAll<HTMLElement>(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
  )).filter((element) => element.getClientRects().length > 0)
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && (document.activeElement === first || !viewElement.value.contains(document.activeElement))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (document.activeElement === last || !viewElement.value.contains(document.activeElement))) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  if (fullscreen.value) document.body.style.overflow = previousBodyOverflow
})
</script>

<template>
  <!-- The table is never duplicated or remounted: edits and modal actions keep their state. -->
  <div
    ref="viewElement"
    class="accounting-table-view"
    :class="{ 'accounting-table-view-fullscreen': fullscreen }"
    :role="fullscreen ? 'dialog' : undefined"
    :aria-modal="fullscreen ? 'true' : undefined"
    :aria-label="fullscreen ? props.title : undefined"
  >
    <div class="accounting-table-view-bar">
      <div class="accounting-table-view-summary">
        <strong>{{ props.title }}</strong>
        <span class="muted">Записей: {{ props.count }} · на странице: {{ props.pageCount }}</span>
      </div>
      <button
        v-if="!fullscreen"
        ref="openButton"
        class="secondary-button accounting-fullscreen-toggle"
        type="button"
        title="Развернуть таблицу на весь экран"
        @click="openFullscreen"
      >
        <span aria-hidden="true">⛶</span> На весь экран
      </button>
      <button
        v-else
        ref="closeButton"
        class="secondary-button accounting-fullscreen-toggle"
        type="button"
        title="Вернуться к обычной бухгалтерии"
        @click="closeFullscreen"
      >
        <span aria-hidden="true">×</span> Закрыть
      </button>
    </div>
    <slot />
  </div>
</template>
