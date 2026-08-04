import type { AuditLogItem } from '@/shared/types/entities'

const ACTION_LABELS: Record<string, string> = {
  create: 'Создание',
  update: 'Обновление',
  delete: 'Удаление',
  'phone.create': 'Добавлен телефон',
  'phone.update': 'Изменён телефон',
  'phone.delete': 'Удалён телефон',
  'passport.create': 'Добавлен паспорт',
  'passport.update': 'Изменён паспорт',
  'passport.delete': 'Удалён паспорт',
  'snils.create': 'Добавлен СНИЛС',
  'snils.update': 'Изменён СНИЛС',
  'snils.delete': 'Удалён СНИЛС',
  'document.upload': 'Загружен документ',
  'document.delete': 'Удалён документ',
  'document.generate_contract': 'Сформирован договор',
  'accounting.custom_values.update': 'Изменены бухгалтерские поля',
  'accounting.contract.update': 'Изменены расходы по договору',
  'settings.update': 'Изменены настройки',
  archive: 'Клиент перемещён в архив',
  restore: 'Клиент восстановлен из архива',
  'component.archive': 'Комплектующая перемещена в архив',
  'component.restore': 'Комплектующая восстановлена из архива',
  'components.tsr.assign': 'Назначен ТСР комплектующим',
  'prosthesis.upsert': 'Добавлен вид протеза',
  'prosthesis.update': 'Изменён вид протеза',
  'prosthesis.delete': 'Удалён вид протеза',
  'tsr.upsert': 'Добавлен код ТСР',
  'tsr.update': 'Изменён код ТСР',
  'tsr.delete': 'Удалён код ТСР',
  'tsr.attach': 'ТСР добавлен клиенту',
  'tsr.detach': 'ТСР удалён у клиента',
  'client_tsr.create': 'Добавлен клиенту',
  'client_tsr.update': 'Изменены данные',
  'client_tsr.delete': 'Удалён у клиента',
  'name_index.upsert': 'Добавлено название комплектующей',
  'name_index.delete': 'Удалено название комплектующей',
  'status.create': 'Добавлен статус',
  'stage.create': 'Добавлен этап',
}

const FIELD_LABELS: Record<string, string> = {
  username: 'Логин',
  role: 'Роль',
  is_active: 'Активность',
  last_name: 'Фамилия',
  first_name: 'Имя',
  middle_name: 'Отчество',
  status_code: 'Статус',
  current_stage: 'Этап',
  agent_id: 'Агент',
  client_id: 'Клиент',
  tsr_id: 'ТСР',
  deadline: 'Повторное обращение',
  repeat_visit_date: 'Повторное обращение по ТСР',
  check_date: 'Дата пробития',
  certificate_price: 'Стоимость сертификата',
  taxation_system: 'Налогообложение',
  prosthesis_type: 'Диагноз',
  tsr_code: 'ТСР',
  prosthetist_salary: 'ЗП протезиста',
  agent_salary: 'ЗП агента',
  support_salary: 'ЗП поддержки',
  prosthetist_work: 'Работа протезиста',
  patient_travel: 'Проезд пациента',
  patient_accommodation: 'Проживание пациента',
  patient_meals: 'Питание пациента',
  patient_payment: 'Пациенту',
  other_expenses: 'Прочее',
  agency_expenses: 'Агентские',
  place_of_residence: 'Адрес протезиста',
  prosthetist: 'Протезист',
  is_archived: 'В архиве',
  ipra_code: 'Номер ИПРА',
  notes: 'Заметки',
  legal_address: 'Юридический адрес',
  actual_address: 'Фактический адрес',
  inn: 'ИНН',
  ogrnip: 'ОГРНИП',
  account_number: 'Расчетный счет',
  correspondent_account: 'Корреспондентский счет',
  bic: 'БИК',
  module_name_index: 'Индекс / название',
  supplier: 'Поставщик',
  quantity: 'Количество',
  cost: 'Себестоимость',
  price: 'Цена',
  ordered: 'Заказано',
  recd: 'Получено',
  pending: 'Ожидается',
  prosthetist_keep: 'У протезиста',
  properties: 'Характеристики',
  order_date_acc_num: 'Номер счёта и дата',
  size: 'Размер',
  stiffness: 'Жёсткость',
  side: 'Сторона',
  number: 'Номер',
  full_name: 'ФИО',
  birth_date: 'Дата рождения',
  birth_place: 'Место рождения',
  series_number: 'Серия и номер',
  issued_by: 'Кем выдан',
  issue_date: 'Дата выдачи',
  department_code: 'Код подразделения',
  registration_address: 'Адрес регистрации',
  filename: 'Файл',
  document_number: 'Номер договора',
  field_name: 'Название поля',
  field_type: 'Тип поля',
  tax_percent: 'Налог при ставке 6%, %',
  tax_usn_percent: 'Налог при ставке 6%, %',
  tax_osno_percent: 'Налог при ставке 12%, %',
  acq_percent: 'Эквайринг, %',
  custom_values: 'Дополнительные поля',
}

