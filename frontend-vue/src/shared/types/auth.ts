import type { Token, UserLogin, UserRead } from '@/shared/api/generated/types.gen'

export type LoginPayload = UserLogin
export type LoginResponse = Token
export type User = UserRead

export interface UserSettings {
  // Старый ключ читается как резервный, чтобы не потерять сохранённый процент.
  tax_percent?: number | null
  tax_usn_percent?: number | null
  tax_osno_percent?: number | null
  acq_percent?: number | null
  vat_percent?: number | null
  [key: string]: unknown
}
