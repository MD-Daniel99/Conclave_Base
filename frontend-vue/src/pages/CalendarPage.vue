<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ListChecks,
  Plus,
  RefreshCw,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from '@lucide/vue'

import { useAuthStore } from '@/app/stores/auth'
import { getApiErrorMessage } from '@/shared/api/http'
import {
  createTask,
  deleteTask,
  fetchTask,
  fetchTasks,
  fetchTaskUsers,
  updateTask,
  type CalendarTask,
  type TaskPayload,
  type TaskPriority,
  type TaskStatus,
  type TaskUser,
} from '@/shared/api/tasks'
import { useSuccessToast } from '@/shared/composables/useAppFeedback'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const tasks = ref<CalendarTask[]>([])
const users = ref<TaskUser[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const successMessage = ref('')
useSuccessToast(successMessage)

const today = startOfDay(new Date())
const visibleMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))
const selectedDate = ref(today)
const mineOnly = ref(false)
const assigneeFilter = ref('')
const statusFilter = ref<'' | TaskStatus>('')
const modalOpen = ref(false)
const editingTask = ref<CalendarTask | null>(null)
const openTimePicker = ref<'' | 'start' | 'due'>('')
const deleteConfirmOpen = ref(false)
const deleteCandidate = ref<{ taskId: string; title: string } | null>(null)
let syncTimer: number | undefined

const form = reactive({
  title: '',
  description: '',
  startDate: '',
  startTime: '09:00',
  dueDate: '',
  dueTime: '10:00',
  allDay: false,
  status: 'planned' as TaskStatus,
  priority: 'normal' as TaskPriority,
  color: '#8B5CF6',
  assigneeIds: [] as string[],
})

const weekdayLabels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const statusOptions: Array<{ value: TaskStatus; label: string }> = [
  { value: 'planned', label: 'Запланировано' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'done', label: 'Выполнено' },
  { value: 'cancelled', label: 'Отменено' },
]
const priorityOptions: Array<{ value: TaskPriority; label: string }> = [
  { value: 'low', label: 'Низкий' },
  { value: 'normal', label: 'Обычный' },
  { value: 'high', label: 'Высокий' },
  { value: 'urgent', label: 'Срочный' },
]
const colorOptions = ['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B', '#EF4444', '#EC4899']

const timeOptions = Array.from({ length: 96 }, (_, index) => {
  const totalMinutes = index * 15
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
})

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function endOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999)
}

function addDays(date: Date, amount: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + amount)
  return next
}

function startOfWeek(date: Date) {
  const value = startOfDay(date)
  const day = value.getDay() || 7
  return addDays(value, 1 - day)
}

function endOfWeek(date: Date) {
  return endOfDay(addDays(startOfWeek(date), 6))
}

function toDateKey(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function toIso(dateValue: string, timeValue: string, allDay: boolean, end = false) {
  const time = allDay ? (end ? '23:59' : '00:00') : timeValue
  return new Date(`${dateValue}T${time}:00`).toISOString()
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    hourCycle: 'h23',
  }).format(new Date(value))
}

function formatDate(value: string | Date) {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value))
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' }).format(new Date(value))
}

function statusLabel(status: TaskStatus) {
  return statusOptions.find((item) => item.value === status)?.label ?? status
}

function priorityLabel(priority: TaskPriority) {
  return priorityOptions.find((item) => item.value === priority)?.label ?? priority
}

function priorityColor(task: CalendarTask) {
  if (task.status === 'done') return '#10B981'
  if (task.status === 'cancelled') return '#64748B'
  if (task.color) return task.color
  if (task.priority === 'urgent') return '#EF4444'
  if (task.priority === 'high') return '#F59E0B'
  if (task.priority === 'low') return '#3B82F6'
  return '#8B5CF6'
}

