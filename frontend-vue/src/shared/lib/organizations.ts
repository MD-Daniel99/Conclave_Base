/** The same legal-entity keys are used in patient cards and accounting. */
export const SMART_COMPANY = 'ООО "Смарт Движение"'
export const ZET_COMPANY = 'ООО «ПрОП ДВИЖЕНИЕ ЗЕТ»'
export const DMK_COMPANY = 'ИП ДМК'

export const COMPANY_OPTIONS = [
  { value: SMART_COMPANY, label: 'ООО Смарт Движение' },
  { value: ZET_COMPANY, label: 'ООО ПрОП ДВИЖЕНИЕ ЗЕТ' },
  { value: DMK_COMPANY, label: 'ИП ДМК' },
] as const

export const ALL_COMPANIES: string[] = COMPANY_OPTIONS.map((company) => company.value)

/** An unassigned historical patient belongs to Smart, as in the accounting API. */
export function accountingCompany(value: unknown): string {
  return String(value ?? '').trim() || SMART_COMPANY
}

export function companyBadgeClass(value: unknown): string {
  const company = accountingCompany(value)
  if (company === SMART_COMPANY) return 'org-badge-smart'
  if (company === ZET_COMPANY) return 'org-badge-zet'
  if (company === DMK_COMPANY) return 'org-badge-dmk'
  return 'org-badge-other'
}

/** Keep a distinct empty array: it means "show nobody", not "show everybody". */
export function readCompanySelection(key: string, fallback: readonly string[] = ALL_COMPANIES): string[] {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return [...fallback]
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [...fallback]
    const selected = new Set(parsed.filter((item): item is string => typeof item === 'string'))
    return ALL_COMPANIES.filter((company) => selected.has(company))
  } catch {
    return [...fallback]
  }
}

export function writeCompanySelection(key: string, selection: readonly string[]): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(selection))
  } catch {
    // Storage may be disabled; selection still works for this visit.
  }
}
