"""
Проверка заполняемых данных на соответствие заданным шаблонам; осуществляет промежуточный контроль между пользователем,
базой данных и интерфейсом:
- Валидирует входящие запросы (JSON → Python);
- Преобразует данные между форматами (Python-объекты ↔ JSON ↔ БД);
- Документирует API (Swagger/OpenAPI автоматически);
- Служит «границей» между HTTP и внутренним ORM/логикой;
- Упрощает сериализацию SQLAlchemy-объектов в JSON (через orm_mode / from_attributes).
"""

from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime, date

from pydantic import BaseModel, Field, constr, model_validator, ConfigDict

# --- типы с базовой валидацией ---
InnType = constr(pattern=r'^\d{10}(\d{2})?$', strip_whitespace=True)  # 10 или 12 цифр
OgrnipType = constr(pattern=r'^\d{15}$', strip_whitespace=True)         # 15 цифр
BicType = constr(pattern=r'^\d{9}$', strip_whitespace=True)            # 9 цифр
AccountType = constr(min_length=20, max_length=34, pattern=r'^\d+$', strip_whitespace=True)  # 20..34 цифр

# -------------------------
# Agent
# -------------------------
class AgentBase(BaseModel):
    """
    Базовые поля агента. from_attributes=True позволяет Pydantic v2 читать ORM-объекты.
    Поля first_name/middle_name — опционально, чтобы не ломать старые записи.
    """
    model_config = ConfigDict(from_attributes=True)

    last_name: str = Field(..., description="Фамилия")
    first_name: Optional[str] = Field(None, description="Имя")
    middle_name: Optional[str] = Field(None, description="Отчество")
    legal_address: str = Field(..., description="Юридический адрес")
    actual_address: str = Field(..., description="Фактический адрес")
    inn: InnType = Field(..., description="ИНН (10 или 12 цифр)")
    ogrnip: OgrnipType = Field(..., description="ОГРНИП (15 цифр)")
    account_number: AccountType = Field(..., description="Расчётный счёт (20–34 цифр)")
    # ИЗМЕНЕНИЕ: делаем поле необязательным
    correspondent_account: Optional[AccountType] = Field(None, description="Корреспондентский счёт (20–34 цифр)")
    bic: BicType = Field(..., description="БИК (9 цифр)")

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        # Убираем пробелы по краям у всех строковых значений
        for k, v in list(values.items()):
            if isinstance(v, str):
                values[k] = v.strip()
        return values


class AgentCreate(AgentBase):
    """Схема для создания агента."""
    pass


class AgentUpdate(BaseModel):
    """Частичное обновление (PATCH) — все поля опциональны."""
    model_config = ConfigDict(from_attributes=True)

    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    inn: Optional[InnType] = None
    ogrnip: Optional[OgrnipType] = None
    account_number: Optional[AccountType] = None
    correspondent_account: Optional[AccountType] = None
    bic: Optional[BicType] = None

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        for k, v in list(values.items()):
            if isinstance(v, str):
                values[k] = v.strip()
        return values


class AgentRead(AgentBase):
    """Схема для вывода агента из БД (response_model)."""
    agent_id: UUID
    external_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class AgentSummary(BaseModel):
    """Краткая схема агента для вложений (в списках клиентов)."""
    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    external_id: Optional[int] = None
    last_name: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None


# -------------------------
# Phone
# -------------------------
class PhoneCreate(BaseModel):
    number: str = Field(..., min_length=3, max_length=32)


class PhoneRead(BaseModel):
    phone_id: int
    client_id: UUID
    number: str
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Client
# -------------------------
class ClientBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    last_name: str = Field(..., description="Фамилия")
    first_name: str = Field(..., description="Имя")
    middle_name: Optional[str] = Field(None, description="Отчество")
    status_code: str = Field(..., description="Статус работы (code)")
    current_stage: str = Field(..., description="Этап работы (code)")
    agent_id: UUID = Field(..., description="ID агента (UUID)")
    deadline: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        for k, v in list(values.items()):
            if isinstance(v, str):
                values[k] = v.strip()
        return values


class ClientCreate(ClientBase):
    phones: Optional[List[PhoneCreate]] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    status_code: Optional[str] = None
    current_stage: Optional[str] = None
    agent_id: Optional[UUID] = None
    deadline: Optional[datetime] = None
    notes: Optional[str] = None
    phones: Optional[List[PhoneCreate]] = None

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        for k, v in list(values.items()):
            if isinstance(v, str):
                values[k] = v.strip()
        return values


