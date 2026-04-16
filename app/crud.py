# Бизнес-логика/CRUD - операции с данными

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, or_, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone

from . import models, schemas
from passlib.context import CryptContext

import os
import shutil
import uuid

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto") 

# --- USER CRUD ---

def get_user_by_username(db: Session, username: str):
    return db.execute(select(models.User).where(models.User.username == username)).scalars().first()

def create_user(db: Session, user_in: schemas.UserCreate):
    hashed_password = pwd_context.hash(user_in.password)
    db_user = models.User(
        username=user_in.username,
        password_hash=hashed_password,
        role=user_in.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, user_id: UUID):
    return db.get(models.User, user_id)

def update_user(db: Session, user_id: UUID, payload: schemas.UserUpdate):
    user = db.get(models.User, user_id)
    if not user: return None
    
    # Обновление логина с проверкой на уникальность
    if payload.username is not None:
        # Проверяем, не занят ли логин кем-то другим
        existing = get_user_by_username(db, payload.username)
        if existing and existing.user_id != user_id:
            raise ValueError(f"Логин '{payload.username}' уже занят.")
        user.username = payload.username

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = pwd_context.hash(payload.password)
        
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise ValueError("Ошибка базы данных (возможно, логин занят)")
    except Exception as e:
        db.rollback()
        raise e

def delete_user(db: Session, user_id: UUID):
    user = db.get(models.User, user_id)
    if not user: return False
    db.delete(user)
    db.commit()
    return True

