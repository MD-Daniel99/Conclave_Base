import { ref, type Ref } from 'vue'

function normalizeOrder(saved: unknown, availableKeys: string[]): string[] {
  const available = new Set(availableKeys)
  const result: string[] = []

  if (Array.isArray(saved)) {
    for (const value of saved) {
      const key = String(value)
      if (available.has(key) && !result.includes(key)) {
        result.push(key)
      }
    }
  }

  for (const key of availableKeys) {
    if (!result.includes(key)) result.push(key)
  }

  return result
}

function readStoredOrder(storageKey: string, availableKeys: string[]): string[] {
  if (typeof window === 'undefined') return [...availableKeys]

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return [...availableKeys]
    return normalizeOrder(JSON.parse(raw), availableKeys)
  } catch {
    return [...availableKeys]
  }
}

export function usePersistentColumnOrder(storageKey: string, initialKeys: string[]) {
  const order = ref<string[]>(readStoredOrder(storageKey, initialKeys))
  const draggingKey = ref<string | null>(null)

  function persist() {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(order.value))
    } catch {
      // localStorage may be unavailable in private/restricted browser contexts.
    }
  }

  function syncKeys(availableKeys: string[]) {
    const next = normalizeOrder(order.value, availableKeys)
    if (next.join('\u0000') !== order.value.join('\u0000')) {
      order.value = next
      persist()
    }
  }

  function startDrag(key: string, event?: DragEvent) {
    draggingKey.value = key
    if (event?.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move'
      event.dataTransfer.setData('text/plain', key)
    }
  }

  function dropOn(targetKey: string, event?: DragEvent) {
    const sourceKey = draggingKey.value || event?.dataTransfer?.getData('text/plain') || ''
    draggingKey.value = null
    if (!sourceKey || sourceKey === targetKey) return

    const sourceIndex = order.value.indexOf(sourceKey)
    const targetIndex = order.value.indexOf(targetKey)
    if (sourceIndex < 0 || targetIndex < 0) return

    const next = [...order.value]
    next.splice(sourceIndex, 1)
    next.splice(targetIndex, 0, sourceKey)
    order.value = next
    persist()
  }

  function endDrag() {
    draggingKey.value = null
  }

  return {
    order: order as Ref<string[]>,
    draggingKey,
    syncKeys,
    startDrag,
    dropOn,
    endDrag,
  }
}
