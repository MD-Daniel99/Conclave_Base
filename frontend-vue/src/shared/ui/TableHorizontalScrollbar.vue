<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

// One always-visible drag handle for the horizontal scroll of the table
// currently in view. Native scrolling inside tables remains unchanged.
const dock = ref<HTMLDivElement | null>(null)
const visible = ref(false)
const dockLeft = ref(0)
const dockWidth = ref(0)
const thumbWidth = ref(50)
const thumbOffset = ref(0)
const scrollNow = ref(0)
const scrollMax = ref(0)

let tableScrollers: HTMLElement[] = []
let activeScroller: HTMLElement | null = null
let preferredScroller: HTMLElement | null = null
let mutationObserver: MutationObserver | null = null
let resizeObserver: ResizeObserver | null = null
let frame = 0
let needsDiscovery = true
let dragging = false
let grabOffset = 0

function discoverTables() {
  const found = new Set<HTMLElement>()
  for (const table of document.querySelectorAll('table')) {
    let ancestor = table.parentElement
    while (ancestor && ancestor !== document.body) {
      const overflow = window.getComputedStyle(ancestor).overflowX
      if (overflow === 'auto' || overflow === 'scroll') {
        found.add(ancestor)
        break
      }
      ancestor = ancestor.parentElement
    }
  }
  tableScrollers = [...found]
}

function isVisibleScrollable(scroller: HTMLElement) {
  if (!scroller.isConnected || scroller.clientWidth === 0 || scroller.scrollWidth - scroller.clientWidth < 5) return false
  const rect = scroller.getBoundingClientRect()
  return rect.width > 80 && rect.height > 15 && rect.bottom > 28 && rect.top < window.innerHeight - 32
}

function refresh() {
  frame = 0
  if (needsDiscovery) {
    discoverTables()
    needsDiscovery = false
  }

  // Never cover an open patient card, confirmation dialog or modal.
  if (document.querySelector('.modal-backdrop, .p-dialog-mask, [aria-modal="true"]')) {
    visible.value = false
    return
  }

  const candidates = tableScrollers.filter(isVisibleScrollable)
  const chosen = (preferredScroller && candidates.includes(preferredScroller) ? preferredScroller : null)
    ?? (activeScroller && candidates.includes(activeScroller) ? activeScroller : null)
    ?? candidates.sort((a, b) => {
      const center = window.innerHeight / 2
      const aRect = a.getBoundingClientRect()
      const bRect = b.getBoundingClientRect()
      const aDistance = Math.abs(Math.max(aRect.top, Math.min(center, aRect.bottom)) - center)
      const bDistance = Math.abs(Math.max(bRect.top, Math.min(center, bRect.bottom)) - center)
      return aDistance - bDistance
    })[0]

  if (!chosen) {
    activeScroller = null
    visible.value = false
    resizeObserver?.disconnect()
    return
  }

  if (activeScroller !== chosen) {
    activeScroller = chosen
    resizeObserver?.disconnect()
    resizeObserver?.observe(chosen)
    const table = chosen.querySelector('table')
    if (table) resizeObserver?.observe(table)
  }

  const rect = chosen.getBoundingClientRect()
  const left = Math.max(12, rect.left)
  const right = Math.min(window.innerWidth - 12, rect.right)
  const width = Math.max(0, right - left)
  if (width < 80) {
    visible.value = false
    return
  }

  const trackSpace = Math.max(1, width - 4) // 1px border and 1px padding on each side
  const maxScroll = Math.max(0, chosen.scrollWidth - chosen.clientWidth)
  const widthOfThumb = Math.min(trackSpace, Math.max(48, trackSpace * chosen.clientWidth / chosen.scrollWidth))
  dockLeft.value = left
  dockWidth.value = width
  thumbWidth.value = widthOfThumb
  thumbOffset.value = maxScroll ? (chosen.scrollLeft / maxScroll) * (trackSpace - widthOfThumb) : 0
  scrollNow.value = chosen.scrollLeft
  scrollMax.value = maxScroll
  visible.value = true
}

function schedule(discover = false) {
  if (discover) needsDiscovery = true
  if (!frame) frame = window.requestAnimationFrame(refresh)
}

