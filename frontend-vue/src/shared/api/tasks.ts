import { api } from './http'

export type TaskStatus = 'planned' | 'in_progress' | 'done' | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface TaskUser {
  user_id: string
  username: string
  role: string
}

export interface CalendarTask {
  task_id: string
  title: string
  description?: string | null
  start_at: string
  due_at: string
  all_day: boolean
  status: TaskStatus
  priority: TaskPriority
  color?: string | null
  created_by?: string | null
  creator?: TaskUser | null
  assignees: TaskUser[]
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface TaskNotification {
  notification_id: string
  user_id: string
  task_id: string
  kind: string
  title: string
  body?: string | null
  created_at: string
  read_at?: string | null
  task_title?: string | null
  task_due_at?: string | null
}

export interface TaskPayload {
  title: string
  description?: string | null
  start_at: string
  due_at: string
  all_day: boolean
  status: TaskStatus
  priority: TaskPriority
  color?: string | null
  assignee_ids: string[]
}

export type TaskUpdatePayload = Partial<TaskPayload>

export interface FetchTasksParams {
  start?: string
  end?: string
  assignee_id?: string
  mine?: boolean
  status?: TaskStatus
}

export async function fetchTasks(params: FetchTasksParams = {}) {
  const { data } = await api.get<CalendarTask[]>('/tasks', { params })
  return data
}

export async function fetchTask(taskId: string) {
  const { data } = await api.get<CalendarTask>(`/tasks/${taskId}`)
  return data
}

export async function createTask(payload: TaskPayload) {
  const { data } = await api.post<CalendarTask>('/tasks', payload)
  return data
}

export async function updateTask(taskId: string, payload: TaskUpdatePayload) {
  const { data } = await api.patch<CalendarTask>(`/tasks/${taskId}`, payload)
  return data
}

export async function deleteTask(taskId: string) {
  await api.delete(`/tasks/${taskId}`)
}

export async function fetchTaskUsers() {
  const { data } = await api.get<TaskUser[]>('/tasks/users')
  return data
}

export async function fetchTaskNotifications(unreadOnly = false, limit = 50) {
  const { data } = await api.get<TaskNotification[]>('/tasks/notifications/list', {
    params: { unread_only: unreadOnly, limit },
  })
  return data
}

export async function markTaskNotificationRead(notificationId: string) {
  const { data } = await api.post<TaskNotification>(`/tasks/notifications/${notificationId}/read`)
  return data
}

export async function markAllTaskNotificationsRead() {
  const { data } = await api.post<{ status: string; updated: number }>('/tasks/notifications/read-all')
  return data
}