def _client_to_dict(db: Session, client: models.Client) -> Dict[str, Any]:
    """
    Формирование словаря для ClientRead на основе модели Client и связанных объектов.
    Возвращает dict, чтобы Pydantic корректно сериализовал его в response_model.
    """
    # phones (relationship preloaded via selectinload in list/get)
    phones = []
    if getattr(client, "phones", None) is not None:
        for p in client.phones:
            phones.append({
                "phone_id": p.phone_id,
                "client_id": p.client_id,
                "number": p.number,
                "created_at": p.created_at
            })
    else:
        phones_q = db.execute(
            select(models.Phone).where(models.Phone.client_id == client.client_id).order_by(models.Phone.phone_id)
        ).scalars().all()
        for p in phones_q:
            phones.append({
                "phone_id": p.phone_id,
                "client_id": p.client_id,
                "number": p.number,
                "created_at": p.created_at
            })

    # agent summary 
    agent_summary = None
    agent_obj = getattr(client, "agent", None)
    if agent_obj is None and client.agent_id is not None:
        # safe fallback 
        agent_obj = db.get(models.Agent, client.agent_id)
    if agent_obj is not None:
        agent_summary = {
            "agent_id": agent_obj.agent_id,
            "external_id": getattr(agent_obj, "external_id", None),
            "last_name": agent_obj.last_name,
            "first_name": getattr(agent_obj, "first_name", None),
            "middle_name": getattr(agent_obj, "middle_name", None),
        }

    # status & stage (справочники)
    status_summary = None
    if client.status_code:
        st = db.get(models.Status, client.status_code)
        if st:
            status_summary = {"status_code": st.status_code, "description": st.description}

    stage_summary = None
    if client.current_stage:
        sg = db.get(models.Stage, client.current_stage)
        if sg:
            stage_summary = {"stage_code": sg.stage_code, "description": sg.description}

    # passports
    passports_list: List[Dict[str, Any]] = []
    if getattr(client, "passports", None) is not None:
        for ps in client.passports:
            passports_list.append({
                "passport_id": ps.passport_id,
                "client_id": ps.client_id,
                "full_name": ps.full_name,
                "birth_place": ps.birth_place,
                "birth_date": ps.birth_date,
                "department_code": ps.department_code,
                "series_number": ps.series_number,
                "issued_by": ps.issued_by,
                "issue_date": ps.issue_date,
                "expiry_date": ps.expiry_date,
                "registration_address": ps.registration_address,
                "version": ps.version,
                "created_at": ps.created_at,
            })
    else:
        # fallback query
        pss = db.execute(select(models.Passport).where(models.Passport.client_id == client.client_id)).scalars().all()
        for ps in pss:
            passports_list.append({
                "passport_id": ps.passport_id,
                "client_id": ps.client_id,
                "full_name": ps.full_name,
                "birth_place": ps.birth_place,
                "series_number": ps.series_number,
                "issued_by": ps.issued_by,
                "issue_date": ps.issue_date,
                "expiry_date": ps.expiry_date,
                "registration_address": ps.registration_address,
                "version": ps.version,
                "created_at": ps.created_at,
            })

    # snils
    snils_list: List[Dict[str, Any]] = []
    if getattr(client, "snils", None) is not None:
        for s in client.snils:
            snils_list.append({
                "snils_id": s.snils_id,
                "client_id": s.client_id,
                "number": s.number,
                "issued_date": s.issued_date,
                "version": s.version,
                "created_at": s.created_at,
            })
    else:
        sns = db.execute(select(models.Snils).where(models.Snils.client_id == client.client_id)).scalars().all()
        for s in sns:
            snils_list.append({
                "snils_id": s.snils_id,
                "client_id": s.client_id,
                "number": s.number,
                "issued_date": s.issued_date,
                "version": s.version,
                "created_at": s.created_at,
            })
    
    modules_list: List[Dict[str, Any]] = []
    if "modules" in client.__dict__: 
        for m in client.modules:
            modules_list.append(schemas.ModuleRead.from_orm(m).model_dump())
    else:
        # Fallback (на всякий случай, если вызвана функцию без selectinload)
        m_q = db.execute(select(models.Module).where(models.Module.client_id == client.client_id)).scalars().all()
        for m in m_q:
            modules_list.append(schemas.ModuleRead.from_orm(m).model_dump())

    custom_fields = get_client_custom_field_values(db, client.client_id)

    result = {
        "client_id": client.client_id,
        "external_id": getattr(client, "external_id", None),
        "last_name": client.last_name,
        "first_name": client.first_name,
        "middle_name": client.middle_name,
        "status_code": client.status_code,
        "current_stage": client.current_stage,
        "agent_id": client.agent_id,
        "deadline": client.deadline,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        "notes": client.notes,
        "check_date": client.check_date,
        "prosthesis_type": client.prosthesis_type,
        "certificate_price": client.certificate_price,
        "ipra_code": client.ipra_code,
        "place_of_residence": client.place_of_residence,
        # вложенные
        "agent": agent_summary,
        "status": status_summary,
        "stage": stage_summary,
        "phones": phones,
        "passports": passports_list,
        "snils": snils_list,
        "modules": modules_list,
        "tsr_code": client.tsr_code,
        "prosthetist_salary": getattr(client, "prosthetist_salary", 0.0),
        "agent_salary": getattr(client, "agent_salary", 0.0),
        "support_salary": getattr(client, "support_salary", 0.0),
        "custom_fields": custom_fields,
    }

    return result


# -------------------------
# Client
# -------------------------

def create_client(db: Session, client_in: schemas.ClientCreate) -> Dict[str, Any]:
    """
    Создать клиента и телефоны (если есть).
    Возвращает dict, соответствующий 'schemas.ClientRead'.
    """
    # Проверка на существование объекта
    agent_exists = db.get(models.Agent, client_in.agent_id)
    if not agent_exists:
        raise ValueError(f"Agent with id = {client_in.agent_id} not found")

    client = models.Client(
        last_name=client_in.last_name,
        first_name=client_in.first_name,
        middle_name=client_in.middle_name or "",
        status_code=client_in.status_code,
        current_stage=client_in.current_stage,
        agent_id=client_in.agent_id,
        deadline=client_in.deadline,
        notes=client_in.notes,
        check_date=client_in.check_date,
        prosthesis_type=client_in.prosthesis_type,
        certificate_price=client_in.certificate_price,
        place_of_residence=client_in.place_of_residence,
        ipra_code=client_in.ipra_code,
        tsr_code = client_in.tsr_code,
    )

    db.add(client)
    try:
        db.flush()  # чтобы client.client_id появился до commit
        for p in client_in.phones or []:
            phone = models.Phone(client_id=client.client_id, number=p.number)
            db.add(phone)

        db.commit()
        db.refresh(client)
        return _client_to_dict(db, client)
    except IntegrityError as e:
        db.rollback()
        raise e
    



