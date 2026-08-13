/**
 * Нормативные сроки повторного обращения из Excel «Сроки пользования ТСР».
 * Для расчёта сроков маркер (1) / .1 после 8 не меняет ТСР:
 * 8-04-01 == 8(1)-04-01 == 8.1-04-01.
 * Эти данные намеренно не выводятся и не редактируются в справочнике ТСР.
 */
const TSR_REPEAT_TERM_MONTHS: Record<string, number> = {
  '8-01-01': 3,
  '8-01-02': 3,
  '8-06-04': 3,

  '8-06-03': 12,
  '8-08-05': 12,
  '8-08-06': 12,
  '8-08-07': 12,

  '8-01-03': 24,
  '8-01-04': 24,
  '8-02-01': 24,
  '8-02-02': 24,
  '8-02-03': 24,
  '8-03-01': 24,
  '8-03-02': 24,
  '8-03-03': 24,
  '8-07-01': 24,
  '8-07-09': 24,
  '8-07-10': 24,
  '8-07-11': 24,
  '8-04-01': 24,
  '8-07-12': 24,
  '8-07-13': 24,
  '8-07-14': 24,

  '8-07-04': 36,
  '8-07-05': 36,
  '8-04-02': 36,
  '8-04-03': 36,
  '8-05-01': 36,
}

export function normalizeTsrCode(value: string | null | undefined) {
  const raw = String(value ?? '')
    .trim()
    .replace(/[–—]/g, '-')
  const match = raw.match(/^\s*(8(?:\(1\)|\.1)?-\d{2}(?:-\d{2})?)/i)
  return (match?.[1] ?? '').replace(/^8(?:\(1\)|\.1)-/i, '8-')
}

export function getTsrRepeatTermMonths(value: string | null | undefined) {
  return TSR_REPEAT_TERM_MONTHS[normalizeTsrCode(value)] ?? null
}

export function hasAutomaticRepeatVisitTerm(value: string | null | undefined) {
  return getTsrRepeatTermMonths(value) !== null
}

export function calculateTsrRepeatVisitDate(
  value: string | null | undefined,
  checkDate: string | null | undefined,
) {
  const months = getTsrRepeatTermMonths(value)
  const dateText = String(checkDate ?? '').slice(0, 10)
  if (months === null || !/^\d{4}-\d{2}-\d{2}$/.test(dateText)) return ''

  const [year, month, day] = dateText.split('-').map(Number)
  const monthIndex = month - 1 + months
  const targetYear = year + Math.floor(monthIndex / 12)
  const targetMonthIndex = ((monthIndex % 12) + 12) % 12
  const lastDay = new Date(Date.UTC(targetYear, targetMonthIndex + 1, 0)).getUTCDate()
  const targetDay = Math.min(day, lastDay)

  return [
    String(targetYear).padStart(4, '0'),
    String(targetMonthIndex + 1).padStart(2, '0'),
    String(targetDay).padStart(2, '0'),
  ].join('-')
}