const IGNORED_FIELDS = new Set([
  'updated_at',
  'created_at',
  'password_hash',
  'user_id',
  'module_id',
  'component_id',
  'phone_id',
  'passport_id',
  'snils_id',
  'document_id',
  'field_id',
  'value_id',
  'accounting_id',
  'client_tsr_id',
  'log_id',
  'modules',
  'phones',
  'passports',
  'snils',
  'documents',
  'accounting_values',
  'agent',
  'status',
  'stage',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  if (typeof value === 'boolean') {
    return value ? 'да' : 'нет'
  }

  if (typeof value === 'number') {
    return String(value)
  }

  if (typeof value === 'string') {
    return value.length > 80 ? `${value.slice(0, 80)}…` : value
  }

  if (Array.isArray(value)) {
    const labels = value
      .filter((item): item is string | number => typeof item === 'string' || typeof item === 'number')
      .map(String)
    if (labels.length > 0) {
      const preview = labels.slice(0, 4).join(', ')
      return labels.length > 4 ? `${preview} и ещё ${labels.length - 4}` : preview
    }
  }

  if (isRecord(value)) {
    const entries: string[] = Object.entries(value)
      .filter(([key]) => !IGNORED_FIELDS.has(key))
      .slice(0, 3)
      .map(([key, nested]) => `${FIELD_LABELS[key] ?? key}: ${stringifyValue(nested)}`)
    return entries.length > 0 ? entries.join(', ') : '—'
  }

  return String(value)
}

function getChangedFields(before: Record<string, unknown>, after: Record<string, unknown>) {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)])
  const changes: string[] = []

  keys.forEach((key) => {
    if (IGNORED_FIELDS.has(key)) {
      return
    }

    const beforeValue = before[key]
    const afterValue = after[key]

    if (JSON.stringify(beforeValue ?? null) === JSON.stringify(afterValue ?? null)) {
      return
    }

    const label = FIELD_LABELS[key] ?? key
    changes.push(`${label}: ${stringifyValue(beforeValue)} → ${stringifyValue(afterValue)}`)
  })

  return changes
}

function getSnapshotFields(value: Record<string, unknown>) {
  return Object.entries(value)
    .filter(([key, fieldValue]) => !IGNORED_FIELDS.has(key) && fieldValue !== null && fieldValue !== '')
    .map(([key, fieldValue]) => `${FIELD_LABELS[key] ?? key}: ${stringifyValue(fieldValue)}`)
}

function getSubject(item: AuditLogItem) {
  const details = isRecord(item.details) ? item.details : {}
  const label = typeof details.subject_label === 'string' ? details.subject_label : 'Запись'
  const name = typeof details.subject_name === 'string' ? details.subject_name : ''
  return { label, name }
}

function withSubject(action: string, item: AuditLogItem) {
  const { label, name } = getSubject(item)
  if (!name) {
    return action
  }
  const visibleLabel = label === 'ТСР' ? label : label.toLowerCase()
  return `${action}: ${visibleLabel} «${name}»`
}