def get_client(db: Session, client_id: UUID) -> Optional[Dict[str, Any]]:
    stmt = (
        select(models.Client)
        .where(models.Client.client_id == client_id)
        .options(
            selectinload(models.Client.phones),
            selectinload(models.Client.agent),
            selectinload(models.Client.passports),
            selectinload(models.Client.snils),
            selectinload(models.Client.modules),
            selectinload(models.Client.accounting_values).joinedload(models.AccountingFieldValue.field),
        )
    )
    client = db.execute(stmt).scalars().first()
    if not client:
        return None
    return _client_to_dict(db, client)


def list_clients(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[UUID] = None,
    current_stage: Optional[str] = None, 
) -> List[Dict[str, Any]]:
    """
    Возвращает список клиентов с вложенными сущностями (agent, status, stage, phones, passports, snils).
    Поддерживает поиск по ФИО (q), фильтр по статусу и агенту, пагинацию.
    """
    stmt = select(models.Client).options(
        selectinload(models.Client.phones),
        selectinload(models.Client.agent),
        selectinload(models.Client.passports),
        selectinload(models.Client.snils),
        selectinload(models.Client.modules),
        selectinload(models.Client.accounting_values).joinedload(models.AccountingFieldValue.field),
    )

    conditions = []
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                models.Client.first_name.ilike(like),
                models.Client.last_name.ilike(like),
                models.Client.middle_name.ilike(like),
            )
        )
    if status:
        conditions.append(models.Client.status_code == status)
    if agent_id:
        conditions.append(models.Client.agent_id == agent_id)
    if current_stage:
        conditions.append(models.Client.current_stage == current_stage)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # порядок — по external_id (если есть) или по фамилии/имени
    # используем существующие колонки; если external_id не существует в старых БД — сортировка по NULLs
    try:
        stmt = stmt.order_by(models.Client.external_id)  # если column есть, будет работать
    except Exception:
        stmt = stmt.order_by(models.Client.last_name, models.Client.first_name)

    stmt = stmt.offset(skip).limit(limit)
    clients = db.execute(stmt).scalars().all()

    results = [_client_to_dict(db, c) for c in clients]
    return results


