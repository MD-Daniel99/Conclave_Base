export type SortDirection = 'asc' | 'desc' | null
export type TableFilterKind = 'text' | 'number' | 'date' | 'select'

export interface SortState {
  key: string | null
  direction: SortDirection
}

function normalizeText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(normalizeText).join(' ')
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).map(normalizeText).join(' ')
  }
  return String(value).trim().toLocaleLowerCase('ru-RU')
}

function parseComparableNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const raw = String(value ?? '')
    .replace(/\s|\u00a0/g, '')
    .replace(',', '.')
    .replace(/[^\d.+-]/g, '')
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeNumberSearchText(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  return String(value ?? '')
    .trim()
    .replace(/\s|\u00a0/g, '')
    .replace(',', '.')
    .replace(/[^\d.-]/g, '')
}

function normalizeDate(value: unknown): string {
  const raw = String(value ?? '').trim()
  if (!raw) return ''
  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`
  const ruMatch = raw.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/)
  if (ruMatch) {
    return `${ruMatch[3]}-${ruMatch[2].padStart(2, '0')}-${ruMatch[1].padStart(2, '0')}`
  }
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toISOString().slice(0, 10)
}

function dateSearchText(value: unknown): string {
  const raw = normalizeText(value)
  const iso = normalizeDate(value)
  if (!iso) return raw
  const [year, month, day] = iso.split('-')
  return `${raw} ${iso} ${day}.${month}.${year}`.trim()
}

function splitRange(filter: string): [string, string] | null {
  const separators = ['..', '—', '–']
  for (const separator of separators) {
    const index = filter.indexOf(separator)
    if (index >= 0) {
      return [filter.slice(0, index).trim(), filter.slice(index + separator.length).trim()]
    }
  }
  return null
}

export function matchesTableFilter(
  value: unknown,
  filterValue: unknown,
  kind: TableFilterKind = 'text',
): boolean {
  const filter = String(filterValue ?? '').trim()
  if (!filter) return true

  // A client may have several certificate dates or TSR values. A column
  // filter matches when at least one value in that cell matches.
  if (Array.isArray(value)) {
    return value.some((item) => matchesTableFilter(item, filter, kind))
  }

  if (kind === 'number') {
    const actual = parseComparableNumber(value)
    if (actual === null) return false

    const operator = filter.match(/^(<=|>=|!=|=|<|>)\s*(.+)$/)
    if (operator) {
      const expected = parseComparableNumber(operator[2])
      if (expected === null) return false
      switch (operator[1]) {
        case '<=': return actual <= expected
        case '>=': return actual >= expected
        case '!=': return actual !== expected
        case '=': return actual === expected
        case '<': return actual < expected
        case '>': return actual > expected
      }
    }

    const range = splitRange(filter)
    if (range) {
      const lower = parseComparableNumber(range[0])
      const upper = parseComparableNumber(range[1])
      return (lower === null || actual >= lower) && (upper === null || actual <= upper)
    }

    // A plain number acts like Google Sheets' quick filter: entering "3"
    // finds 3 893 700, while operators/ranges above keep numeric semantics.
    const actualText = normalizeNumberSearchText(value)
    const filterText = normalizeNumberSearchText(filter)
    return Boolean(filterText) && actualText.includes(filterText)
  }

  if (kind === 'date') {
    const actual = normalizeDate(value)
    if (!actual) return false

    const range = splitRange(filter)
    if (range) {
      const lower = normalizeDate(range[0])
      const upper = normalizeDate(range[1])
      return (!lower || actual >= lower) && (!upper || actual <= upper)
    }

    const normalizedFilterDate = normalizeDate(filter)
    const isFullDate = /^\d{4}-\d{1,2}-\d{1,2}$/.test(filter)
      || /^\d{1,2}[./-]\d{1,2}[./-]\d{4}$/.test(filter)
    if (normalizedFilterDate && isFullDate) {
      return actual === normalizedFilterDate
    }

    // Partial date input is supported: "05.08", "2026-08" and "05".
    return dateSearchText(value).includes(normalizeText(filter))
  }

  if (kind === 'select') {
    return normalizeText(value) === normalizeText(filter)
  }

  return normalizeText(value).includes(normalizeText(filter))
}

function comparableScalar(value: unknown): unknown {
  if (!Array.isArray(value)) return value
  const nonEmpty = value.filter((item) => String(item ?? '').trim())
  if (nonEmpty.length === 0) return ''
  return [...nonEmpty].sort((left, right) => normalizeText(left).localeCompare(normalizeText(right), 'ru', {
    numeric: true,
    sensitivity: 'base',
  }))[nonEmpty.length - 1]
}

export function compareTableValues(leftValue: unknown, rightValue: unknown): number {
  const left = comparableScalar(leftValue)
  const right = comparableScalar(rightValue)

  const leftNumber = parseComparableNumber(left)
  const rightNumber = parseComparableNumber(right)
  if (leftNumber !== null && rightNumber !== null) return leftNumber - rightNumber

  const leftDate = normalizeDate(left)
  const rightDate = normalizeDate(right)
  const datePattern = /^\d{4}-\d{2}-\d{2}$/
  if (datePattern.test(leftDate) && datePattern.test(rightDate)) return leftDate.localeCompare(rightDate)

  return normalizeText(left).localeCompare(normalizeText(right), 'ru', {
    numeric: true,
    sensitivity: 'base',
  })
}

export function sortTableRows<T>(
  rows: T[],
  key: string | null,
  direction: SortDirection,
  accessor: (row: T, key: string) => unknown,
): T[] {
  if (!key || !direction) return [...rows]
  const multiplier = direction === 'asc' ? 1 : -1
  return [...rows].sort((left, right) => multiplier * compareTableValues(accessor(left, key), accessor(right, key)))
}

export function nextSortState(current: SortState, key: string): SortState {
  if (current.key !== key) return { key, direction: 'asc' }
  if (current.direction === 'asc') return { key, direction: 'desc' }
  if (current.direction === 'desc') return { key: null, direction: null }
  return { key, direction: 'asc' }
}