function onNativeScroll(event: Event) {
  if (event.target === activeScroller || event.target === window || event.target === document) schedule()
}

function onPointerOver(event: PointerEvent) {
  const element = event.target
  if (!(element instanceof Node)) return
  const hovered = tableScrollers.find((scroller) => scroller.contains(element))
  if (hovered && hovered !== preferredScroller) {
    preferredScroller = hovered
    schedule()
  }
}

function moveThumb(clientX: number) {
  if (!activeScroller || !dock.value) return
  const trackSpace = Math.max(1, dock.value.getBoundingClientRect().width - 4)
  const usable = trackSpace - thumbWidth.value
  if (usable <= 0) return
  const start = dock.value.getBoundingClientRect().left + 2
  const offset = Math.max(0, Math.min(usable, clientX - start - grabOffset))
  activeScroller.scrollLeft = offset / usable * (activeScroller.scrollWidth - activeScroller.clientWidth)
  schedule()
}

function onPointerDown(event: PointerEvent) {
  if (!activeScroller || !dock.value) return
  if (event.button !== 0 && event.pointerType === 'mouse') return
  const thumb = (event.target as Element).closest('.global-table-scrollbar-thumb')
  grabOffset = thumb ? event.clientX - thumb.getBoundingClientRect().left : thumbWidth.value / 2
  dragging = true
  dock.value.setPointerCapture(event.pointerId)
  moveThumb(event.clientX)
}

function onPointerMove(event: PointerEvent) {
  if (dragging) moveThumb(event.clientX)
}

function onPointerEnd(event: PointerEvent) {
  dragging = false
  if (dock.value?.hasPointerCapture(event.pointerId)) dock.value.releasePointerCapture(event.pointerId)
}

function onKeyDown(event: KeyboardEvent) {
  if (!activeScroller) return
  const movements: Record<string, number> = {
    ArrowLeft: -80, ArrowRight: 80, PageUp: -activeScroller.clientWidth, PageDown: activeScroller.clientWidth,
  }
  if (event.key in movements) activeScroller.scrollLeft += movements[event.key]
  else if (event.key === 'Home') activeScroller.scrollLeft = 0
  else if (event.key === 'End') activeScroller.scrollLeft = activeScroller.scrollWidth
  else return
  event.preventDefault()
  schedule()
}

function onResize() { schedule(true) }
function onMutation() { schedule(true) }

onMounted(() => {
  resizeObserver = new ResizeObserver(() => schedule())
  mutationObserver = new MutationObserver(onMutation)
  // Vue/PrimeVue dialogs are sometimes teleported outside #app.
  mutationObserver.observe(document.body, { childList: true, subtree: true })
  window.addEventListener('scroll', onNativeScroll, true)
  window.addEventListener('resize', onResize)
  document.addEventListener('pointerover', onPointerOver)
  schedule(true)
})

onBeforeUnmount(() => {
  mutationObserver?.disconnect()
  resizeObserver?.disconnect()
  window.removeEventListener('scroll', onNativeScroll, true)
  window.removeEventListener('resize', onResize)
  document.removeEventListener('pointerover', onPointerOver)
  if (frame) window.cancelAnimationFrame(frame)
})
</script>

<template>
  <div
    v-show="visible"
    ref="dock"
    class="global-table-scrollbar"
    :style="{ left: `${dockLeft}px`, width: `${dockWidth}px` }"
    tabindex="0"
    role="scrollbar"
    aria-orientation="horizontal"
    aria-label="Горизонтальная прокрутка таблицы"
    :aria-valuemin="0"
    :aria-valuemax="Math.round(scrollMax)"
    :aria-valuenow="Math.round(scrollNow)"
    title="Перетащите ползунок вправо или влево, чтобы прокрутить таблицу"
    @pointerdown.prevent="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerEnd"
    @pointercancel="onPointerEnd"
    @keydown="onKeyDown"
  >
    <div class="global-table-scrollbar-thumb" :style="{ width: `${thumbWidth}px`, transform: `translateX(${thumbOffset}px)` }" />
  </div>
</template>
