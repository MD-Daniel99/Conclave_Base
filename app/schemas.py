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

from typing import Optional, List, Any, Dict, Literal
from uuid import UUID
from datetime import datetime, date

from pydantic import AliasChoices, BaseModel, Field, constr, model_validator, ConfigDict

# --- типы с базовой валидацией ---
InnType = constr(pattern=r'^\d{10}(\d{2})?$', strip_whitespace=True)  # 10 или 12 цифр
OgrnipType = constr(pattern=r'^\d{15}$', strip_whitespace=True)         # 15 цифр
BicType = constr(pattern=r'^\d{9}$', strip_whitespace=True)            # 9 цифр
AccountType = constr(min_length=20, max_length=34, pattern=r'^\d+$', strip_whitespace=True)  # 20..34 цифр

TaxationSystem = Literal["УСН", "ОСНО"]
Prosthetists = Literal["Дмитрий", "Никита"]
PlacesOfResidence = Literal["Ивана Сусанина, д. 3", "Большая Почтовая, д. 18/20"]
PROSTHETIST_ADDRESSES = {
    "Дмитрий": "Ивана Сусанина, д. 3",
    "Никита": "Большая Почтовая, д. 18/20",
}


class ClientSummary(BaseModel):
    client_id: UUID
    first_name: str
    last_name: str
    model_config = ConfigDict(from_attributes=True)


class TsrSummary(BaseModel):
    # ORM objects expose ``tsr_id``; the client serializer may pass the already
    # normalized ``id`` key through a second validation step.
    id: UUID = Field(validation_alias=AliasChoices("tsr_id", "id"))
    full_tsr_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ClientTsrBase(BaseModel):
    tsr_id: UUID
    check_date: Optional[date] = None
    certificate_price: Optional[str] = None
    prosthetist: Prosthetists | None = None
    repeat_visit_date: Optional[date] = None


class ClientTsrCreate(ClientTsrBase):
    pass


class ClientTsrUpdate(BaseModel):
    check_date: Optional[date] = None
    certificate_price: Optional[str] = None
    prosthetist: Prosthetists | None = None
    repeat_visit_date: Optional[date] = None


class ClientTsrRead(ClientTsrBase):
    client_tsr_id: UUID
    client_id: UUID
    place_of_residence: Optional[str] = None
    tsr: TsrSummary
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# -------------------------
# Module
# -------------------------
class ModuleBase(BaseModel):
    tsr_id: Optional[UUID] = None
    client_tsr_id: Optional[UUID] = None
    module_name_index: Optional[str] = None
    supplier: str
    ordered: int = Field(default=0, ge=0)
    order_date_acc_num: str
    size: Optional[str] = None
    stiffness: Optional[str] = None
    side: Optional[str] = None
    quantity: int = 0
    cost: float = 0.0
    price: float = 0.0
    recd: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    prosthetist_keep: int = Field(default=0, ge=0)
    properties: str
    notes: Optional[str] = None

class ModuleCreate(ModuleBase):
    # Разрешаем None, чтобы комплектующая могла находиться на складе.
    client_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _require_tsr(self):
        if self.tsr_id is None:
            raise ValueError("Для комплектующей необходимо выбрать ТСР.")
        return self
    

class ModuleUpdate(BaseModel):
    # Все поля опциональны для PATCH-запросов
    client_id: Optional[UUID] = None # Разрешаем перепривязку комплектующей
    tsr_id: Optional[UUID] = None
    client_tsr_id: Optional[UUID] = None
    module_name_index: Optional[str] = None
    supplier: Optional[str] = None
    ordered: Optional[int] = Field(default=None, ge=0)
    order_date_acc_num: Optional[str] = None
    size: Optional[str] = None
    stiffness: Optional[str] = None
    side: Optional[str] = None
    quantity: Optional[int] = None
    cost: Optional[float] = None
    price: Optional[float] = None
    recd: Optional[int] = Field(default=None, ge=0)
    pending: Optional[int] = Field(default=None, ge=0)
    prosthetist_keep: Optional[int] = Field(default=None, ge=0)
    properties: Optional[str] = None
    notes: Optional[str] = None