# Вложенные (summary) схемы для status/stage (в ClientRead)
class StatusSummary(BaseModel):
    status_code: str
    description: str
    model_config = ConfigDict(from_attributes=True)


class StageSummary(BaseModel):
    stage_code: str
    description: str
    model_config = ConfigDict(from_attributes=True)


class ClientRead(ClientBase):
    client_id: UUID
    external_id: Optional[int] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    # Вложенные сущности (summary/details)
    agent: Optional[AgentSummary] = None
    status: Optional[StatusSummary] = None
    stage: Optional[StageSummary] = None
    phones: Optional[List[PhoneRead]] = Field(default_factory=list)

    # Дополнительные вложенные списки (SNILS, Passports)
    snils: Optional[List["SnilsRead"]] = Field(default_factory=list)
    passports: Optional[List["PassportRead"]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Status / Stage / DocumentType
# -------------------------
class StatusCreate(BaseModel):
    status_code: str
    description: str


class StatusRead(StatusCreate):
    model_config = ConfigDict(from_attributes=True)


class StageCreate(BaseModel):
    stage_code: str
    description: str


class StageRead(BaseModel):
    stage_code: str
    description: str
    model_config = ConfigDict(from_attributes=True)


class DocumentTypeCreate(BaseModel):
    type_code: str
    title: str


class DocumentTypeRead(DocumentTypeCreate):
    model_config = ConfigDict(from_attributes=True)


# app/schemas.py

# ... (остальной код файла без изменений) ...

# -------------------------
# Passport
# -------------------------
class PassportBase(BaseModel):
    full_name: str
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    birth_date: Optional[date] = None # <-- ДОБАВЛЕНО
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    birth_place: str
    series_number: str
    issued_by: str
    issue_date: date
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    department_code: Optional[str] = None # <-- ДОБАВЛЕНО
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    expiry_date: Optional[date] = None
    registration_address: str


class PassportCreate(PassportBase):
    pass

# НОВАЯ СХЕМА
class PassportUpdate(BaseModel):
    full_name: Optional[str] = None
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    birth_date: Optional[date] = None # <-- ДОБАВЛЕНО
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    birth_place: Optional[str] = None
    series_number: Optional[str] = None
    issued_by: Optional[str] = None
    issue_date: Optional[date] = None
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    department_code: Optional[str] = None # <-- ДОБАВЛЕНО
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    expiry_date: Optional[date] = None
    registration_address: Optional[str] = None

# ... (остальной код файла без изменений) ...


class PassportRead(PassportBase):
    passport_id: UUID
    client_id: UUID
    version: int
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# SNILS
# -------------------------
class SnilsBase(BaseModel):
    number: str
    issued_date: Optional[date] = None


class SnilsCreate(SnilsBase):
    pass

# НОВАЯ СХЕМА
class SnilsUpdate(BaseModel):
    number: Optional[str] = None
    issued_date: Optional[date] = None


class SnilsRead(SnilsBase):
    snils_id: UUID
    client_id: UUID
    version: int
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Document (метаданные для S3/MinIO)
# -------------------------
class DocumentBase(BaseModel):
    type_code: str
    filename: str
    object_key: str
    version: Optional[int] = Field(1)


class DocumentCreate(DocumentBase):
    client_id: UUID


class DocumentRead(DocumentBase):
    document_id: UUID
    client_id: UUID
    uploaded_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Reminder
# -------------------------
class ReminderBase(BaseModel):
    service_stage: str
    remind_at: datetime


class ReminderCreate(ReminderBase):
    client_id: UUID


class ReminderRead(ReminderBase):
    reminder_id: UUID
    client_id: UUID
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# AuditLog
# -------------------------
class AuditLogBase(BaseModel):
    entity: str
    entity_id: UUID
    action: str
    user_id: str
    details: Optional[Dict[str, Any]] = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    log_id: UUID
    timestamp: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# Разрешаем forward references (PassportRead / SnilsRead использованы в ClientRead)
ClientRead.model_rebuild() # ИЗМЕНЕНИЕ: update_forward_refs() устарел в Pydantic v2