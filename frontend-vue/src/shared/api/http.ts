import axios, { AxiosError } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
})

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`
    return
  }

  delete api.defaults.headers.common.Authorization
}

export function getApiErrorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const location = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => part !== 'body').join('.') : ''
          const message = item.msg ?? JSON.stringify(item)
          return location ? `${location}: ${message}` : message
        })
        .join(', ')
    }

    if (error.response?.status) {
      return `Ошибка сервера (${error.response.status})`
    }
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Неизвестная ошибка'
}
