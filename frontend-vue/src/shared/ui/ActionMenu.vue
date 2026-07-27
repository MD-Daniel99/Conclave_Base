<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, type Component } from 'vue'
import { Ellipsis } from '@lucide/vue'

export type ActionMenuItem = {
  label: string
  icon?: Component
  danger?: boolean
  disabled?: boolean
  action: () => void | Promise<void>
}

withDefaults(defineProps<{
  items: ActionMenuItem[]
  label?: string
}>(), {
  label: 'Открыть меню действий',
})

const isOpen = ref(false)
const trigger = ref<HTMLButtonElement | null>(null)
const menu = ref<HTMLElement | null>(null)
const menuStyle = ref<Record<string, string>>({})

function removeGlobalListeners() {
  window.removeEventListener('pointerdown', handleOutsidePointer, true)
  window.removeEventListener('resize', closeMenu)
}

function closeMenu() {
  isOpen.value = false
  removeGlobalListeners()
}

function handleOutsidePointer(event: PointerEvent) {
  const target = event.target as Node | null

  if (target && (trigger.value?.contains(target) || menu.value?.contains(target))) {
    return
  }

  closeMenu()
}

function positionMenu(itemCount: number) {
  if (!trigger.value) {
    return
  }

  const rect = trigger.value.getBoundingClientRect()
  const width = 210
  const estimatedHeight = Math.max(52, itemCount * 40 + 12)
  const margin = 8
  const left = Math.min(
    window.innerWidth - width - margin,
    Math.max(margin, rect.right - width),
  )
  const top = rect.bottom + estimatedHeight + margin <= window.innerHeight
    ? rect.bottom + 6
    : Math.max(margin, rect.top - estimatedHeight - 6)

  menuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
  }
}

async function toggleMenu(event: MouseEvent, itemCount: number) {
  event.preventDefault()
  event.stopPropagation()

  if (isOpen.value) {
    closeMenu()
    return
  }

  positionMenu(itemCount)
  isOpen.value = true

  await nextTick()
  window.addEventListener('pointerdown', handleOutsidePointer, true)
  window.addEventListener('resize', closeMenu)
  menu.value?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()
}

async function runAction(item: ActionMenuItem) {
  if (item.disabled) {
    return
  }

  closeMenu()
  await item.action()
}

function handleMenuKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeMenu()
    trigger.value?.focus()
    return
  }

  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
    return
  }

  event.preventDefault()
  const buttons = Array.from(
    menu.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [],
  )

  if (buttons.length === 0) {
    return
  }

  const currentIndex = buttons.indexOf(document.activeElement as HTMLButtonElement)
  const direction = event.key === 'ArrowDown' ? 1 : -1
  const nextIndex = (currentIndex + direction + buttons.length) % buttons.length
  buttons[nextIndex]?.focus()
}

onBeforeUnmount(removeGlobalListeners)
</script>

<template>
  <button
    ref="trigger"
    class="icon-button action-menu-trigger"
    type="button"
    :aria-label="label"
    :title="label"
    aria-haspopup="menu"
    :aria-expanded="isOpen"
    @click="toggleMenu($event, items.length)"
  >
    <Ellipsis :size="18" aria-hidden="true" />
  </button>

  <Teleport to="body">
    <div
      v-if="isOpen"
      ref="menu"
      class="app-action-menu custom-action-popover"
      role="menu"
      :aria-label="label"
      :style="menuStyle"
      @click.stop
      @keydown="handleMenuKeydown"
    >
      <button
        v-for="item in items"
        :key="item.label"
        class="custom-action-item"
        :class="{ 'is-danger': item.danger }"
        type="button"
        role="menuitem"
        :disabled="item.disabled"
        @click="runAction(item)"
      >
        <component
          :is="item.icon"
          v-if="item.icon"
          :size="17"
          aria-hidden="true"
        />
        <span>{{ item.label }}</span>
      </button>
    </div>
  </Teleport>
</template>
