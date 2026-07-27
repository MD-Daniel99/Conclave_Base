export function parseMoney(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (value === null || value === undefined) {
    return 0
  }

  const normalized = String(value)
    .trim()
    .replace(/[\s\u00a0\u202f]/g, '')
    .replace('−', '-')
    .replace(',', '.')
    .replace(/[^\d.-]/g, '')

  if (!normalized) {
    return 0
  }

  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function groupIntegerPart(value: string) {
  return value.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

function trimFraction(value: string) {
  return value.replace(/0+$/, '')
}

export function formatMoney(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const parsed = parseMoney(value)

  if (!Number.isFinite(parsed)) {
    return String(value)
  }

  const sign = parsed < 0 ? '−' : ''
  const absolute = Math.abs(parsed)
  const fixed = absolute.toFixed(Number.isInteger(absolute) ? 0 : 2)
  const [integerPart, rawFraction = ''] = fixed.split('.')
  const fraction = trimFraction(rawFraction)

  return `${sign}${groupIntegerPart(integerPart)}${fraction ? `,${fraction}` : ''} ₽`
}

export function formatMoneyInput(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return ''
  }

  const parsed = parseMoney(value)

  if (!Number.isFinite(parsed)) {
    return String(value)
  }

  const sign = parsed < 0 ? '−' : ''
  const absolute = Math.abs(parsed)
  const fixed = absolute.toFixed(Number.isInteger(absolute) ? 0 : 2)
  const [integerPart, rawFraction = ''] = fixed.split('.')
  const fraction = trimFraction(rawFraction)

  return `${sign}${groupIntegerPart(integerPart)}${fraction ? `,${fraction}` : ''}`
}
