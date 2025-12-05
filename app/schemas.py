# Слой модели данных - структура и валидация
# Описывают DTO (Data Transfer Objects) - объекты для передачи данных между слоями приложения
# Для ввода (ModuleCreate) - валидация входящих данных
# Для вывода (ModuleRead) - контроль того, что возвращается клиенту
# Для внутренней передачи - между API, CRUD и сервисными слоями
"""
Проверка заполняемых данных на соответствие заданным шаблонам; осуществляет промежуточный контроль между пользователем,
базой данных и интерфейсом:
- Валидирует/парсит входящие запросы (JSON → Python), из JSON-словарей в объекты Python;
- Преобразует данные между форматами (Python-объекты ↔ JSON ↔ БД);
- Документирует API (Swagger/OpenAPI автоматически);
- Служит «границей» между HTTP и внутренним ORM/логикой;
- Упрощает сериализацию SQLAlchemy-объектов из Python в JSON (через orm_mode / from_attributes).
Поддерживает значения полей по умолчанию.
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



class ClientSummary(BaseModel):
    client_id: UUID
    first_name: str
    last_name: str
    model_config = ConfigDict(from_attributes=True)

# -------------------------
# Module
# -------------------------
class ModuleBase(BaseModel):
    module_name: str
    catalogue_index: str
    supplier: str
    ordered: str
    order_date_acc_num: str
    quantity: int = 0
    cost: float = 0.0
    price: float = 0.0
    recd: str
    pending: str
    properties: str
    notes: Optional[str] = None

class ModuleCreate(ModuleBase):
    # Разрешаем None, чтобы модуль мог быть "ничьим"
    client_id: Optional[UUID] = None
    

class ModuleUpdate(BaseModel):
    # Все поля опциональны для PATCH-запросов
    client_id: Optional[UUID] = None # Разрешаем перепривязку модуля
    module_name: Optional[str] = None
    catalogue_index: Optional[str] = None
    supplier: Optional[str] = None
    ordered: Optional[str] = None
    order_date_acc_num: Optional[str] = None
    cost: Optional[float] = None
    price: Optional[float] = None
    recd: Optional[str] = None
    pending: Optional[str] = None
    properties: Optional[str] = None
    notes: Optional[str] = None

class ModuleRead(ModuleBase):
    module_id: UUID
    client_id: Optional[UUID] = None 
    client: Optional[ClientSummary] = None # информация о клиенте-владельце 
    #module_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    legal_address: Optional[str] = Field(None, description="Юридический адрес")
    actual_address: Optional[str] = Field(None, description="Фактический адрес")
    inn: Optional[InnType] = Field(None, description="ИНН (10 или 12 цифр)")
    ogrnip: Optional[OgrnipType] = Field(None, description="ОГРНИП (15 цифр)")
    account_number: Optional[AccountType] = Field(None, description="Расчётный счёт (20–34 цифр)")
    # ИЗМЕНЕНИЕ: делаем поле необязательным
    correspondent_account: Optional[AccountType] = Field(None, description="Корреспондентский счёт (20–34 цифр)")
    bic: Optional[BicType] = Field(None, description="БИК (9 цифр)")

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

class PhoneUpdate(BaseModel):
    number: Optional[str] = None

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
    check_date: Optional[date] = None
    prosthesis_type: Optional[str] = None
    certificate_price: Optional[float] = None

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
    check_date: Optional[date] = None
    prosthesis_type: Optional[str] = None
    certificate_price: Optional[float] = None

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

    # Дополнительные вложенные списки
    snils: Optional[List["SnilsRead"]] = Field(default_factory = list)
    passports: Optional[List["PassportRead"]] = Field(default_factory = list)

    modules: Optional[List["ModuleRead"]] = Field(default_factory = list)

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

# -------------------------
# Passport
# -------------------------
class PassportBase(BaseModel):
    full_name: str
    
    birth_date: Optional[date] = None 
    
    birth_place: str
    series_number: str
    issued_by: str
    issue_date: date
    
    department_code: Optional[str] = None 
    
    expiry_date: Optional[date] = None
    registration_address: str


class PassportCreate(PassportBase):
    pass


class PassportUpdate(BaseModel):
    full_name: Optional[str] = None
    
    birth_date: Optional[date] = None 
    
    birth_place: Optional[str] = None
    series_number: Optional[str] = None
    issued_by: Optional[str] = None
    issue_date: Optional[date] = None
    
    department_code: Optional[str] = None 

    
    expiry_date: Optional[date] = None
    registration_address: Optional[str] = None

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


# -------------------------
# Auth / Users
# -------------------------
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: str = "user"

class UserUpdate(BaseModel):
    username: Optional[str] = None 
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None 

class UserRead(UserBase):
    user_id: UUID
    role: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    user_id: UUID 

# Documents storage
class DocumentRead(BaseModel):
    document_id: UUID
    client_id: UUID
    filename: str
    content_type: str
    size: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

DocumentRead.model_rebuild()

ClientRead.model_rebuild() 
UserRead.model_rebuild()

