/**
 * Table column resizing across the application.
 * Only tables with a real header are enhanced. Resizing is persisted per user,
 * page and column identity, independently of filtering, pagination and sorting.
 * The underlying Vue table cells are not moved or re-rendered by this module.
 */
type Widths = Record<string, number>
const MIN = 86
const MAX = 680
const headerKeys = new WeakMap<HTMLTableElement, string>()
// Preserve natural widths before applying a user's preferences. Without this,
// switching accounts within the same mounted SPA inherits the previous user's widths.
const defaultWidths = new WeakMap<HTMLTableElement, Widths>()
const clamp = (n: number, min: number) => Math.max(min, Math.min(MAX, Math.round(n)))

function columnKey(th: HTMLTableCellElement, index: number) {
  const explicit = th.dataset.columnKey
  if (explicit) return explicit
  const label = (th.querySelector('.table-sort-button')?.textContent || th.textContent || '')
    .replace(/[↕▲▼⋮]/g, '').replace(/\s+/g, ' ').trim().slice(0, 72)
  return `${index}:${label || th.getAttribute('aria-label') || 'column'}`
}

function storageKey(table: HTMLTableElement, index: number, userId: string) {
  const tableId = table.dataset.resizeId || `table-${index}`
  return `dbcrm.table-columns.v1:${userId}:${location.pathname}:${tableId}`
}

function load(key: string): Widths {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Widths : {}
  } catch { return {} }
}

function save(key: string, value: Widths) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* blocked storage: still resizable */ }
}

function enhance(table: HTMLTableElement, index: number, userId: string) {
  const header = table.tHead?.rows[0]
  if (!header || !header.cells.length) return
  const cells = Array.from(header.cells) as HTMLTableCellElement[]
  // Spanning headers require a dedicated layout and are left intact.
  if (cells.some((th) => th.colSpan !== 1 || th.rowSpan > 1)) return
  const key = storageKey(table, index, userId)
  const identity = `${key}:${cells.map(columnKey).join('|')}`
  if (headerKeys.get(table) === identity && cells.every((th) => th.querySelector(':scope > .dbcrm-column-resize-handle'))) return

  const saved = load(key)
  const natural = defaultWidths.get(table) || {}
  const original = cells.map((th, colIndex) => {
    const min = th.classList.contains('selection-cell') ? 48 : MIN
    const identifier = columnKey(th, colIndex)
    const measured = th.getBoundingClientRect().width
    const fallback = min === 48 ? 56 : Math.max(116, measured || 150)
    if (!Number.isFinite(natural[identifier])) natural[identifier] = fallback
    const value = saved[identifier]
    return clamp(Number.isFinite(value) ? value : natural[identifier], min)
  })
  defaultWidths.set(table, natural)
  const existingGroup = table.querySelector(':scope > colgroup.dbcrm-resize-cols')
  const group = existingGroup || document.createElement('colgroup')
  group.classList.add('dbcrm-resize-cols')
  group.replaceChildren(...cells.map(() => document.createElement('col')))
  if (!existingGroup) table.insertBefore(group, table.firstChild)
  const columns = Array.from(group.children) as HTMLTableColElement[]
  const widths = [...original]

  function layout() {
    columns.forEach((col, idx) => { col.style.width = `${widths[idx]}px` })
    // Explicit pixel width keeps the user's column widths precise. The surrounding
    // .table-wrap remains horizontally scrollable as columns are expanded.
    table.style.setProperty('width', `${widths.reduce((a, b) => a + b, 0)}px`, 'important')
    table.style.setProperty('min-width', '0', 'important')
  }
  layout()
  table.classList.add('dbcrm-resizable-table')

  cells.forEach((th, colIndex) => {
    th.classList.add('dbcrm-resizable-header')
    th.querySelectorAll(':scope > .dbcrm-column-resize-handle').forEach((old) => old.remove())
    const handle = document.createElement('span')
    handle.className = 'dbcrm-column-resize-handle'
    handle.setAttribute('role', 'separator')
    handle.setAttribute('aria-orientation', 'vertical')
    handle.setAttribute('aria-label', `Изменить ширину колонки ${columnKey(th, colIndex)}`)
    handle.setAttribute('title', 'Перетащите для изменения ширины')
    handle.tabIndex = 0
    handle.draggable = false
    handle.addEventListener('dragstart', (event) => { event.stopPropagation(); event.preventDefault() })
    th.appendChild(handle)

    const update = (value: number) => {
      widths[colIndex] = clamp(value, th.classList.contains('selection-cell') ? 48 : MIN)
      layout()
    }
    const persist = () => {
      const latest = load(key)
      latest[columnKey(th, colIndex)] = widths[colIndex]
      save(key, latest)
    }
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return
      event.stopPropagation()
      event.preventDefault()
      const pointerX = event.clientX
      const startWidth = widths[colIndex]
      handle.setPointerCapture(event.pointerId)
      handle.classList.add('dragging')
      const move = (moveEvent: PointerEvent) => update(startWidth + moveEvent.clientX - pointerX)
      const end = () => {
        persist()
        handle.classList.remove('dragging')
        handle.removeEventListener('pointermove', move)
        handle.removeEventListener('pointerup', end)
        handle.removeEventListener('pointercancel', end)
      }
      handle.addEventListener('pointermove', move)
      handle.addEventListener('pointerup', end)
      handle.addEventListener('pointercancel', end)
    })
    handle.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      event.preventDefault()
      event.stopPropagation()
      update(widths[colIndex] + (event.key === 'ArrowRight' ? 16 : -16))
      persist()
    })
  })
  headerKeys.set(table, identity)
}

export function initResizableTables(getUserId: () => string | undefined) {
  let pending = false
  const scan = () => {
    pending = false
    const userId = getUserId()
    // Never mix the preferences of different users while auth is loading.
    if (!userId) return
    document.querySelectorAll<HTMLTableElement>('table').forEach((table, index) => {
      try { enhance(table, index, userId) } catch (error) { console.warn('Column resizing unavailable for table', error) }
    })
  }
  const schedule = () => {
    if (!pending) {
      pending = true
      requestAnimationFrame(scan)
    }
  }
  const observer = new MutationObserver(schedule)
  observer.observe(document.getElementById('app') || document.body, { childList: true, subtree: true })
  schedule()
  return () => observer.disconnect()
}