export function formatAuditAction(item: AuditLogItem) {
  const clientTsrLabels: Record<string, string> = {
    'tsr.attach': 'ТСР добавлен клиенту',
    'tsr.update': 'Изменены данные ТСР клиента',
    'tsr.detach': 'ТСР удалён у клиента',
  }
  const action = item.entity === 'client' && clientTsrLabels[item.action]
    ? clientTsrLabels[item.action]
    : ACTION_LABELS[item.action] ?? item.action ?? 'Изменение'
  return withSubject(action, item)
}

export function formatAuditEntity(item: AuditLogItem) {
  const { label, name } = getSubject(item)
  return name ? `${label} «${name}»` : label
}

export function formatAuditActor(item: AuditLogItem) {
  const details = isRecord(item.details) ? item.details : {}
  const username = typeof details.actor_username === 'string' ? details.actor_username : ''
  const role = typeof details.actor_role === 'string' ? details.actor_role : ''

  if (username && role) {
    return `${username} · ${role}`
  }

  return username || item.user_id || 'system'
}

export function formatAuditTime(value?: string | null) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

export function summarizeAuditDetails(item: AuditLogItem) {
  const details = isRecord(item.details) ? item.details : {}
  const before = isRecord(details.before) ? details.before : null
  const after = isRecord(details.after) ? details.after : null
  const relatedComponents = Array.isArray(details.related_components)
    ? details.related_components.filter((value): value is string => typeof value === 'string')
    : []

  if (item.action === 'archive') {
    const suffix = relatedComponents.length
      ? ` Комплектующие: ${stringifyValue(relatedComponents)}.`
      : ''
    return `Карточка клиента и связанные комплектующие перемещены в архив.${suffix}`
  }

  if (item.action === 'restore') {
    const suffix = relatedComponents.length
      ? ` Комплектующие: ${stringifyValue(relatedComponents)}.`
      : ''
    return `Карточка клиента восстановлена; вручную архивированные позиции остались в архиве.${suffix}`
  }

  if (item.action === 'component.archive') {
    return 'Комплектующая скрыта из рабочего склада и помещена в архив.'
  }

  if (item.action === 'component.restore') {
    return 'Комплектующая возвращена из архива на рабочий склад.'
  }

  if (item.action === 'components.tsr.assign') {
    const tsr = stringifyValue(details.tsr_id)
    const components = stringifyValue(details.component_ids)
    return `ТСР «${tsr}» назначен комплектующим: ${components}.`
  }

  if (before && after) {
    const changes = getChangedFields(before, after)
    if (changes.length > 0) {
      const preview = changes.slice(0, 5).join('; ')
      const changeSummary = changes.length > 5 ? `${preview}; ещё изменений: ${changes.length - 5}` : preview
      const passwordSummary = details.password_changed === true
        ? `${changeSummary}; пароль изменён`
        : changeSummary
      return item.action === 'accounting.contract.update' && typeof details.document_name === 'string'
        ? `Договор «${details.document_name}»: ${passwordSummary}`
        : passwordSummary
    }
    if (details.password_changed === true) {
      return 'Пароль учетной записи изменён.'
    }
  }

  if (after && !before) {
    const values = getSnapshotFields(after)
    return values.length > 0 ? values.slice(0, 4).join('; ') : 'Запись создана.'
  }

  if (before && !after) {
    const values = getSnapshotFields(before)
    return values.length > 0 ? values.slice(0, 4).join('; ') : 'Запись удалена.'
  }

  if (typeof details.template_type === 'string') {
    const documentNumber = typeof details.document_number === 'string' ? details.document_number : ''
    return documentNumber
      ? `Договор № ${documentNumber}; шаблон: ${details.template_type}.`
      : `Шаблон: ${details.template_type}.`
  }

  return 'Действие выполнено без изменения отображаемых полей.'
}
