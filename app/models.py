# Модели БД (models.py) - отображение на таблицы БД
"""
    Описание ORM-моделей и метаданных схемы:
     Уровни работы с БД:
        -Core (Expression Language): гибкий конструктор SQL-запросов на Python-коде.
        -ORM: над Core надстраивается слой, который позволяет описывать таблицы как Python-классы 
    (модели), а строки — как объекты этих классов. 
    -CRUD-операции при этом превращаются в методы над объектами и сессией.
     Основные компоненты: 
        -Engine: точка входа — управляет пулом соединений и генерирует SQL.
        -Metadata / Declarative Base: хранит описание таблиц и связей; с помощью декларативного стиля создаются модели как классы, 
        наследующиеся от Base.
        -Session: объект для работы в транзакциях. Сессия кэширует изменения объектов и при commit() превращает их в 
        INSERT/UPDATE/DELETE запросы.
     -Миграции через Alembic: тесная интеграция позволяет автогенерировать изменения схемы.
"""

from sqlalchemy import (
    Column, String, Text, Date, Integer, DateTime, ForeignKey, JSON, BigInteger, text, func, Float, Boolean, Sequence,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime, timezone

Base = declarative_base() # объектно-реляционное отображение таблиц рел. базах данных в виде классов. Создается из экземпляра 
# ORM класса, наследуемым, например, от declarative_base


def gen_uuid():
    return uuid.uuid4()


class Agent(Base):
    __tablename__ = "AGENT"

    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    # Человекочитаемый порядковый идентификатор (external_id) — заполняется серверной последовательностью
    external_id = Column(
        BigInteger,
        Sequence('agent_external_id_seq', start=1, increment=1), 
        nullable=False,
        unique=True
    )

    last_name = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), nullable=True)  

    legal_address = Column(Text, nullable=True)
    actual_address = Column(Text, nullable=True)
    inn = Column(String(12), nullable=True)
    ogrnip = Column(String(15), nullable=True)
    account_number = Column(String(34), nullable=True)
    correspondent_account = Column(String(34), nullable=True)
    bic = Column(String(9), nullable=True)

    # Relationship: один агент — много клиентов
    # FK у CLIENT задан с ondelete="RESTRICT", поэтому здесь НЕ ставится cascade удаления.
    clients = relationship(
        "Client",
        back_populates="agent",
        passive_deletes=True,
        # не указываем cascade="all, delete-orphan" — чтобы не конфликтовать с RESTRICT
    )

    def __repr__(self):
        return f"<Agent {self.agent_id} {self.last_name}>"


class Status(Base):
    __tablename__ = "STATUS"
    status_code = Column(String(32), primary_key=True)
    description = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Status {self.status_code}>"


class Stage(Base):
    __tablename__ = "STAGE"
    stage_code = Column(String(32), primary_key=True)
    description = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Stage {self.stage_code}>"