class ModuleRead(ModuleBase):
    module_id: UUID
    client_id: Optional[UUID] = None 
    client: Optional[ClientSummary] = None # информация о клиенте-владельце 
    tsr: Optional[TsrSummary] = None
    is_archived: bool = False
    is_manually_archived: bool = False
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

    last_name: Optional[str] = Field(None, description="Фамилия")
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
        for k, v in list(values.items()):
            if isinstance(v, str):
                v = v.strip()
                # ЕСЛИ СТРОКА ПУСТАЯ -> ПРЕВРАЩАЕМ В NONE
                if v == "":
                    values[k] = None
                else:
                    values[k] = v
        return values


class AgentCreate(AgentBase):
    """Схема создания: обязательно только непустое имя."""

    first_name: str = Field(..., min_length=1, max_length=128, description="Имя")


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
                v = v.strip()
                # ЕСЛИ СТРОКА ПУСТАЯ -> ПРЕВРАЩАЕМ В NONE
                if v == "":
                    values[k] = None
                else:
                    values[k] = v
        if "first_name" in values and values.get("first_name") is None:
            raise ValueError("Имя агента обязательно")
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
    last_name: Optional[str] = None
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
    ipra_code: Optional[str] = None
    certificate_price: Optional[str] = None
    taxation_system: TaxationSystem = "УСН"
    place_of_residence: PlacesOfResidence | None = None
    prosthetist: Prosthetists | None = None
    tsr_code: Optional[str] = None
    email: Optional[str] = None

    prosthetist_salary: Optional[float] = 0.0
    agent_salary: Optional[float] = 0.0
    support_salary: Optional[float] = 0.0
    prosthetist_work: float = 0.0
    patient_travel: float = 0.0
    patient_accommodation: float = 0.0
    patient_meals: float = 0.0
    patient_payment: float = 0.0
    other_expenses: float = 0.0
    agency_expenses: float = 0.0

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        for k, v in list(values.items()):
            if isinstance(v, str):
                v = v.strip()
                # ЕСЛИ СТРОКА ПУСТАЯ -> ПРЕВРАЩАЕМ В NONE
                if v == "":
                    values[k] = None
                else:
                    values[k] = v
        prosthetist = values.get("prosthetist")
        if prosthetist in PROSTHETIST_ADDRESSES:
            values["place_of_residence"] = PROSTHETIST_ADDRESSES[prosthetist]
        elif prosthetist is None:
            values["place_of_residence"] = None
        return values


class ClientCreate(ClientBase):
    # Протезист теперь назначается отдельно для каждого ТСР клиента.
    prosthetist: Optional[Prosthetists] = None
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
    ipra_code: Optional[str] = None
    certificate_price: Optional[str] = None
    taxation_system: Optional[TaxationSystem] = None
    place_of_residence: PlacesOfResidence | None = None
    prosthetist: Optional[Prosthetists] = None
    tsr_code: Optional[str] = None
    email: Optional[str] = None

    prosthetist_salary: Optional[float] = None
    agent_salary: Optional[float] = None
    support_salary: Optional[float] = None
    prosthetist_work: Optional[float] = None
    patient_travel: Optional[float] = None
    patient_accommodation: Optional[float] = None
    patient_meals: Optional[float] = None
    patient_payment: Optional[float] = None
    other_expenses: Optional[float] = None
    agency_expenses: Optional[float] = None

    @model_validator(mode="before")
    def _strip_strings(cls, values: dict) -> dict:
        for k, v in list(values.items()):
            if isinstance(v, str):
                v = v.strip()
                # ЕСЛИ СТРОКА ПУСТАЯ -> ПРЕВРАЩАЕМ В NONE
                if v == "":
                    values[k] = None
                else:
                    values[k] = v
        prosthetist = values.get("prosthetist")
        if prosthetist in PROSTHETIST_ADDRESSES:
            values["place_of_residence"] = PROSTHETIST_ADDRESSES[prosthetist]
        elif "prosthetist" in values and prosthetist is None:
            values["place_of_residence"] = None
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
    is_archived: bool = False
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
    tsr_items: Optional[List[ClientTsrRead]] = Field(default_factory=list)

    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
    

