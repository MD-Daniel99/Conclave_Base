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
    Column, String, Text, Date, Integer, DateTime, ForeignKey, JSON, BigInteger, text, func, Float, Boolean, Sequence
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

    last_name = Column(String(128), nullable=False)
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

    # на агента — запрещаем каскадное удаление (RESTRICT), чтобы случайно не потерять клиентов
    agent_id = Column(UUID(as_uuid=True), ForeignKey("AGENT.agent_id", ondelete="RESTRICT"), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    notes = Column(Text, nullable=True)

    check_date = Column(Date, nullable=True)          
    certificate_price = Column(String(255), nullable=True)
    taxation_system = Column(
        String(4),
        nullable=False,
        default="УСН",
        server_default=text("'УСН'"),
    )
    ipra_code = Column(String(64), nullable = True)
    place_of_residence = Column(String(255), nullable = True)
    prosthetist = Column(String(255), nullable=True)
    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    prosthesis_type = Column(String(255), ForeignKey("REF_PROSTHESIS.name"), nullable=True) 
    # Хранится как многострочное текстовое поле, потому что в текущем UI можно выбрать несколько ТСР.
    # Для строгой нормализации позже лучше вынести в отдельную таблицу CLIENT_TSR.
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
    contract_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.now, server_default=func.now())

    client = relationship("Client", back_populates="documents")
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
    expiry_date = Column(Date, nullable=True)
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

    client = relationship("Client", back_populates = "modules")
    tsr = relationship("TstCodeRef", back_populates="modules")


class User(Base):
    __tablename__ = "USERS"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="user") # 'admin' или 'user'
    is_active = Column(Boolean, default=True) # Требуется import Boolean
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    settings = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class ProsthesisRef(Base):
    __tablename__ = "REF_PROSTHESIS"
    prosthesis_id = Column(UUID(as_uuid = True), primary_key = True, default = gen_uuid)
    name = Column(Text, nullable = True, unique = True)

class TstCodeRef(Base):
    __tablename__ = "REF_TSR"
    tsr_id = Column(UUID(as_uuid = True), primary_key = True, default = gen_uuid)
    #number_code = Column(Text, nulllable = True, unique = True)
    #letter_code = Column(Text, nulllable = True, unique = True)
    full_tsr_code = Column(Text, nullable=True, unique=True)
    modules = relationship("Module", back_populates="tsr", passive_deletes=True)


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
