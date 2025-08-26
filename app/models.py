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
    Column, String, Text, Date, Integer, DateTime, ForeignKey, JSON, BigInteger, text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime, timezone

Base = declarative_base()


def gen_uuid():
    return uuid.uuid4()


class Agent(Base):
    __tablename__ = "AGENT"

    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)

    # Человекочитаемый порядковый идентификатор (external_id) — заполняется серверной последовательностью
    external_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
        server_default=text("nextval('agent_external_id_seq')")
    )

    last_name = Column(String(128), nullable=False)
    first_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), nullable=True)  # отчество — опционально

    legal_address = Column(Text, nullable=False)
    actual_address = Column(Text, nullable=False)
    inn = Column(String(12), nullable=False)
    ogrnip = Column(String(15), nullable=False)
    account_number = Column(String(34), nullable=False)
    correspondent_account = Column(String(34), nullable=False)
    bic = Column(String(9), nullable=False)

    # Relationship: один агент — много клиентов
    # Замечание: FK у CLIENT задан с ondelete="RESTRICT", поэтому здесь НЕ ставим cascade удаления.
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
    external_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
        server_default=text("nextval('client_external_id_seq')")
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

    # отношения
    agent = relationship("Agent", back_populates="clients")
    phones = relationship("Phone", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    passports = relationship("Passport", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    snils = relationship("Snils", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    documents = relationship("Document", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)
    reminders = relationship("Reminder", back_populates="client", cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f"<Client {self.client_id} {self.last_name}>"


class DocumentType(Base):
    __tablename__ = "DOCUMENT_TYPE"
    type_code = Column(String(32), primary_key=True)
    title = Column(Text, nullable=False)


class Document(Base):
    __tablename__ = "DOCUMENT"
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    type_code = Column(String(32), ForeignKey("DOCUMENT_TYPE.type_code"), nullable=False)
    filename = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="documents")
    doc_type = relationship("DocumentType")


class Phone(Base):
    __tablename__ = "PHONE"
    phone_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    number = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="phones")


# app/models.py

# ... (остальной код файла без изменений) ...

class Passport(Base):
    __tablename__ = "PASSPORT"
    passport_id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=True), ForeignKey("CLIENT.client_id", ondelete="CASCADE"), nullable=False)
    full_name = Column(Text, nullable=False)
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    birth_date = Column(Date, nullable=True) # <-- ДОБАВЛЕНО: Дата рождения
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    birth_place = Column(Text, nullable=False)
    series_number = Column(String(20), nullable=False)
    issued_by = Column(Text, nullable=False)
    issue_date = Column(Date, nullable=False)
    
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    department_code = Column(String(7), nullable=True) # <-- ДОБАВЛЕНО: Код подразделения (формат xxx-xxx)
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    
    expiry_date = Column(Date, nullable=True)
    registration_address = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client = relationship("Client", back_populates="passports")

# ... (остальной код файла без изменений) ...


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