class ClientComponentsTsrUpdate(BaseModel):
    component_ids: List[UUID] = Field(..., min_length=1)
    tsr_id: UUID


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
    settings: Optional[Dict[str, Any]] = None

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    user_id: UUID 

class UserSettingsUpdate(BaseModel):
    # Старый ключ остаётся совместимым с уже собранным frontend.
    tax_percent: Optional[float] = None
    tax_usn_percent: Optional[float] = Field(default=None, ge=0)
    tax_osno_percent: Optional[float] = Field(default=None, ge=0)
    acq_percent: Optional[float] = None
    vat_percent: Optional[float] = Field(default=None, ge=0)

# Documents storage
class DocumentRead(BaseModel):
    document_id: UUID
    client_id: UUID
    filename: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    created_at: datetime
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    contract_total: Optional[float] = None
    certificate_amount: Optional[float] = None
    certificate_id: Optional[UUID] = None
    contract_metadata: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)

class DocumentType:
    LLC_CONTRACT = "llc_contract"
    DMK_CONTRACT = "dmk_contract"
    DMK_INSTRUMENT = "dmk_instrument"


class ContractGeneration(BaseModel):
    template_type: str = DocumentType.LLC_CONTRACT
    document_number: Optional[str] = None
    document_date: str
    plan_date: Optional[str] = None
    document_number_prefix: Optional[str] = None
    document_number_suffix: Optional[str] = None
    appendix_number: Optional[str] = None
    appendix_date: Optional[str] = None
    selected_client_tsr_ids: List[UUID] = Field(default_factory=list)
    selected_tsr_ids: List[UUID] = Field(default_factory=list)
    selected_module_ids: List[UUID] = Field(default_factory=list)


class ContractAccountingUpdate(BaseModel):
    prosthetist_work: Optional[float] = None
    patient_travel: Optional[float] = None
    patient_accommodation: Optional[float] = None
    patient_meals: Optional[float] = None
    patient_payment: Optional[float] = None
    other_expenses: Optional[float] = None
    agency_expenses: Optional[float] = None
    custom_values: Optional[Dict[str, Any]] = None

# References

class ProsthesisRefCreate(BaseModel):
    name: str

class ProsthesisRefUpdate(BaseModel):
    name: str

class ProsthesisRefRead(BaseModel):
    id: UUID = Field(validation_alias = "prosthesis_id")
    name: str
    model_config = ConfigDict(from_attributes = True)

class TstCodeRefCreate(BaseModel):
    full_tsr_code: str

class TstCodeRefUpdate(BaseModel):
    full_tsr_code: str

class TstCodeRefRead(BaseModel):
    id: UUID = Field(validation_alias=AliasChoices("tsr_id", "id"))
    full_tsr_code: Optional[str]
    model_config = ConfigDict(from_attributes = True)


# -------------------------
# ModuleNameIndex
# -------------------------
class ModuleNameIndexCreate(BaseModel):
    name_index: str

class ModuleNameIndexRead(BaseModel):
    id: UUID = Field(validation_alias="name_index_id")
    name_index: Optional[str]
    model_config = ConfigDict(from_attributes=True)

# -------------------------
# Accounting Custom Fields
# -------------------------
class AccountingCustomFieldBase(BaseModel):
    field_name: str
    field_type: str  # 'number' или 'text'

class AccountingCustomFieldCreate(AccountingCustomFieldBase):
    pass

class AccountingCustomFieldRead(AccountingCustomFieldBase):
    field_id: UUID
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AccountingFieldValueUpdate(BaseModel):
    """Для обновления значений кастомных полей клиента"""
    field_id: UUID
    value: Optional[str | float] = None  # строка для text, число для number

class AccountingValuesUpdate(BaseModel):
    """Тело запроса на обновление нескольких значений"""
    values: List[AccountingFieldValueUpdate]


DocumentRead.model_rebuild()

ClientRead.model_rebuild() 
UserRead.model_rebuild()