class Client(Base):
    __tablename__ = "CLIENT"
    __table_args__ = (
        CheckConstraint(
            "taxation_system IN ('УСН', 'ОСНО')",
            name="ck_client_taxation_system_allowed",
        ),
        CheckConstraint(
            "contract_status IS NULL OR contract_status IN ('Подписан', 'Сделан', 'Отправлен')",
            name="ck_client_contract_status_allowed",
        ),
        CheckConstraint(
            "act_status IS NULL OR act_status IN ('Подписан', 'Сделан', 'Отправлен')",
            name="ck_client_act_status_allowed",
        ),
        CheckConstraint(
            "prosthetist IS NULL OR prosthetist IN ('Дмитрий', 'Никита')",
            name="ck_client_prosthetist_allowed",
        ),
        CheckConstraint(
            "(prosthetist IS NULL AND place_of_residence IS NULL) OR "
            "(prosthetist = 'Дмитрий' AND place_of_residence = 'Ивана Сусанина, д. 3') OR "
            "(prosthetist = 'Никита' AND place_of_residence = 'Большая Почтовая, д. 18/20')",
            name="ck_client_prosthetist_address",
        ),
    )

    client_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)

    # Человекочитаемый порядковый идентификатор (external_id) — заполняется последовательностью
    # Человекочитаемый порядковый идентификатор (external_id)
    external_id = Column(
        BigInteger,
        Sequence('client_external_id_seq', start=1, increment=1), 
        nullable=False,
        unique=True
    )
  
    last_name = Column(String(128), nullable=False)
    first_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), nullable=True)  # отчество — опционально

    status_code = Column(String(32), ForeignKey("STATUS.status_code"), nullable=False)
    current_stage = Column(String(32), ForeignKey("STAGE.stage_code"), nullable=False)
    contract_status = Column(String(32), nullable=True)
    act_status = Column(String(32), nullable=True)

    # на агента — запрещаем каскадное удаление (RESTRICT), чтобы случайно не потерять клиентов
    agent_id = Column(UUID(as_uuid=True), ForeignKey("AGENT.agent_id", ondelete="RESTRICT"), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    notes = Column(Text, nullable=True)

    check_date = Column(Date, nullable=True)          
    certificate_price = Column(String(255), nullable=True)

    taxation_system = Column(
        String(16),
        nullable=False,
        default="УСН",
        server_default=text("'УСН'"),
    )
    place_of_residence = Column(String(255), nullable = True)
    prosthetist = Column(String(32), nullable=True)

    ipra_code = Column(String(64), nullable = True)
    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    prosthesis_type = Column(String(255), nullable=True)
    # Legacy mirror for old reports/templates. The normalized source of truth is CLIENT_TSR.
    tsr_code = Column(Text, nullable=True)

    prosthetist_salary = Column(Float, default=0.0)
    agent_salary = Column(Float, default=0.0)
    support_salary = Column(Float, default=0.0)

    # Единые статьи расходов для бухгалтерии «По клиентам» и «По договорам».
    prosthetist_work = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    patient_travel = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    patient_accommodation = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    patient_meals = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    patient_payment = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    other_expenses = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    agency_expenses = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    email = Column(String(64), nullable = True)

    # Детализация расходов бухгалтерии: ключ статьи -> список расходов.
    # Старые числовые поля выше сохраняются для совместимости; при появлении
    # детализации её сумма становится источником значения статьи.
    accounting_expenses = Column(JSON, nullable=True, default=dict)
    accounting_expense_status = Column(JSON, nullable=True, default=dict)

    # отношения
    # prosthesis_type = relationship("ProsthesisRef", back_populates = "client")
    # tsr_code = relationship("TstCodeRef", back_populates = "client")
    agent = relationship("Agent", back_populates="clients")
    phones = relationship("Phone", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    passports = relationship("Passport", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    snils = relationship("Snils", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    documents = relationship("Document", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    reminders = relationship("Reminder", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    # Комплектующие — складские позиции, поэтому при удалении клиента их нельзя удалять каскадом.
    modules = relationship("Module", back_populates="client", passive_deletes=True)
    tsr_items = relationship(
        "ClientTsr",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ClientTsr.created_at",
    )

    # В класс Client добавьте relationship (после существующих)
    accounting_values = relationship("AccountingFieldValue", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client {self.client_id} {self.last_name}>"

# Documents storage models
class Document(Base):
    __tablename__ = "DOCUMENT"
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    
    # Метаданные файла
    filename = Column(Text, nullable=False)     # Оригинальное имя: "passport.pdf"
    storage_path = Column(Text, nullable=False) # Путь на диске: "storage/uuid.pdf"
    content_type = Column(String(100), nullable=True) # "application/pdf"
    size = Column(Integer, nullable=True)       # Размер в байтах
    document_type = Column(String(64), nullable=True, index=True)
    document_number = Column(String(64), nullable=True)
    contract_total = Column(Float, nullable=True)
    certificate_amount = Column(Float, nullable=True)
    # Конкретный сертификат (экземпляр CLIENT_TSR), на основании которого
    # сформирован договор. Один сертификат может иметь только один актуальный
    # договор; повторная генерация заменяет предыдущий документ.
    certificate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("CLIENT_TSR.client_tsr_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contract_metadata = Column(JSON, nullable=True)
    contract_status = Column(String(32), nullable=True)
    act_status = Column(String(32), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.now, server_default=func.now())

    client = relationship("Client", back_populates="documents")
    certificate = relationship("ClientTsr", back_populates="documents")
    contract_accounting = relationship(
        "ContractAccounting",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Phone(Base):
    __tablename__ = "PHONE"
    phone_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    number = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="phones")



class Passport(Base):
    __tablename__ = "PASSPORT"
    passport_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    full_name = Column(Text, nullable=False)
    birth_date = Column(Date, nullable=True) 
    birth_place = Column(Text, nullable=False)
    series_number = Column(String(20), nullable=False)
    issued_by = Column(Text, nullable=False)
    issue_date = Column(Date, nullable=False)
    department_code = Column(String(7), nullable=True) 
    registration_address = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="passports")


class Snils(Base):
    __tablename__ = "SNILS"
    snils_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    number = Column(String(14), nullable=False)
    issued_date = Column(Date, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="snils")


class Reminder(Base):
    __tablename__ = "REMINDER"
    reminder_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    service_stage = Column(String(32), ForeignKey("STAGE.stage_code"), nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="reminders")


class AuditLog(Base):
    __tablename__ = "AUDIT_LOG"
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    entity = Column(String(64), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    details = Column(JSON, nullable=True)


class Module(Base):
    __tablename__ = "MODULES"

    module_id = Column(UUID(as_uuid = True), primary_key = True, default = gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="SET NULL"), nullable=True)
    tsr_id = Column(UUID(as_uuid=True), ForeignKey("REF_TSR.tsr_id", ondelete="RESTRICT"), nullable=True, index=True)
    client_tsr_id = Column(
        UUID(as_uuid=True),
        ForeignKey("CLIENT_TSR.client_tsr_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    module_name_index = Column(String(128), ForeignKey("REF_NameIndex.name_index"), nullable = False) 
    supplier = Column(String(64), nullable = False)
    ordered = Column(Integer, nullable=False, default=0, server_default=text("0"))
    order_date_acc_num = Column(String(64), nullable = False)
    quantity = Column(Integer, nullable = False, default = 1)
    size = Column(String(64), nullable=True)
    stiffness = Column(String(64), nullable=True)
    side = Column(String(64), nullable=True)
    cost = Column(Float)
    price = Column(Float)
    recd = Column(Integer, nullable=False, default=0, server_default=text("0"))
    pending = Column(Integer, nullable=False, default=0, server_default=text("0"))
    prosthetist_keep = Column(Integer, nullable=False, default=0, server_default=text("0"))
    properties = Column(String(64), nullable = False)
    created_at = Column(DateTime(timezone = True), server_default = func.now(), nullable = False)
    updated_at = Column(DateTime(timezone = True), server_default = func.now(), onupdate = func.now(), nullable = False)
    notes = Column(Text, nullable=True)
    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )
    # Ручной архив не сбрасывается при восстановлении карточки клиента.
    is_manually_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    # Отдельное состояние для новой вкладки «Склад». Оно не заменяет владельца:
    # при отправке позиции на склад владелец снимается, а этот флаг позволяет
    # отличить бесхозную складскую позицию от позиции рабочего склада.
    is_in_stock = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )
    # DBCRM_UPDATE_20260831: stock accounting
    # True only while a client assignment was made directly from the dedicated
    # «Склад» state.  Such an item was bought earlier and must not become a new
    # expense when it is put back into work.
    accounting_cost_excluded = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    client = relationship("Client", back_populates = "modules")
    tsr = relationship("TstCodeRef", back_populates="modules")
    client_tsr = relationship("ClientTsr", back_populates="modules")


class User(Base):
    __tablename__ = "USERS"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="user") # 'admin' или 'user'
    is_active = Column(Boolean, default=True) # Требуется import Boolean
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    settings = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class ProsthesisRef(Base):
    """Legacy reference retained for API/backward compatibility."""

    __tablename__ = "REF_PROSTHESIS"
    prosthesis_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name = Column(Text, nullable=True, unique=True)


class TstCodeRef(Base):
    __tablename__ = "REF_TSR"
    tsr_id = Column(UUID(as_uuid = True), primary_key = True, default = gen_uuid)
    #number_code = Column(Text, nulllable = True, unique = True)
    #letter_code = Column(Text, nulllable = True, unique = True)
    full_tsr_code = Column(Text, nullable=True, unique=True)
    modules = relationship("Module", back_populates="tsr", passive_deletes=True)
    client_links = relationship("ClientTsr", back_populates="tsr", passive_deletes=True)


class ClientTsr(Base):
    """Explicit TSR assignment to a client, independent from warehouse components."""

    __tablename__ = "CLIENT_TSR"
    __table_args__ = (
        CheckConstraint(
            "prosthetist IS NULL OR prosthetist IN ('Дмитрий', 'Никита')",
            name="ck_client_tsr_prosthetist_allowed",
        ),
        CheckConstraint(
            "(prosthetist IS NULL AND place_of_residence IS NULL) OR "
            "(prosthetist = 'Дмитрий' AND place_of_residence = 'Ивана Сусанина, д. 3') OR "
            "(prosthetist = 'Никита' AND place_of_residence = 'Большая Почтовая, д. 18/20')",
            name="ck_client_tsr_prosthetist_address",
        ),
    )
    client_tsr_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("CLIENT.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tsr_id = Column(
        UUID(as_uuid=True),
        ForeignKey("REF_TSR.tsr_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    check_date = Column(Date, nullable=True)
    certificate_price = Column(String(255), nullable=True)
    prosthetist = Column(String(32), nullable=True)
    place_of_residence = Column(String(255), nullable=True)
    repeat_visit_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client = relationship("Client", back_populates="tsr_items")
    tsr = relationship("TstCodeRef", back_populates="client_links")
    modules = relationship("Module", back_populates="client_tsr", passive_deletes=True)
    documents = relationship("Document", back_populates="certificate", passive_deletes=True)


class ModuleNameIndex(Base):
    __tablename__ = "REF_NameIndex"
    name_index_id = Column(UUID(as_uuid = True), primary_key = True, default = gen_uuid)
    name_index = Column(Text, nullable = True, unique = True)

# --- ACCOUNTING CUSTOM FIELDS ---
class AccountingCustomField(Base):
    __tablename__ = "ACCOUNTING_CUSTOM_FIELD"
    
    field_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    field_name = Column(String(128), unique=True, nullable=False)
    field_type = Column(String(16), nullable=False)  # 'number' или 'text'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    values = relationship("AccountingFieldValue", back_populates="field", cascade="all, delete-orphan")


class AccountingFieldValue(Base):
    __tablename__ = "ACCOUNTING_FIELD_VALUE"
    
    value_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    field_id = Column(UUID(as_uuid=True), ForeignKey("ACCOUNTING_CUSTOM_FIELD.field_id", ondelete="CASCADE"), nullable=False)
    value_text = Column(Text, nullable=True)
    value_number = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    client = relationship("Client", back_populates="accounting_values")
    field = relationship("AccountingCustomField", back_populates="values")


class ContractAccounting(Base):
    __tablename__ = "CONTRACT_ACCOUNTING"

    accounting_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("DOCUMENT.document_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    prosthetist_work = Column(Float, nullable=False, default=0.0)
    patient_travel = Column(Float, nullable=False, default=0.0)
    patient_accommodation = Column(Float, nullable=False, default=0.0)
    patient_meals = Column(Float, nullable=False, default=0.0)
    patient_payment = Column(Float, nullable=False, default=0.0)
    other_expenses = Column(Float, nullable=False, default=0.0)
    agency_expenses = Column(Float, nullable=False, default=0.0)
    custom_values = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document = relationship("Document", back_populates="contract_accounting")