def update_client(db: Session, client_id: UUID, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    client = db.get(models.Client, client_id)
    if not client:
        return None

    # обновляются только существующие поля
    for k, v in payload.items():
        if hasattr(client, k):
            setattr(client, k, v)

    db.add(client)
    try:
        db.commit()
        db.expire(client)  # Сбрасываем кэш
        db.refresh(client)  # Перезагружаем из БД
        return _client_to_dict(db, client)
    except Exception:
        db.rollback()
        raise


def delete_client(db: Session, client_id: UUID) -> bool:
    client = db.get(models.Client, client_id)
    if not client:
        return False
    db.delete(client)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# -------------------------
# Agent
# -------------------------

def _agent_to_dict(agent: models.Agent) -> Dict[str, Any]:
    """Преобразование модели Agent в словарь для response_model."""
    return {
        "agent_id": agent.agent_id,
        "external_id": getattr(agent, "external_id", None),
        "last_name": agent.last_name,
        "first_name": agent.first_name,
        "middle_name": agent.middle_name,
        "legal_address": agent.legal_address,
        "actual_address": agent.actual_address,
        "inn": agent.inn,
        "ogrnip": agent.ogrnip,
        "account_number": agent.account_number,
        "correspondent_account": agent.correspondent_account,
        "bic": agent.bic,
    }


def create_agent(db: Session, agent_in: schemas.AgentCreate) -> Dict[str, Any]:
    """
    Создаёт агента и возвращает dict, соответствующий schemas.AgentRead.
    """
    corr_account = agent_in.correspondent_account or agent_in.account_number

    agent = models.Agent(
        last_name=agent_in.last_name,
        first_name=agent_in.first_name or "",
        middle_name=agent_in.middle_name or "",
        legal_address=agent_in.legal_address,
        actual_address=agent_in.actual_address,
        
        # УБРАЛИ str(), теперь передается None, если поле пустое
        inn=agent_in.inn,
        ogrnip=agent_in.ogrnip,
        account_number=agent_in.account_number,
        correspondent_account=corr_account,
        bic=agent_in.bic,
    )
    
    db.add(agent)
    try:
        # flush чтобы DB присвоила external_id (если server_default/sequence настроены)
        db.flush()
        db.commit()
        db.refresh(agent)
        return _agent_to_dict(agent)
    except IntegrityError as e:
        db.rollback()
        raise e


def get_agent(db: Session, agent_id: UUID) -> Optional[Dict[str, Any]]:
    agent = db.get(models.Agent, agent_id)
    if not agent:
        return None
    return _agent_to_dict(agent)


def get_agent_by_external(db: Session, external_id: int) -> Optional[Dict[str, Any]]:
    stmt = select(models.Agent).where(models.Agent.external_id == external_id)
    agent = db.execute(stmt).scalars().first()
    if not agent:
        return None
    return _agent_to_dict(agent)


def list_agents(db: Session, skip: int = 0, limit: int = 50, q: Optional[str] = None):
    stmt = select(models.Agent).distinct()
    
    if q:
        like = f"%{q}%"
        agent_cond = or_(
            models.Agent.first_name.ilike(like),
            models.Agent.last_name.ilike(like),
            models.Agent.middle_name.ilike(like)
        )
        
        stmt = stmt.outerjoin(models.Client)
        client_cond = or_(
            models.Client.first_name.ilike(like),
            models.Client.last_name.ilike(like)
        )
        
        stmt = stmt.where(or_(agent_cond, client_cond))

    stmt = stmt.order_by(models.Agent.last_name, models.Agent.first_name).offset(skip).limit(limit)
    agents = db.execute(stmt).scalars().all()
    # Используем существующую функцию _agent_to_dict
    return [_agent_to_dict(a) for a in agents]


def update_agent(db: Session, agent_id: UUID, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Частичное обновление агента (PATCH-like). Возвращает обновлённый агент или None.
    """
    agent = db.get(models.Agent, agent_id)
    if not agent:
        return None

    for k, v in payload.items():
        if hasattr(agent, k):
            setattr(agent, k, v)
    db.add(agent)
    try:
        db.commit()
        db.refresh(agent)
        return _agent_to_dict(agent)
    except Exception:
        db.rollback()
        raise


def delete_agent(db: Session, agent_id: UUID) -> bool:
    """
    Удаление агента. Если на агента ссылаются клиенты — запретим удаление (sa.ForeignKey).
    """
    agent = db.get(models.Agent, agent_id)
    if not agent:
        return False

    # Проверим, есть ли связанные клиенты
    cnt = db.execute(select(func.count()).select_from(models.Client).where(models.Client.agent_id == agent_id)).scalar_one()
    if cnt > 0:
        # можно либо запретить, либо удалять каскадом; я предлагаю запретить и вернуть ошибку
        raise ValueError("Agent has linked clients and cannot be deleted. Reassign or delete clients first.")

    db.delete(agent)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# ----------------------------------
# Phones, Passport, SNILS 
# ----------------------------------

def add_phone(db: Session, client_id: UUID, number: str) -> models.Phone:
    client = db.get(models.Client, client_id)
    if not client: raise ValueError("Client not found")
    
    phone = models.Phone(client_id=client_id, number=number,  created_at=datetime.now(timezone.utc))
    db.add(phone)
    db.commit()
    db.refresh(phone)
    return phone


def list_phones(db: Session, client_id: UUID) -> List[Dict[str, Any]]:
    phones = db.execute(select(models.Phone).where(models.Phone.client_id == client_id)).scalars().all()
    return [
        {"phone_id": p.phone_id, "client_id": p.client_id, "number": p.number, "created_at": p.created_at}
        for p in phones
    ]

def delete_phone(db: Session, phone_id: int) -> bool:
    phone = db.get(models.Phone, phone_id)
    if not phone:
        return False
    db.delete(phone)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
def update_phone(db: Session, phone_id: int, payload: Dict[str, Any]) -> Optional[models.Phone]:
    phone = db.get(models.Phone, phone_id)
    if not phone:
        return None
    
    for key, value in payload.items():
        setattr(phone, key, value)
        
    db.add(phone)
    try:
        db.commit()
        db.refresh(phone)
        return phone
    except Exception:
        db.rollback()
        raise

def create_passport(db: Session, client_id: UUID, passport_in: schemas.PassportCreate) -> models.Passport:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    
    # Явная передача полей, чтобы избежать ошибок валидации
    passport = models.Passport(
        client_id=client_id,
        full_name=passport_in.full_name,
        birth_date=passport_in.birth_date,
        birth_place=passport_in.birth_place,
        series_number=passport_in.series_number,
        issued_by=passport_in.issued_by,
        issue_date=passport_in.issue_date,
        department_code=passport_in.department_code,
        expiry_date=passport_in.expiry_date,
        registration_address=passport_in.registration_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(passport)
    try:
        db.commit()
        db.refresh(passport)
        return passport
    except Exception:
        db.rollback()
        raise

def update_passport(db: Session, passport_id: UUID, payload: Dict[str, Any]) -> Optional[models.Passport]:
    passport = db.get(models.Passport, passport_id)
    if not passport:
        return None
    
    for key, value in payload.items():
        setattr(passport, key, value)
        
    db.add(passport)
    try:
        db.commit()
        db.refresh(passport)
        return passport
    except Exception:
        db.rollback()
        raise

def delete_passport(db: Session, passport_id: UUID) -> bool:
    passport = db.get(models.Passport, passport_id)
    if not passport:
        return False
    db.delete(passport)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

def create_snils(db: Session, client_id: UUID, snils_in: schemas.SnilsCreate) -> models.Snils:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
        
    snils = models.Snils(
        client_id=client_id, 
        number=snils_in.number, 
        issued_date=snils_in.issued_date,
        created_at=datetime.now(timezone.utc),
    )
    db.add(snils)
    try:
        db.commit()
        db.refresh(snils)
        return snils
    except Exception:
        db.rollback()
        raise

def update_snils(db: Session, snils_id: UUID, payload: Dict[str, Any]) -> Optional[models.Snils]:
    snils = db.get(models.Snils, snils_id)
    if not snils:
        return None
        
    for key, value in payload.items():
        setattr(snils, key, value)
        
    db.add(snils)
    try:
        db.commit()
        db.refresh(snils)
        return snils
    except Exception:
        db.rollback()
        raise

def delete_snils(db: Session, snils_id: UUID) -> bool:
    snils = db.get(models.Snils, snils_id)
    if not snils:
        return False
    db.delete(snils)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

# -------------------------
# Stage / Status / helpers
# -------------------------
def list_stages(db: Session):
    """Вернуть все Stage (ORM-объекты)"""
    return db.execute(select(models.Stage).order_by(models.Stage.stage_code)).scalars().all()


def get_stage(db: Session, stage_code: str):
    """Получить Stage по коду"""
    return db.get(models.Stage, stage_code)


def create_stage(db: Session, stage_in: schemas.StageCreate):
    stage = models.Stage(stage_code=stage_in.stage_code, description=stage_in.description)
    db.add(stage)
    try:
        db.commit()
        db.refresh(stage)
        return stage
    except Exception:
        db.rollback()
        raise


def list_statuses(db: Session):
    return db.execute(select(models.Status).order_by(models.Status.status_code)).scalars().all()


def get_status(db: Session, status_code: str):
    return db.get(models.Status, status_code)


def create_status(db: Session, status_in: schemas.StatusCreate):
    status = models.Status(status_code=status_in.status_code, description=status_in.description)
    db.add(status)
    try:
        db.commit()
        db.refresh(status)
        return status
    except Exception:
        db.rollback()
        raise


# -------------------------
# Module
# -------------------------

def create_module(db: Session, module_in: schemas.ModuleCreate) -> models.Module:
    """Создает модуль. Проверяет клиента, если ID передан."""
    # Если client_id передан (не None), проверяем, существует ли такой клиент
    if module_in.client_id:
        client = db.get(models.Client, module_in.client_id)
        if not client:
            raise ValueError(f"Client with id {module_in.client_id} not found")
    
    # Создаем объект модели
    db_module = models.Module(**module_in.model_dump())

    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    return db_module

def get_module(db: Session, module_id: UUID) -> Optional[models.Module]:
    return db.get(models.Module, module_id)

def list_modules(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    q: Optional[str] = None, 
    supplier: Optional[str] = None, 
    client_id: Optional[UUID] = None
) -> List[models.Module]:
    
    stmt = select(models.Module).options(selectinload(models.Module.client))

    # условия фильтрации
    conditions = []
    if q:
        conditions.append(models.Module.module_name.ilike(f"%{q}%"))
    if supplier:
        conditions.append(models.Module.supplier.ilike(f"%{supplier}%"))
    if client_id:
        conditions.append(models.Module.client_id == client_id)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(models.Module.updated_at.desc())
    stmt = stmt.offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()

def update_module(db: Session, module_id: UUID, payload: schemas.ModuleUpdate) -> Optional[models.Module]:
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return None
    
    data = payload.model_dump(exclude_unset=True)
    
    # Если меняем владельца
    if 'client_id' in data and data['client_id'] is not None:
        client = db.get(models.Client, data['client_id'])
        if not client: raise ValueError("Target client not found")

    for k, v in data.items():
        setattr(db_module, k, v)
    
    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    return db_module

def delete_module(db: Session, module_id: UUID) -> bool:
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return False
    db.delete(db_module)
    db.commit()
    return True

# Documents storage CRUD
# -------------------------
# FILE STORAGE CRUD
# -------------------------
UPLOAD_DIR = "storage"

def upload_document(db: Session, client_id: UUID, file_obj, filename: str, content_type: str):
    # 1. Проверяем клиента
    if not db.get(models.Client, client_id):
        raise ValueError("Client not found")
    
    # 2. Создаем уникальное имя для хранения, чтобы не было коллизий
    # (например, два файла passport.pdf перезапишут друг друга, если не переименовать)
    unique_name = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    
    # 3. Убедимся, что папка существует
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    print(f"Attempting to save file to: {file_path}")

    # 4. Сохраняем байты на диск
    # file_obj - это SpooledTemporaryFile от FastAPI
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file_obj.file, buffer)
    
    # 5. Получаем размер
    file_size = os.path.getsize(file_path)
    
    # 6. Запись в БД
    db_doc = models.Document(
        client_id=client_id,
        filename=filename,
        storage_path=file_path,
        content_type=content_type,
        size=file_size,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

def list_documents(db: Session, client_id: UUID):
    return db.execute(
        select(models.Document)
        .where(models.Document.client_id == client_id)
        .order_by(models.Document.created_at.desc())
    ).scalars().all()

def get_document(db: Session, document_id: UUID):
    return db.get(models.Document, document_id)

def delete_document(db: Session, document_id: UUID):
    doc = db.get(models.Document, document_id)
    if not doc: return False
    
    # 1. Удаляем файл с диска
    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
    
    # 2. Удаляем из БД
    db.delete(doc)
    db.commit()
    return True


# -------------------------
# Prosthesis / TSR
# -------------------------

def get_prosthesis(db: Session):
    return db.execute(select(models.ProsthesisRef).order_by(models.ProsthesisRef.name)).scalars().all()

def create_prosthesis(db: Session, name: str):
    exists = db.execute(select(models.ProsthesisRef).where(models.ProsthesisRef.name == name)).scalars().first()
    if exists: 
        return exists
    
    new_prosthesis = models.ProsthesisRef(name = name)
    db.add(new_prosthesis)
    db.commit()
    db.refresh(new_prosthesis)
    return new_prosthesis

def delete_prosthesis(db: Session, prosthesis_id: UUID):
    prosthesis_to_delete = db.get(models.ProsthesisRef, prosthesis_id)
    if prosthesis_to_delete:
        db.delete(prosthesis_to_delete)
        db.commit()
        return True
    else:
        return False

def get_tsr(db: Session):
    return db.execute(select(models.TstCodeRef).order_by(models.TstCodeRef.full_tsr_code)).scalars().all()

def create_tsr(db: Session, full_tsr_code: str):
    exists = db.execute(select(models.TstCodeRef).where(models.TstCodeRef.full_tsr_code == full_tsr_code)).scalars().first()
    if exists:
        return exists
    
    new_tsr = models.TstCodeRef(full_tsr_code = full_tsr_code)
    db.add(new_tsr)
    db.commit()
    db.refresh(new_tsr)
    return new_tsr

def delete_tsr(db: Session, tsr_id: UUID):
    tsr_to_delete = db.get(models.TstCodeRef, tsr_id)
    if tsr_to_delete:
        db.delete(tsr_to_delete)
        db.commit()
        return True
    else:
        return False


# -------------------------
# ModuleNameIndex
# -------------------------

def get_module_name_index(db: Session):
    return db.execute(select(models.ModuleNameIndex).order_by(models.ModuleNameIndex.name_index)).scalars().all()

def create_module_name_index(db: Session, name_index: str):
    exists = db.execute(select(models.ModuleNameIndex).where(models.ModuleNameIndex.name_index == name_index)).scalars().first()
    if exists:
        return exists
    
    new_module_name_index = models.ModuleNameIndex(name_index=name_index)
    db.add(new_module_name_index)
    db.commit()
    db.refresh(new_module_name_index)
    return new_module_name_index

def delete_module_name_index(db: Session, name_index_id: UUID):
    module_name_to_delete = db.get(models.ModuleNameIndex, name_index_id)
    if module_name_to_delete:
        db.delete(module_name_to_delete)
        db.commit()
        return True
    else:
        return False

# -------------------------
# Accounting Custom Fields
# -------------------------

def get_accounting_custom_fields(db: Session, active_only: bool = True):
    stmt = select(models.AccountingCustomField)
    if active_only:
        stmt = stmt.where(models.AccountingCustomField.is_active == True)
    return db.execute(stmt.order_by(models.AccountingCustomField.field_name)).scalars().all()

def create_accounting_custom_field(db: Session, field_name: str, field_type: str):
    # проверка уникальности
    existing = db.execute(
        select(models.AccountingCustomField).where(models.AccountingCustomField.field_name == field_name)
    ).scalars().first()
    if existing:
        raise ValueError(f"Field '{field_name}' already exists")
    field = models.AccountingCustomField(field_name=field_name, field_type=field_type)
    db.add(field)
    db.commit()
    db.refresh(field)
    return field

def delete_accounting_custom_field(db: Session, field_id: UUID):
    field = db.get(models.AccountingCustomField, field_id)
    if not field:
        return False
    db.delete(field)
    db.commit()
    return True

def get_client_custom_field_values(db: Session, client_id: UUID) -> Dict[str, Any]:
    """Возвращает словарь {field_name: value} для клиента"""
    stmt = (
        select(models.AccountingFieldValue, models.AccountingCustomField)
        .join(models.AccountingCustomField)
        .where(models.AccountingFieldValue.client_id == client_id)
    )
    result = db.execute(stmt).all()
    values = {}
    for val, field in result:
        if field.field_type == 'number':
            values[field.field_name] = val.value_number
        else:
            values[field.field_name] = val.value_text
    return values

def set_client_custom_field_values(db: Session, client_id: UUID, updates: List[Dict]):
    """Обновляет значения кастомных полей для клиента.
    updates - список вида [{"field_id": UUID, "value": ...}, ...]
    """
    for upd in updates:
        field_id = upd["field_id"]
        value = upd.get("value")
        # Получаем поле, чтобы узнать тип
        field = db.get(models.AccountingCustomField, field_id)
        if not field:
            continue
        # Ищем существующую запись значения
        stmt = select(models.AccountingFieldValue).where(
            models.AccountingFieldValue.client_id == client_id,
            models.AccountingFieldValue.field_id == field_id
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            if field.field_type == 'number':
                existing.value_number = float(value) if value is not None and value != "" else None
            else:
                existing.value_text = str(value) if value is not None else None
        else:
            # создаём новую запись
            new_val = models.AccountingFieldValue(
                client_id=client_id,
                field_id=field_id,
                value_number=float(value) if field.field_type == 'number' and value not in (None, "") else None,
                value_text=str(value) if field.field_type == 'text' and value is not None else None
            )
            db.add(new_val)
    db.commit()

def update_user_settings(db: Session, user_id: UUID, settings: dict):
    user = db.get(models.User, user_id)
    if not user:
        return None
    current = dict(user.settings) if user.settings else {}
    current.update(settings)
    user.settings = current
    db.commit()
    db.refresh(user)
    return user
