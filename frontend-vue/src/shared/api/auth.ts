import { api } from './http'
import type { LoginPayload, LoginResponse, User, UserSettings } from '@/shared/types/auth'

export async function login(payload: LoginPayload) {
  const { data } = await api.post<LoginResponse>('/auth/login', payload)
  return data
}

export async function fetchMe() {
  const { data } = await api.get<User>('/auth/me')
  return data
}

export async function fetchUsers() {
  const { data } = await api.get<User[]>('/auth/users')
  return data
}

export interface CreateUserPayload {
  username: string
  password: string
  role: string
  is_active?: boolean
}

export async function createUser(payload: CreateUserPayload) {
  const { data } = await api.post<User>('/auth/register', payload)
  return data
}

export interface UpdateUserPayload {
  username?: string
  password?: string
  role?: string
  is_active?: boolean
}

export async function updateUser(userId: string, payload: UpdateUserPayload) {
  const { data } = await api.patch<User>(`/auth/users/${userId}`, payload)
  return data
}

export async function deleteUser(userId: string) {
  await api.delete(`/auth/users/${userId}`)
}

export async function fetchUserSettings(userId: string) {
  const { data } = await api.get<UserSettings>(`/auth/users/${userId}/settings`)
  return data
}

export async function updateUserSettings(userId: string, payload: UserSettings) {
  const { data } = await api.patch<{ status: string }>(`/auth/users/${userId}/settings`, payload)
  return data
}


export async function touchPresence() {
  await api.post('/auth/presence')
}