function normalizeTimeValue(value: string) {
  const compact = value.trim().replace('.', ':')
  const digits = compact.replace(/\D/g, '')
  const candidate = compact.includes(':')
    ? compact
    : digits.length >= 3
      ? `${digits.slice(0, -2)}:${digits.slice(-2)}`
      : compact
  const match = candidate.match(/^(\d{1,2}):(\d{1,2})$/)
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (!Number.isInteger(hours) || !Number.isInteger(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function timeValue(kind: 'start' | 'due') {
  return kind === 'start' ? form.startTime : form.dueTime
}

function setTimeValue(kind: 'start' | 'due', value: string, close = false, switchToTimed = true) {
  if (switchToTimed && form.allDay) form.allDay = false
  if (kind === 'start') form.startTime = value
  else form.dueTime = value
  if (close) openTimePicker.value = ''
}

function onAllDayChange(event: Event) {
  const target = event.target as HTMLInputElement
  form.allDay = target.checked
  openTimePicker.value = ''
}

function onTimeInput(kind: 'start' | 'due', event: Event) {
  const target = event.target as HTMLInputElement
  let value = target.value.replace(/[^0-9:.]/g, '').replace('.', ':').slice(0, 5)
  if (!value.includes(':')) {
    const digits = value.replace(/\D/g, '').slice(0, 4)
    if (digits.length > 2) value = `${digits.slice(0, 2)}:${digits.slice(2)}`
    else value = digits
  }
  setTimeValue(kind, value)
}

function normalizeTimeField(kind: 'start' | 'due') {
  const normalized = normalizeTimeValue(timeValue(kind))
  if (normalized) setTimeValue(kind, normalized, false, false)
}

function toggleTimePicker(kind: 'start' | 'due') {
  openTimePicker.value = openTimePicker.value === kind ? '' : kind
}

function onDocumentMouseDown(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('.task-time-control')) return
  openTimePicker.value = ''
}

const monthLabel = computed(() => new Intl.DateTimeFormat('ru-RU', {
  month: 'long', year: 'numeric',
}).format(visibleMonth.value).replace(/^./, (letter) => letter.toUpperCase()))

const calendarStart = computed(() => startOfWeek(new Date(visibleMonth.value.getFullYear(), visibleMonth.value.getMonth(), 1)))
const calendarEnd = computed(() => endOfWeek(new Date(visibleMonth.value.getFullYear(), visibleMonth.value.getMonth() + 1, 0)))
const calendarDays = computed(() => {
  const result: Date[] = []
  let cursor = calendarStart.value
  while (cursor <= calendarEnd.value) {
    result.push(cursor)
    cursor = addDays(cursor, 1)
  }
  return result
})

const visibleTasks = computed(() => tasks.value.filter((task) => {
  if (mineOnly.value && !task.assignees.some((user) => user.user_id === authStore.user?.user_id)) return false
  if (assigneeFilter.value && !task.assignees.some((user) => user.user_id === assigneeFilter.value)) return false
  if (statusFilter.value && task.status !== statusFilter.value) return false
  return true
}))

function taskTouchesDay(task: CalendarTask, date: Date) {
  const dayStart = startOfDay(date).getTime()
  const dayEnd = endOfDay(date).getTime()
  return new Date(task.start_at).getTime() <= dayEnd && new Date(task.due_at).getTime() >= dayStart
}

function tasksForDay(date: Date) {
  return visibleTasks.value
    .filter((task) => taskTouchesDay(task, date))
    .sort((a, b) => {
      if (a.all_day !== b.all_day) return a.all_day ? -1 : 1
      return new Date(a.start_at).getTime() - new Date(b.start_at).getTime()
    })
}

const selectedDayTasks = computed(() => tasksForDay(selectedDate.value))
const upcomingTasks = computed(() => visibleTasks.value
  .filter((task) => ['planned', 'in_progress'].includes(task.status) && new Date(task.due_at).getTime() >= Date.now())
  .sort((a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime())
  .slice(0, 6))

const summary = computed(() => {
  const now = Date.now()
  const todayStart = startOfDay(new Date()).getTime()
  const todayEnd = endOfDay(new Date()).getTime()
  return {
    today: visibleTasks.value.filter((task) => taskTouchesDay(task, new Date()) && ['planned', 'in_progress'].includes(task.status)).length,
    overdue: visibleTasks.value.filter((task) => ['planned', 'in_progress'].includes(task.status) && new Date(task.due_at).getTime() < now).length,
    inProgress: visibleTasks.value.filter((task) => task.status === 'in_progress').length,
    done: visibleTasks.value.filter((task) => task.status === 'done' && new Date(task.completed_at ?? task.updated_at).getTime() >= todayStart && new Date(task.completed_at ?? task.updated_at).getTime() <= todayEnd).length,
  }
})

function isToday(date: Date) {
  return toDateKey(date) === toDateKey(today)
}

function isSelected(date: Date) {
  return toDateKey(date) === toDateKey(selectedDate.value)
}

function isCurrentMonth(date: Date) {
  return date.getMonth() === visibleMonth.value.getMonth() && date.getFullYear() === visibleMonth.value.getFullYear()
}

function chooseDay(date: Date) {
  selectedDate.value = startOfDay(date)
}

function changeMonth(delta: number) {
  visibleMonth.value = new Date(visibleMonth.value.getFullYear(), visibleMonth.value.getMonth() + delta, 1)
}

function goToday() {
  visibleMonth.value = new Date(today.getFullYear(), today.getMonth(), 1)
  selectedDate.value = today
}

async function loadUsers() {
  try {
    users.value = await fetchTaskUsers()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function loadTasks(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    tasks.value = await fetchTasks({
      start: calendarStart.value.toISOString(),
      end: calendarEnd.value.toISOString(),
    })
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    if (!silent) loading.value = false
  }
}

function resetForm(date = selectedDate.value) {
  const dateKey = toDateKey(date)
  form.title = ''
  form.description = ''
  form.startDate = dateKey
  form.startTime = '09:00'
  form.dueDate = dateKey
  form.dueTime = '10:00'
  form.allDay = false
  form.status = 'planned'
  form.priority = 'normal'
  form.color = '#8B5CF6'
  form.assigneeIds = authStore.user?.user_id ? [authStore.user.user_id] : []
}

function openNewTask(date = selectedDate.value) {
  editingTask.value = null
  resetForm(date)
  modalOpen.value = true
}

function openTask(task: CalendarTask) {
  editingTask.value = task
  const start = new Date(task.start_at)
  const due = new Date(task.due_at)
  form.title = task.title
  form.description = task.description ?? ''
  form.startDate = toDateKey(start)
  form.startTime = `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}`
  form.dueDate = toDateKey(due)
  form.dueTime = `${String(due.getHours()).padStart(2, '0')}:${String(due.getMinutes()).padStart(2, '0')}`
  form.allDay = task.all_day
  form.status = task.status
  form.priority = task.priority
  form.color = task.color ?? priorityColor(task)
  form.assigneeIds = task.assignees.map((user) => user.user_id)
  modalOpen.value = true
}

function closeModal() {
  openTimePicker.value = ''
  deleteConfirmOpen.value = false
  deleteCandidate.value = null
  modalOpen.value = false
  editingTask.value = null
  if (route.query.task) {
    void router.replace({ query: { ...route.query, task: undefined } })
  }
}

async function saveTask() {
  error.value = ''
  if (!form.title.trim()) {
    error.value = 'Введите название задачи'
    return
  }
  if (!form.startDate || !form.dueDate) {
    error.value = 'Укажите начало и срок задачи'
    return
  }
  const normalizedStartTime = form.allDay ? '00:00' : normalizeTimeValue(form.startTime)
  const normalizedDueTime = form.allDay ? '23:59' : normalizeTimeValue(form.dueTime)
  if (!normalizedStartTime || !normalizedDueTime) {
    error.value = 'Укажите время в 24-часовом формате ЧЧ:ММ'
    return
  }
  form.startTime = normalizedStartTime
  form.dueTime = normalizedDueTime
  const startAt = toIso(form.startDate, normalizedStartTime, form.allDay, false)
  const dueAt = toIso(form.dueDate, normalizedDueTime, form.allDay, true)
  if (new Date(dueAt).getTime() < new Date(startAt).getTime()) {
    error.value = 'Срок задачи не может быть раньше её начала'
    return
  }
  const payload: TaskPayload = {
    title: form.title.trim(),
    description: form.description.trim() || null,
    start_at: startAt,
    due_at: dueAt,
    all_day: form.allDay,
    status: form.status,
    priority: form.priority,
    color: form.color,
    assignee_ids: form.assigneeIds,
  }
  saving.value = true
  try {
    const saved = editingTask.value
      ? await updateTask(editingTask.value.task_id, payload)
      : await createTask(payload)
    selectedDate.value = startOfDay(new Date(saved.start_at))
    visibleMonth.value = new Date(selectedDate.value.getFullYear(), selectedDate.value.getMonth(), 1)
    successMessage.value = editingTask.value ? 'Задача обновлена' : 'Задача создана'
    closeModal()
    await loadTasks(true)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

function requestDeleteTask() {
  const task = editingTask.value
  if (!task || saving.value) return
  deleteCandidate.value = { taskId: task.task_id, title: task.title }
  deleteConfirmOpen.value = true
  openTimePicker.value = ''
}

function cancelDeleteTask() {
  if (saving.value) return
  deleteConfirmOpen.value = false
  deleteCandidate.value = null
}

async function confirmDeleteTask() {
  const candidate = deleteCandidate.value
  if (!candidate || saving.value) return

  const taskId = candidate.taskId
  saving.value = true
  error.value = ''
  try {
    await deleteTask(taskId)
    successMessage.value = 'Задача удалена'
    deleteConfirmOpen.value = false
    deleteCandidate.value = null
    closeModal()
    await loadTasks(true)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

async function quickComplete(task: CalendarTask) {
  try {
    await updateTask(task.task_id, { status: task.status === 'done' ? 'planned' : 'done' })
    await loadTasks(true)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function openTaskFromQuery() {
  const taskId = typeof route.query.task === 'string' ? route.query.task : ''
  if (!taskId) return
  try {
    const task = await fetchTask(taskId)
    const date = startOfDay(new Date(task.start_at))
    visibleMonth.value = new Date(date.getFullYear(), date.getMonth(), 1)
    selectedDate.value = date
    await loadTasks(true)
    openTask(task)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') void loadTasks(true)
}

watch(visibleMonth, () => { void loadTasks() })
watch(() => route.query.task, () => { void openTaskFromQuery() })

onMounted(async () => {
  await Promise.all([loadUsers(), loadTasks()])
  await openTaskFromQuery()
  syncTimer = window.setInterval(() => { void loadTasks(true) }, 15_000)
  document.addEventListener('visibilitychange', onVisibilityChange)
  document.addEventListener('mousedown', onDocumentMouseDown)
})

onBeforeUnmount(() => {
  if (syncTimer) window.clearInterval(syncTimer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  document.removeEventListener('mousedown', onDocumentMouseDown)
})
</script>

<template>
  <section class="calendar-page">
    <div class="calendar-hero">
      <div>
        <p class="calendar-kicker">Командное планирование</p>
        <h2>Календарь и задачи</h2>
        <p class="calendar-subtitle">Планируйте работу, назначайте ответственных и следите за сроками в одном месте.</p>
      </div>
      <button class="calendar-primary-button" type="button" @click="openNewTask()">
        <Plus :size="18" aria-hidden="true" />
        Новая задача
      </button>
    </div>

    <div v-if="error" class="calendar-alert" role="alert">
      <AlertTriangle :size="18" aria-hidden="true" />
      <span>{{ error }}</span>
      <button type="button" aria-label="Скрыть ошибку" @click="error = ''"><X :size="16" /></button>
    </div>

    <div class="calendar-summary-grid">
      <article class="calendar-summary-card">
        <span class="summary-icon violet"><CalendarDays :size="20" /></span>
        <div><strong>{{ summary.today }}</strong><span>Задач сегодня</span></div>
      </article>
      <article class="calendar-summary-card">
        <span class="summary-icon amber"><Clock3 :size="20" /></span>
        <div><strong>{{ summary.inProgress }}</strong><span>В работе</span></div>
      </article>
      <article class="calendar-summary-card">
        <span class="summary-icon red"><AlertTriangle :size="20" /></span>
        <div><strong>{{ summary.overdue }}</strong><span>Просрочено</span></div>
      </article>
      <article class="calendar-summary-card">
        <span class="summary-icon green"><Check :size="20" /></span>
        <div><strong>{{ summary.done }}</strong><span>Выполнено сегодня</span></div>
      </article>
    </div>

    <div class="calendar-toolbar">
      <div class="calendar-month-nav">
        <button type="button" class="calendar-icon-button" aria-label="Предыдущий месяц" @click="changeMonth(-1)"><ChevronLeft :size="19" /></button>
        <button type="button" class="calendar-today-button" @click="goToday">Сегодня</button>
        <button type="button" class="calendar-icon-button" aria-label="Следующий месяц" @click="changeMonth(1)"><ChevronRight :size="19" /></button>
        <h3>{{ monthLabel }}</h3>
      </div>
      <div class="calendar-filters">
        <label class="calendar-toggle">
          <input v-model="mineOnly" type="checkbox" />
          <span>Только мои</span>
        </label>
        <select v-model="assigneeFilter" aria-label="Фильтр по ответственному">
          <option value="">Все ответственные</option>
          <option v-for="user in users" :key="user.user_id" :value="user.user_id">{{ user.username }}</option>
        </select>
        <select v-model="statusFilter" aria-label="Фильтр по статусу">
          <option value="">Все статусы</option>
          <option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <button type="button" class="calendar-refresh" :disabled="loading" @click="loadTasks()">
          <RefreshCw :size="17" :class="{ spinning: loading }" />
        </button>
      </div>
    </div>

    <div class="calendar-workspace">
      <div class="calendar-board">
        <div class="calendar-weekdays">
          <div v-for="label in weekdayLabels" :key="label">{{ label }}</div>
        </div>
        <div class="calendar-grid">
          <div
            v-for="day in calendarDays"
            :key="toDateKey(day)"
            class="calendar-day"
            role="button"
            tabindex="0"
            :class="{
              muted: !isCurrentMonth(day),
              today: isToday(day),
              selected: isSelected(day),
            }"
            @click="chooseDay(day)"
            @dblclick="openNewTask(day)"
            @keydown.enter.prevent="chooseDay(day)"
          >
            <span class="calendar-day-number">{{ day.getDate() }}</span>
            <div class="calendar-day-tasks">
              <button
                v-for="task in tasksForDay(day).slice(0, 3)"
                :key="task.task_id"
                type="button"
                class="calendar-task-chip"
                :class="{ completed: task.status === 'done', overdue: task.status !== 'done' && task.status !== 'cancelled' && new Date(task.due_at).getTime() < Date.now() }"
                :style="{ '--task-color': priorityColor(task) }"
                :title="task.title"
                @click.stop="openTask(task)"
              >
                <span class="task-chip-dot"></span>
                <span v-if="!task.all_day" class="task-chip-time">{{ formatTime(task.start_at) }}</span>
                <span class="task-chip-title">{{ task.title }}</span>
              </button>
              <span v-if="tasksForDay(day).length > 3" class="calendar-more-tasks">+{{ tasksForDay(day).length - 3 }}</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="calendar-agenda">
        <div class="agenda-header">
          <div>
            <p>Выбранный день</p>
            <h3>{{ formatDate(selectedDate) }}</h3>
          </div>
          <button class="calendar-icon-button" type="button" aria-label="Добавить задачу" @click="openNewTask(selectedDate)"><Plus :size="18" /></button>
        </div>

        <div v-if="selectedDayTasks.length" class="agenda-timeline">
          <article v-for="task in selectedDayTasks" :key="task.task_id" class="agenda-item" :class="task.status">
            <div class="agenda-time">
              <span v-if="task.all_day">Весь день</span>
              <template v-else>
                <strong>{{ formatTime(task.start_at) }}</strong>
                <small>{{ formatTime(task.due_at) }}</small>
              </template>
            </div>
            <span class="agenda-line" :style="{ background: priorityColor(task) }"></span>
            <button type="button" class="agenda-task-card" @click="openTask(task)">
              <span class="agenda-task-topline">
                <strong>{{ task.title }}</strong>
                <span class="agenda-priority">{{ priorityLabel(task.priority) }}</span>
              </span>
              <span class="agenda-assignees">
                <UsersRound :size="14" />
                {{ task.assignees.length ? task.assignees.map((user) => user.username).join(', ') : 'Без ответственного' }}
              </span>
              <span class="agenda-status">{{ statusLabel(task.status) }}</span>
            </button>
            <button class="agenda-complete" type="button" :title="task.status === 'done' ? 'Вернуть в план' : 'Отметить выполненной'" @click="quickComplete(task)">
              <Check :size="15" />
            </button>
          </article>
        </div>
        <div v-else class="agenda-empty">
          <ListChecks :size="32" />
          <strong>На этот день задач нет</strong>
          <span>Дважды нажмите на день в календаре или создайте задачу здесь.</span>
          <button type="button" @click="openNewTask(selectedDate)"><Plus :size="16" /> Добавить задачу</button>
        </div>

        <div class="agenda-upcoming">
          <h4>Ближайшие сроки</h4>
          <button v-for="task in upcomingTasks" :key="task.task_id" type="button" class="upcoming-task" @click="openTask(task)">
            <span class="upcoming-dot" :style="{ background: priorityColor(task) }"></span>
            <span><strong>{{ task.title }}</strong><small>{{ formatShortDate(task.due_at) }} · {{ task.all_day ? 'весь день' : formatTime(task.due_at) }}</small></span>
          </button>
          <span v-if="!upcomingTasks.length" class="upcoming-empty">Ближайших задач нет</span>
        </div>
      </aside>
    </div>

    <div v-if="modalOpen" class="task-modal-backdrop" @mousedown.self="closeModal">
      <section class="task-modal" role="dialog" aria-modal="true" :aria-label="editingTask ? 'Редактирование задачи' : 'Новая задача'">
        <header class="task-modal-header">
          <div>
            <p>{{ editingTask ? 'Редактирование' : 'Планирование' }}</p>
            <h3>{{ editingTask ? 'Задача' : 'Новая задача' }}</h3>
          </div>
          <button type="button" class="calendar-icon-button" aria-label="Закрыть" @click="closeModal"><X :size="19" /></button>
        </header>

        <div class="task-modal-body">
          <label class="task-field task-field-wide">
            <span>Название *</span>
            <input v-model="form.title" type="text" maxlength="255" placeholder="Например: согласовать договор с пациентом" />
          </label>
          <label class="task-field task-field-wide">
            <span>Описание</span>
            <textarea v-model="form.description" rows="3" maxlength="5000" placeholder="Контекст, чек-лист, важные детали..."></textarea>
          </label>

          <div class="task-form-grid task-datetime-grid">
            <div class="task-date-card">
              <h4><Clock3 :size="16" /> Начало</h4>
              <div class="task-date-fields">
                <label class="task-mini-field">
                  <span>Дата</span>
                  <input v-model="form.startDate" type="date" />
                </label>
                <label class="task-mini-field">
                  <span>Время</span>
                  <div class="task-time-control">
                    <input
                      :value="form.startTime"
                      type="text"
                      inputmode="numeric"
                      maxlength="5"
                      autocomplete="off"
                      placeholder="09:00"
                      aria-label="Время начала в формате часы и минуты"
                      @input="onTimeInput('start', $event)"
                      @blur="normalizeTimeField('start')"
                      @keydown.down.prevent="toggleTimePicker('start')"
                    />
                    <button type="button" class="task-time-picker-button" aria-label="Выбрать время начала" @click="toggleTimePicker('start')">
                      <Clock3 :size="16" />
                      <ChevronDown :size="14" />
                    </button>
                    <div v-if="openTimePicker === 'start'" class="task-time-popover">
                      <div class="task-time-popover-title">Выберите время <span>24 часа</span></div>
                      <div class="task-time-options">
                        <button
                          v-for="value in timeOptions"
                          :key="`start-${value}`"
                          type="button"
                          :class="{ active: normalizeTimeValue(form.startTime) === value }"
                          @mousedown.prevent
                          @click="setTimeValue('start', value, true)"
                        >{{ value }}</button>
                      </div>
                      <small>Можно также ввести время вручную, например 14:35.</small>
                    </div>
                  </div>
                </label>
              </div>
            </div>
            <div class="task-date-card">
              <h4><CalendarDays :size="16" /> Дедлайн</h4>
              <div class="task-date-fields">
                <label class="task-mini-field">
                  <span>Дата</span>
                  <input v-model="form.dueDate" type="date" />
                </label>
                <label class="task-mini-field">
                  <span>Время</span>
                  <div class="task-time-control">
                    <input
                      :value="form.dueTime"
                      type="text"
                      inputmode="numeric"
                      maxlength="5"
                      autocomplete="off"
                      placeholder="10:00"
                      aria-label="Время дедлайна в формате часы и минуты"
                      @input="onTimeInput('due', $event)"
                      @blur="normalizeTimeField('due')"
                      @keydown.down.prevent="toggleTimePicker('due')"
                    />
                    <button type="button" class="task-time-picker-button" aria-label="Выбрать время дедлайна" @click="toggleTimePicker('due')">
                      <Clock3 :size="16" />
                      <ChevronDown :size="14" />
                    </button>
                    <div v-if="openTimePicker === 'due'" class="task-time-popover task-time-popover-right">
                      <div class="task-time-popover-title">Выберите время <span>24 часа</span></div>
                      <div class="task-time-options">
                        <button
                          v-for="value in timeOptions"
                          :key="`due-${value}`"
                          type="button"
                          :class="{ active: normalizeTimeValue(form.dueTime) === value }"
                          @mousedown.prevent
                          @click="setTimeValue('due', value, true)"
                        >{{ value }}</button>
                      </div>
                      <small>Можно также ввести время вручную, например 18:45.</small>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <label class="task-check-row">
            <input :checked="form.allDay" type="checkbox" @change="onAllDayChange" />
            <span>
              <strong>Задача на весь день</strong>
              <small>В этом режиме часы не учитываются: задача занимает выбранный день целиком. Если выбрать конкретное время, режим отключится.</small>
            </span>
          </label>

          <div class="task-form-grid">
            <label class="task-field">
              <span>Статус</span>
              <select v-model="form.status">
                <option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="task-field">
              <span>Приоритет</span>
              <select v-model="form.priority">
                <option v-for="item in priorityOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>

          <div class="task-field task-field-wide">
            <span>Цвет на календаре</span>
            <div class="task-color-picker">
              <button
                v-for="color in colorOptions"
                :key="color"
                type="button"
                :class="{ active: form.color === color }"
                :style="{ background: color }"
                :aria-label="`Выбрать цвет ${color}`"
                @click="form.color = color"
              ><Check v-if="form.color === color" :size="14" /></button>
            </div>
          </div>

          <div class="task-field task-field-wide">
            <span>Ответственные</span>
            <div class="task-assignees-list">
              <label v-for="user in users" :key="user.user_id" class="task-assignee-option">
                <input v-model="form.assigneeIds" type="checkbox" :value="user.user_id" />
                <span class="task-assignee-avatar"><UserRound :size="15" /></span>
                <span><strong>{{ user.username }}</strong><small>{{ user.role === 'admin' ? 'Администратор' : 'Сотрудник' }}</small></span>
              </label>
            </div>
          </div>
        </div>

        <footer class="task-modal-footer">
          <button v-if="editingTask" type="button" class="task-delete-button" :disabled="saving" @click="requestDeleteTask">
            <Trash2 :size="17" /> Удалить
          </button>
          <span class="task-modal-spacer"></span>
          <button type="button" class="calendar-secondary-button" :disabled="saving" @click="closeModal">Отмена</button>
          <button type="button" class="calendar-primary-button" :disabled="saving" @click="saveTask">
            {{ saving ? 'Сохранение…' : 'Сохранить задачу' }}
          </button>
        </footer>
      </section>

      <div
        v-if="deleteConfirmOpen && deleteCandidate"
        class="task-delete-confirm-backdrop"
        role="presentation"
        @mousedown.self="cancelDeleteTask"
      >
        <section class="task-delete-confirm" role="alertdialog" aria-modal="true" aria-labelledby="task-delete-confirm-title">
          <div class="task-delete-confirm-icon"><AlertTriangle :size="22" /></div>
          <div class="task-delete-confirm-copy">
            <p>Подтвердите удаление</p>
            <h3 id="task-delete-confirm-title">Удалить задачу?</h3>
            <span>«{{ deleteCandidate.title }}» будет удалена без возможности восстановления.</span>
          </div>
          <div class="task-delete-confirm-actions">
            <button type="button" class="calendar-secondary-button" :disabled="saving" @click="cancelDeleteTask">Отмена</button>
            <button type="button" class="task-delete-confirm-button" :disabled="saving" @click="confirmDeleteTask">
              <Trash2 :size="17" /> {{ saving ? 'Удаление…' : 'Удалить' }}
            </button>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.calendar-page { display: grid; gap: 18px; color: var(--text-primary, #e9eef8); }
.calendar-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding: 4px 2px 8px; }
.calendar-kicker { margin: 0 0 6px; color: #a78bfa; text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 800; }
.calendar-hero h2 { margin: 0; font-size: clamp(26px, 3vw, 38px); }
.calendar-subtitle { margin: 8px 0 0; color: #94a3b8; max-width: 720px; }
.calendar-primary-button, .calendar-secondary-button, .task-delete-button, .calendar-today-button { min-height: 42px; border-radius: 12px; border: 1px solid transparent; padding: 0 16px; font-weight: 750; display: inline-flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; }
.calendar-primary-button { background: linear-gradient(135deg, #7c3aed, #8b5cf6); color: white; box-shadow: 0 10px 25px rgba(124, 58, 237, .22); }
.calendar-secondary-button, .calendar-today-button { background: #17263b; border-color: #33445f; color: #d7e0ee; }
.calendar-primary-button:disabled, .calendar-secondary-button:disabled { opacity: .6; cursor: wait; }
.calendar-alert { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border: 1px solid rgba(239,68,68,.45); background: rgba(127,29,29,.2); color: #fecaca; border-radius: 12px; }
.calendar-alert button { margin-left: auto; border: 0; background: transparent; color: inherit; cursor: pointer; }
.calendar-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
.calendar-summary-card { display: flex; align-items: center; gap: 12px; padding: 15px 16px; border: 1px solid #304159; background: linear-gradient(145deg, rgba(30,47,70,.95), rgba(22,36,55,.95)); border-radius: 16px; }
.calendar-summary-card strong { display: block; font-size: 24px; line-height: 1; }
.calendar-summary-card span:last-child { display: block; color: #93a4bd; margin-top: 5px; font-size: 13px; }
.summary-icon { width: 42px; height: 42px; border-radius: 13px; display: grid; place-items: center; }
.summary-icon.violet { color: #c4b5fd; background: rgba(124,58,237,.2); }
.summary-icon.amber { color: #fde68a; background: rgba(245,158,11,.18); }
.summary-icon.red { color: #fca5a5; background: rgba(239,68,68,.16); }
.summary-icon.green { color: #86efac; background: rgba(16,185,129,.17); }
.calendar-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 14px; border: 1px solid #304159; border-radius: 16px; background: #17263b; }
.calendar-month-nav, .calendar-filters { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.calendar-month-nav h3 { margin: 0 0 0 8px; font-size: 18px; min-width: 170px; }
.calendar-icon-button, .calendar-refresh { width: 40px; height: 40px; border: 1px solid #3a4b65; background: #132238; color: #d8e2ef; border-radius: 11px; display: grid; place-items: center; cursor: pointer; }
.calendar-filters select, .task-field select, .task-field input, .task-field textarea, .task-date-card input { border: 1px solid #3a4b65; background: #102035; color: #eef3fa; border-radius: 11px; min-height: 40px; padding: 9px 11px; outline: none; }
.calendar-filters select:focus, .task-field select:focus, .task-field input:focus, .task-field textarea:focus, .task-date-card input:focus { border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,.14); }
.calendar-toggle { display: inline-flex; align-items: center; gap: 7px; color: #cbd5e1; font-size: 14px; }
.calendar-workspace { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(300px, .75fr); gap: 16px; align-items: start; }
.calendar-board, .calendar-agenda { border: 1px solid #304159; background: #15243a; border-radius: 18px; overflow: hidden; }
.calendar-weekdays { display: grid; grid-template-columns: repeat(7,1fr); background: #112036; border-bottom: 1px solid #304159; }
.calendar-weekdays div { padding: 11px 8px; text-align: center; color: #8fa1ba; font-size: 12px; text-transform: uppercase; font-weight: 800; letter-spacing: .08em; }
.calendar-grid { display: grid; grid-template-columns: repeat(7,1fr); }
.calendar-day { position: relative; min-width: 0; min-height: 124px; padding: 9px; border: 0; border-right: 1px solid #293a53; border-bottom: 1px solid #293a53; background: #172840; color: #dce6f3; text-align: left; cursor: pointer; overflow: hidden; }
.calendar-day:nth-child(7n) { border-right: 0; }
.calendar-day:hover { background: #1b304d; }
.calendar-day.muted { background: #142238; color: #64748b; }
.calendar-day.selected { box-shadow: inset 0 0 0 2px rgba(139,92,246,.8); z-index: 1; }
.calendar-day.today .calendar-day-number { background: #8b5cf6; color: white; }
.calendar-day-number { width: 27px; height: 27px; display: grid; place-items: center; border-radius: 9px; font-size: 13px; font-weight: 800; }
.calendar-day-tasks { display: grid; gap: 4px; margin-top: 7px; }
.calendar-task-chip { --task-color: #8b5cf6; width: 100%; min-width: 0; height: 25px; padding: 0 6px; border: 1px solid color-mix(in srgb, var(--task-color) 45%, transparent); border-radius: 7px; background: color-mix(in srgb, var(--task-color) 17%, #13243a); color: #e8edf5; display: flex; align-items: center; gap: 5px; text-align: left; cursor: pointer; font-size: 11px; }
.task-chip-dot { width: 6px; height: 6px; border-radius: 99px; background: var(--task-color); flex: 0 0 auto; }
.task-chip-time { color: #aebbd0; font-variant-numeric: tabular-nums; }
.task-chip-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.calendar-task-chip.completed { opacity: .65; text-decoration: line-through; }
.calendar-task-chip.overdue { box-shadow: inset 2px 0 0 #ef4444; }
.calendar-more-tasks { color: #9aa9bd; font-size: 11px; padding-left: 4px; }
.calendar-agenda { position: sticky; top: 12px; }
.agenda-header { display: flex; align-items: center; justify-content: space-between; padding: 16px; border-bottom: 1px solid #304159; }
.agenda-header p { margin: 0 0 4px; color: #899bb5; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.agenda-header h3 { margin: 0; font-size: 17px; }
.agenda-timeline { display: grid; gap: 2px; padding: 10px 12px; max-height: 500px; overflow: auto; }
.agenda-item { display: grid; grid-template-columns: 58px 3px minmax(0,1fr) 34px; gap: 9px; align-items: stretch; min-height: 78px; }
.agenda-time { display: flex; flex-direction: column; justify-content: center; color: #b6c3d7; font-size: 12px; text-align: right; }
.agenda-time strong { font-size: 13px; }
.agenda-time small { color: #71839d; }
.agenda-line { width: 3px; border-radius: 99px; }
.agenda-task-card { padding: 10px 9px; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; min-width: 0; }
.agenda-task-topline { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.agenda-task-topline strong { overflow-wrap: anywhere; }
.agenda-priority, .agenda-status { color: #9fb0c7; font-size: 11px; }
.agenda-assignees { display: flex; gap: 5px; align-items: center; color: #8ea0b8; font-size: 12px; margin: 7px 0 4px; }
.agenda-complete { align-self: center; width: 30px; height: 30px; border: 1px solid #3b4c65; background: #132239; color: #a9b8cb; border-radius: 9px; cursor: pointer; display: grid; place-items: center; }
.agenda-item.done .agenda-complete { color: #86efac; border-color: rgba(16,185,129,.5); background: rgba(16,185,129,.12); }
.agenda-empty { padding: 36px 20px; display: grid; justify-items: center; gap: 8px; text-align: center; color: #8496ae; }
.agenda-empty strong { color: #dce6f3; }
.agenda-empty button { margin-top: 8px; border: 0; background: transparent; color: #c4b5fd; font-weight: 700; display: inline-flex; gap: 6px; align-items: center; cursor: pointer; }
.agenda-upcoming { border-top: 1px solid #304159; padding: 14px; display: grid; gap: 6px; }
.agenda-upcoming h4 { margin: 0 0 4px; font-size: 13px; color: #b5c2d4; text-transform: uppercase; letter-spacing: .06em; }
.upcoming-task { display: grid; grid-template-columns: 8px minmax(0,1fr); gap: 9px; align-items: center; border: 0; background: transparent; color: #dce6f3; text-align: left; cursor: pointer; padding: 7px 4px; border-radius: 8px; }
.upcoming-task:hover { background: rgba(255,255,255,.035); }
.upcoming-dot { width: 8px; height: 8px; border-radius: 50%; }
.upcoming-task span:last-child { display: grid; gap: 2px; min-width: 0; }
.upcoming-task strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.upcoming-task small, .upcoming-empty { color: #8294ad; font-size: 11px; }
.task-modal-backdrop { position: fixed; inset: 0; z-index: 1200; background: rgba(2,8,23,.78); display: grid; place-items: center; padding: 24px; }
.task-modal { width: min(820px, 100%); max-height: min(900px, calc(100vh - 48px)); overflow: hidden; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; border: 1px solid #40526e; background: #17263b; color: #e7edf6; border-radius: 20px; box-shadow: 0 30px 90px rgba(0,0,0,.45); }
.task-modal-header { z-index: 2; display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; border-bottom: 1px solid #33445d; background: #17263b; }
.task-modal-header p { margin: 0 0 3px; color: #a78bfa; font-size: 11px; text-transform: uppercase; letter-spacing: .09em; font-weight: 800; }
.task-modal-header h3 { margin: 0; font-size: 21px; }
.task-modal-body { min-height: 0; padding: 18px 20px; display: grid; gap: 15px; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.task-field { display: grid; gap: 7px; }
.task-field > span, .task-date-card h4 { color: #aab8ca; font-size: 12px; font-weight: 750; }
.task-field textarea { resize: vertical; min-height: 84px; }
.task-form-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.task-date-card { min-width: 0; border: 1px solid #33455f; background: #132239; border-radius: 13px; padding: 12px; display: grid; gap: 10px; }
.task-date-card h4 { margin: 0; display: flex; gap: 6px; align-items: center; }
.task-date-fields { min-width: 0; display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(154px, .65fr); gap: 9px; align-items: end; }
.task-mini-field { min-width: 0; display: grid; gap: 5px; }
.task-mini-field > span { color: #8293aa; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
.task-date-fields input { width: 100%; min-width: 0; box-sizing: border-box; font-variant-numeric: tabular-nums; }
.task-time-control { position: relative; min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) 58px; }
.task-time-control > input { border-radius: 11px 0 0 11px; border-right: 0; text-align: center; letter-spacing: .03em; }
.task-time-picker-button { min-width: 0; border: 1px solid #3a4b65; background: #172a43; color: #bfcce0; border-radius: 0 11px 11px 0; display: flex; align-items: center; justify-content: center; gap: 2px; cursor: pointer; }
.task-time-picker-button:hover { background: #1c3352; color: #eef3fa; }
.task-time-picker-button:focus-visible { outline: 0; border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,.14); }
.task-time-popover { position: absolute; z-index: 15; top: calc(100% + 7px); right: 0; width: min(340px, calc(100vw - 52px)); padding: 10px; border: 1px solid #465a78; border-radius: 13px; background: #0f1e32; box-shadow: 0 18px 45px rgba(0,0,0,.38); }
.task-time-popover-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; color: #dce6f3; font-size: 12px; font-weight: 800; }
.task-time-popover-title span { color: #8fa1ba; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
.task-time-options { max-height: 228px; overflow-y: auto; overscroll-behavior: contain; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 5px; padding-right: 3px; }
.task-time-options button { min-height: 31px; border: 1px solid #2e415d; border-radius: 8px; background: #152842; color: #cbd7e7; font: inherit; font-size: 11px; font-variant-numeric: tabular-nums; cursor: pointer; }
.task-time-options button:hover { border-color: #6d5bcc; background: #1c3150; color: white; }
.task-time-options button.active { border-color: #8b5cf6; background: rgba(139,92,246,.22); color: #ddd6fe; font-weight: 800; }
.task-time-popover > small { display: block; margin-top: 8px; color: #778aa4; font-size: 10px; line-height: 1.35; }
.task-check-row { display: flex; align-items: flex-start; gap: 10px; color: #c5d0de; font-size: 13px; cursor: pointer; }
.task-check-row > input { margin-top: 3px; flex: 0 0 auto; }
.task-check-row > span { display: grid; gap: 3px; }
.task-check-row strong { color: #dce6f3; font-size: 13px; }
.task-check-row small { color: #8496ad; line-height: 1.35; font-size: 11px; max-width: 680px; }
.task-color-picker { display: flex; gap: 9px; flex-wrap: wrap; }
.task-color-picker button { width: 30px; height: 30px; border: 2px solid transparent; border-radius: 9px; color: white; display: grid; place-items: center; cursor: pointer; }
.task-color-picker button.active { border-color: white; box-shadow: 0 0 0 2px rgba(139,92,246,.6); }
.task-assignees-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; max-height: 220px; overflow: auto; }
.task-assignee-option { display: grid; grid-template-columns: auto 34px minmax(0,1fr); align-items: center; gap: 8px; padding: 9px; border: 1px solid #32445e; border-radius: 11px; background: #132239; cursor: pointer; }
.task-assignee-avatar { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; background: rgba(139,92,246,.18); color: #c4b5fd; }
.task-assignee-option span:last-child { display: grid; gap: 1px; min-width: 0; }
.task-assignee-option strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.task-assignee-option small { color: #8193aa; font-size: 11px; }
.task-modal-footer { display: flex; align-items: center; gap: 9px; padding: 14px 20px; border-top: 1px solid #33445d; background: #17263b; }
.task-modal-spacer { flex: 1; }
.task-delete-button { color: #fca5a5; border-color: rgba(239,68,68,.38); background: rgba(127,29,29,.16); }
.task-delete-confirm-backdrop { position: fixed; inset: 0; z-index: 1400; background: rgba(2,8,23,.68); display: grid; place-items: center; padding: 20px; }
.task-delete-confirm { width: min(470px, 100%); display: grid; grid-template-columns: 46px minmax(0,1fr); gap: 14px; padding: 20px; border: 1px solid rgba(239,68,68,.42); border-radius: 18px; background: #17263b; color: #e7edf6; box-shadow: 0 30px 90px rgba(0,0,0,.58); }
.task-delete-confirm-icon { width: 46px; height: 46px; border-radius: 14px; display: grid; place-items: center; color: #fca5a5; background: rgba(127,29,29,.24); border: 1px solid rgba(239,68,68,.28); }
.task-delete-confirm-copy { min-width: 0; }
.task-delete-confirm-copy p { margin: 0 0 3px; color: #fca5a5; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }
.task-delete-confirm-copy h3 { margin: 0; font-size: 19px; }
.task-delete-confirm-copy span { display: block; margin-top: 7px; color: #aab8ca; line-height: 1.45; overflow-wrap: anywhere; }
.task-delete-confirm-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 9px; margin-top: 4px; }
.task-delete-confirm-button { min-height: 42px; border-radius: 12px; border: 1px solid rgba(239,68,68,.5); padding: 0 16px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; background: #991b1b; color: #fff; font-weight: 800; cursor: pointer; }
.task-delete-confirm-button:hover { background: #b91c1c; }
.task-delete-confirm-button:disabled { opacity: .6; cursor: wait; }
.spinning { animation: calendar-spin .7s linear infinite; }
@keyframes calendar-spin { to { transform: rotate(360deg); } }
@media (max-width: 1100px) { .calendar-workspace { grid-template-columns: 1fr; } .calendar-agenda { position: static; } .calendar-summary-grid { grid-template-columns: repeat(2,1fr); } }
@media (max-width: 760px) { .calendar-hero, .calendar-toolbar { align-items: stretch; flex-direction: column; } .calendar-primary-button { width: 100%; } .calendar-summary-grid { grid-template-columns: 1fr 1fr; } .calendar-board { overflow-x: auto; } .calendar-weekdays, .calendar-grid { min-width: 760px; } .task-form-grid, .task-assignees-list { grid-template-columns: 1fr; } .task-date-fields { grid-template-columns: minmax(0, 1fr) minmax(142px, .7fr); } .task-time-popover { right: 0; width: min(320px, calc(100vw - 32px)); } .task-modal-backdrop { padding: 8px; } .task-modal { max-height: calc(100vh - 16px); border-radius: 16px; } }
@media (max-width: 520px) { .task-date-fields { grid-template-columns: 1fr; } .task-time-control { grid-template-columns: minmax(0, 1fr) 54px; } .task-time-popover { left: 0; right: auto; width: min(300px, calc(100vw - 40px)); } .task-time-options { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
