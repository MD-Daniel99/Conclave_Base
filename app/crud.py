'''
Функции доступа к базе данных.

 - create_client будет создавать клиента и (опционально) телефоны, возвращать досье клиента
 - get_client будет возвращать досье клиента (включая телефоны и связанные сущности)
 - list_clients — пагинация, поиск по ФИО, возвращает вложенные сущности
 - update_client — частичное обновление (PATCH)
 - delete_client — удаление

Роуты используют response_model и get_db()
'''

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, or_, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from datetime import datetime

from . import models, schemas


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
        # fallback: отдельный запрос (на случай, если связь не была загружена)
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

    # agent summary (use relationship if available)
    agent_summary = None
    agent_obj = getattr(client, "agent", None)
    if agent_obj is None and client.agent_id is not None:
        # safe fallback — загрузим агента
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
        # вложенные
        "agent": agent_summary,
        "status": status_summary,
        "stage": stage_summary,
        "phones": phones,
        "passports": passports_list,
        "snils": snils_list,
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
    """
    Возвращает клиента с вложенными сущностями.
    Используем select + selectinload, чтобы подгрузить нужные связи одним запросом.
    """
    stmt = (
        select(models.Client)
        .where(models.Client.client_id == client_id)
        .options(
            selectinload(models.Client.phones),
            selectinload(models.Client.agent),
            selectinload(models.Client.passports),
            selectinload(models.Client.snils),
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
    current_stage: Optional[str] = None, # <--- ИЗМЕНЕНИЕ: Добавлен параметр
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
    # <--- ИЗМЕНЕНИЕ: Добавлено условие фильтрации
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
        db.refresh(client)
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
    # ИЗМЕНЕНИЕ: Корректная обработка опционального поля
    corr_account = agent_in.correspondent_account or agent_in.account_number

    agent = models.Agent(
        last_name=agent_in.last_name,
        first_name=agent_in.first_name or "",
        middle_name=agent_in.middle_name or "",
        legal_address=agent_in.legal_address,
        actual_address=agent_in.actual_address,
        inn=str(agent_in.inn),
        ogrnip=str(agent_in.ogrnip),
        account_number=str(agent_in.account_number),
        correspondent_account=corr_account, # <--- ИЗМЕНЕНИЕ
        bic=str(agent_in.bic),
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


def list_agents(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Список агентов с поиском по ФИО (q), пагинацией.
    """
    stmt = select(models.Agent)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                models.Agent.first_name.ilike(like),
                models.Agent.last_name.ilike(like),
                models.Agent.middle_name.ilike(like),
            )
        )
    stmt = stmt.order_by(models.Agent.last_name, models.Agent.first_name).offset(skip).limit(limit)
    agents = db.execute(stmt).scalars().all()
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
# Phones, Passport, SNILS (НОВЫЕ И ОБНОВЛЕННЫЕ ФУНКЦИИ)
# ----------------------------------

def add_phone(db: Session, client_id: UUID, number: str) -> models.Phone:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")

    phone = models.Phone(client_id=client_id, number=number)
    db.add(phone)
    try:
        db.commit()
        db.refresh(phone)
        return phone
    except Exception:
        db.rollback()
        raise


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

def create_passport(db: Session, client_id: UUID, passport_in: schemas.PassportCreate) -> models.Passport:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    
    passport = models.Passport(client_id=client_id, **passport_in.model_dump())
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

def create_snils(db: Session, client_id: UUID, snils_in: schemas.SnilsCreate) -> models.Snils:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
        
    snils = models.Snils(client_id=client_id, **snils_in.model_dump())
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