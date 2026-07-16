import type { Token, UserLogin, UserRead } from '@/shared/api/generated/types.gen'

export type LoginPayload = UserLogin
export type LoginResponse = Token
export type User = UserRead

export interface UserSettings {
  tax_percent?: number | null
  acq_percent?: number | null
  [key: string]: unknown
}
