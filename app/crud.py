# Бизнес-логика/CRUD - операции с данными

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, or_, func, and_, update, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from . import models, schemas
from .services.tsr_repeat_terms import calculate_repeat_visit_date, get_repeat_term_months
from passlib.context import CryptContext

import os
import shutil
import uuid
import re

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
        visible_modules = [
            module
            for module in client.modules
            if bool(module.is_archived) == bool(client.is_archived)
        ]
        for m in visible_modules:
            modules_list.append(schemas.ModuleRead.model_validate(m).model_dump())
    else:
        # Fallback (на всякий случай, если вызвана функцию без selectinload)
        m_q = db.execute(
            select(models.Module).where(
                models.Module.client_id == client.client_id,
                models.Module.is_archived.is_(bool(client.is_archived)),
            )
        ).scalars().all()
        for m in m_q:
            modules_list.append(schemas.ModuleRead.model_validate(m).model_dump())

    custom_fields = get_client_custom_field_values(db, client.client_id)
    tsr_items = []
    if "tsr_items" in client.__dict__:
        tsr_items = [
            schemas.ClientTsrRead.model_validate(item).model_dump()
            for item in client.tsr_items
        ]
    else:
        linked_tsr = db.execute(
            select(models.ClientTsr)
            .where(models.ClientTsr.client_id == client.client_id)
            .options(selectinload(models.ClientTsr.tsr))
            .order_by(models.ClientTsr.created_at, models.ClientTsr.client_tsr_id)
        ).scalars().all()
        tsr_items = [schemas.ClientTsrRead.model_validate(item).model_dump() for item in linked_tsr]

    result = {
        "client_id": client.client_id,
        "external_id": getattr(client, "external_id", None),
        "last_name": client.last_name,
        "first_name": client.first_name,
        "middle_name": client.middle_name,
        "status_code": client.status_code,
        "current_stage": client.current_stage,
        "contract_status": getattr(client, "contract_status", None),
        "act_status": getattr(client, "act_status", None),
        "agent_id": client.agent_id,
        "deadline": client.deadline,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        "notes": client.notes,
        "check_date": client.check_date,
        "prosthesis_type": client.prosthesis_type,
        "email": getattr(client, "email", None),
        "certificate_price": client.certificate_price,
        "taxation_system": client.taxation_system or "УСН",
        "ipra_code": client.ipra_code,
        "place_of_residence": client.place_of_residence,
        "prosthetist": client.prosthetist,
        "is_archived": bool(client.is_archived),
        # вложенные
        "agent": agent_summary,
        "status": status_summary,
        "stage": stage_summary,
        "phones": phones,
        "passports": passports_list,
        "snils": snils_list,
        "modules": modules_list,
        "tsr_items": tsr_items,
        "tsr_code": client.tsr_code,
        "prosthetist_salary": getattr(client, "prosthetist_salary", 0.0),
        "agent_salary": getattr(client, "agent_salary", 0.0),
        "support_salary": getattr(client, "support_salary", 0.0),
        "prosthetist_work": getattr(client, "prosthetist_work", 0.0),
        "patient_travel": getattr(client, "patient_travel", 0.0),
        "patient_accommodation": getattr(client, "patient_accommodation", 0.0),
        "patient_meals": getattr(client, "patient_meals", 0.0),
        "patient_payment": getattr(client, "patient_payment", 0.0),
        "other_expenses": getattr(client, "other_expenses", 0.0),
        "agency_expenses": getattr(client, "agency_expenses", 0.0),
        "custom_fields": custom_fields,
        "accounting_expenses": getattr(client, "accounting_expenses", None) or {},
        "accounting_expense_status": getattr(client, "accounting_expense_status", None) or {},
    }

    return result



ACCOUNTING_FIXED_EXPENSE_KEYS = {
    "prosthetist_work",
    "patient_travel",
    "patient_accommodation",
    "patient_meals",
    "patient_payment",
    "other_expenses",
    "agency_expenses",
}


def _accounting_field_exists(db: Session, field_key: str) -> bool:
    if field_key in ACCOUNTING_FIXED_EXPENSE_KEYS:
        return True
    if field_key.startswith("custom:"):
        try:
            field_id = UUID(field_key.split(":", 1)[1])
        except (ValueError, IndexError):
            return False
        field = db.get(models.AccountingCustomField, field_id)
        return bool(field and field.is_active and field.field_type == "number")
    return False


def _legacy_accounting_value(db: Session, client: models.Client, field_key: str) -> float:
    if field_key in ACCOUNTING_FIXED_EXPENSE_KEYS:
        return float(getattr(client, field_key, 0.0) or 0.0)
    if field_key.startswith("custom:"):
        try:
            field_id = UUID(field_key.split(":", 1)[1])
        except (ValueError, IndexError):
            return 0.0
        row = db.query(models.AccountingFieldValue).filter(
            models.AccountingFieldValue.client_id == client.client_id,
            models.AccountingFieldValue.field_id == field_id,
        ).first()
        return float(row.value_number or 0.0) if row else 0.0
    return 0.0


def _legacy_accounting_entry(
    db: Session, client: models.Client, field_key: str
) -> dict[str, Any] | None:
    """Build the virtual pre-detailing row for any supported numeric expense field.

    The row is intentionally created from the legacy source (fixed CLIENT column
    or ACCOUNTING_FIELD_VALUE) so old data can be migrated lazily when the user
    edits, deletes, or appends detailed expenses.
    """
    amount = _legacy_accounting_value(db, client, field_key)
    if amount == 0.0:
        return None
    return {
        "id": f"legacy-{field_key}",
        "amount": amount,
        "description": "Сумма до включения детализации",
        "created_at": None,
        "user_id": None,
        "username": None,
    }


def _normalize_expense_store(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for key, entries in value.items():
        if not isinstance(entries, list):
            continue
        result[str(key)] = [dict(item) for item in entries if isinstance(item, dict)]
    return result


def _expense_total(entries: list[dict[str, Any]]) -> float:
    return sum(float(item.get("amount") or 0.0) for item in entries)


def get_accounting_expense_history(db: Session, client_id: UUID, field_key: str) -> dict[str, Any]:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    field_key = field_key.strip()
    if not _accounting_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _normalize_expense_store(client.accounting_expenses)
    entries = store.get(field_key, [])
    status_store = client.accounting_expense_status if isinstance(client.accounting_expense_status, dict) else {}
    paid = str(status_store.get(field_key, "paid")).lower() != "unpaid"

    # Old values without JSON detail remain visible as one legacy row.
    if not entries:
        legacy = _legacy_accounting_entry(db, client, field_key)
        if legacy:
            entries = [legacy]
    return {
        "field_key": field_key,
        "total": _expense_total(entries),
        "paid": paid,
        "entries": entries,
    }


def add_accounting_expense(
    db: Session,
    client_id: UUID,
    payload: schemas.AccountingExpenseCreate,
    user: models.User,
) -> dict[str, Any]:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    field_key = payload.field_key.strip()
    if not _accounting_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _normalize_expense_store(client.accounting_expenses)
    entries = store.setdefault(field_key, [])

    # Lazy migration: preserve a pre-detailing amount as a real first history row.
    if not entries:
        legacy = _legacy_accounting_entry(db, client, field_key)
        if legacy:
            entries.append(legacy)

    entries.append({
        "id": str(uuid.uuid4()),
        "amount": float(payload.amount),
        "description": payload.description.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user.user_id),
        "username": user.username,
    })
    client.accounting_expenses = store
    status_store = dict(client.accounting_expense_status or {})
    if field_key == "prosthetist_work":
        status_store[field_key] = "paid" if payload.paid is not False else "unpaid"
    else:
        status_store.setdefault(field_key, "paid")
    client.accounting_expense_status = status_store
    _materialize_accounting_expense_total(db, client, field_key, _expense_total(entries))
    db.add(client)
    db.commit()
    db.refresh(client)
    return get_accounting_expense_history(db, client_id, field_key)


def _materialize_accounting_expense_total(db: Session, client: models.Client, field_key: str, total: float) -> None:
    """Keep legacy accounting columns/custom numeric values synchronized with history."""
    if field_key in ACCOUNTING_FIXED_EXPENSE_KEYS:
        setattr(client, field_key, total)
    elif field_key.startswith("custom:"):
        field_id = UUID(field_key.split(":", 1)[1])
        row = db.query(models.AccountingFieldValue).filter(
            models.AccountingFieldValue.client_id == client.client_id,
            models.AccountingFieldValue.field_id == field_id,
        ).first()
        if row:
            row.value_number = total
        else:
            db.add(models.AccountingFieldValue(client_id=client.client_id, field_id=field_id, value_number=total))


def _materialize_requested_legacy_entry(
    db: Session,
    client: models.Client,
    field_key: str,
    entry_id: str,
    entries: list[dict[str, Any]],
) -> None:
    """Turn the virtual legacy row into a real JSON row when it is targeted.

    This is the missing compatibility bridge that makes UPDATE/DELETE work for
    every fixed expense and every active custom numeric expense.
    """
    if entries or str(entry_id) != f"legacy-{field_key}":
        return
    legacy = _legacy_accounting_entry(db, client, field_key)
    if legacy:
        entries.append(legacy)


def update_accounting_expense(
    db: Session, client_id: UUID, field_key: str, entry_id: str, payload: schemas.AccountingExpenseUpdate
) -> dict[str, Any]:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    field_key = field_key.strip()
    if not _accounting_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _normalize_expense_store(client.accounting_expenses)
    entries = store.setdefault(field_key, [])
    _materialize_requested_legacy_entry(db, client, field_key, entry_id, entries)

    entry = next((item for item in entries if str(item.get("id")) == str(entry_id)), None)
    if not entry:
        raise ValueError("Расход не найден")

    entry["amount"] = float(payload.amount)
    entry["description"] = payload.description.strip()
    client.accounting_expenses = store
    _materialize_accounting_expense_total(db, client, field_key, _expense_total(entries))
    db.add(client)
    db.commit()
    db.refresh(client)
    return get_accounting_expense_history(db, client_id, field_key)


def delete_accounting_expense(db: Session, client_id: UUID, field_key: str, entry_id: str) -> dict[str, Any]:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    field_key = field_key.strip()
    if not _accounting_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _normalize_expense_store(client.accounting_expenses)
    entries = store.setdefault(field_key, [])
    _materialize_requested_legacy_entry(db, client, field_key, entry_id, entries)

    index = next((i for i, item in enumerate(entries) if str(item.get("id")) == str(entry_id)), None)
    if index is None:
        raise ValueError("Расход не найден")

    entries.pop(index)
    if entries:
        store[field_key] = entries
    else:
        store.pop(field_key, None)
    client.accounting_expenses = store
    _materialize_accounting_expense_total(db, client, field_key, _expense_total(entries))
    db.add(client)
    db.commit()
    db.refresh(client)
    return get_accounting_expense_history(db, client_id, field_key)


def set_accounting_expense_status(db: Session, client_id: UUID, field_key: str, paid: bool) -> dict[str, Any]:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Client not found")
    field_key = field_key.strip()
    if field_key != "prosthetist_work":
        raise ValueError("Payment status is available only for prosthetist work")
    if not _accounting_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")
    status_store = dict(client.accounting_expense_status or {})
    status_store[field_key] = "paid" if paid else "unpaid"
    client.accounting_expense_status = status_store
    db.add(client)
    db.commit()
    return get_accounting_expense_history(db, client_id, field_key)

# -------------------------
# Client
# -------------------------

def _normalize_reference_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _client_is_successfully_completed(db: Session, client: models.Client) -> bool:
    """Return True only for the explicit business state used for auto-archive."""
    status_code = _normalize_reference_text(client.status_code)
    stage_code = _normalize_reference_text(client.current_stage)

    if status_code == "success" and stage_code == "shipping":
        return True

    status = db.get(models.Status, client.status_code) if client.status_code else None
    stage = db.get(models.Stage, client.current_stage) if client.current_stage else None
    return (
        _normalize_reference_text(getattr(status, "description", None)) == "успешно завершен"
        and _normalize_reference_text(getattr(stage, "description", None)) == "выполнено"
    )


def _apply_client_archive_state(
    db: Session,
    client: models.Client,
    *,
    is_archived: bool,
) -> None:
    client.is_archived = is_archived
    module_update = update(models.Module).where(models.Module.client_id == client.client_id)
    if is_archived:
        module_update = module_update.values(is_archived=True)
    else:
        # Ручно архивированные позиции остаются в архиве после восстановления клиента.
        module_update = module_update.values(is_archived=models.Module.is_manually_archived)
    db.execute(module_update)


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
        contract_status=client_in.contract_status,
        act_status=client_in.act_status,
        agent_id=client_in.agent_id,
        deadline=client_in.deadline,
        notes=client_in.notes,
        check_date=client_in.check_date,
        prosthesis_type=client_in.prosthesis_type,
        email=client_in.email,
        certificate_price=client_in.certificate_price,
        taxation_system=client_in.taxation_system,
        place_of_residence=client_in.place_of_residence,
        prosthetist=client_in.prosthetist,
        ipra_code=client_in.ipra_code,
        tsr_code = client_in.tsr_code,
        prosthetist_work=client_in.prosthetist_work,
        patient_travel=client_in.patient_travel,
        patient_accommodation=client_in.patient_accommodation,
        patient_meals=client_in.patient_meals,
        patient_payment=client_in.patient_payment,
        other_expenses=client_in.other_expenses,
        agency_expenses=client_in.agency_expenses,
    )

    db.add(client)
    try:
        db.flush()  # чтобы client.client_id появился до commit
        for p in client_in.phones or []:
            phone = models.Phone(client_id=client.client_id, number=p.number)
            db.add(phone)

        if _client_is_successfully_completed(db, client):
            _apply_client_archive_state(db, client, is_archived=True)

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
            selectinload(models.Client.modules).selectinload(models.Module.tsr),
            selectinload(models.Client.tsr_items).selectinload(models.ClientTsr.tsr),
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
    archived: bool = False,
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
        selectinload(models.Client.modules).selectinload(models.Module.tsr),
        selectinload(models.Client.tsr_items).selectinload(models.ClientTsr.tsr),
        selectinload(models.Client.accounting_values).joinedload(models.AccountingFieldValue.field),
    )

    conditions = [models.Client.is_archived.is_(archived)]
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                models.Client.first_name.ilike(like),
                models.Client.last_name.ilike(like),
                models.Client.middle_name.ilike(like),
                models.Client.email.ilike(like),
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

    # The actual address is controlled by the selected prosthetist and cannot
    # be changed independently, including through a direct API request.
    payload.pop("place_of_residence", None)
    if "prosthetist" in payload:
        payload["place_of_residence"] = schemas.PROSTHETIST_ADDRESSES.get(payload.get("prosthetist"))

    # обновляются только существующие поля
    for k, v in payload.items():
        if hasattr(client, k):
            setattr(client, k, v)

    if not client.is_archived and _client_is_successfully_completed(db, client):
        _apply_client_archive_state(db, client, is_archived=True)

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

    # Важно: комплектующие — это складские позиции. При удалении клиента они не должны
    # удаляться каскадом; сначала отвязываем их и оставляем "на складе".
    linked_modules = db.execute(
        select(models.Module).where(models.Module.client_id == client_id)
    ).scalars().all()
    for module in linked_modules:
        module.client_id = None
        module.client_tsr_id = None
        module.is_archived = bool(module.is_manually_archived)
        module.is_in_stock = True

    db.flush()
    db.delete(client)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def set_client_archive_state(
    db: Session,
    client_id: UUID,
    *,
    is_archived: bool,
) -> Optional[Dict[str, Any]]:
    """Архивирует/восстанавливает клиента и все закрепленные за ним комплектующие."""
    client = db.get(models.Client, client_id)
    if not client:
        return None

    _apply_client_archive_state(db, client, is_archived=is_archived)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_client(db, client_id)


def assign_tsr_to_client_modules(
    db: Session,
    client_id: UUID,
    component_ids: List[UUID],
    tsr_id: UUID,
) -> List[models.Module]:
    """Атомарно назначает один ТСР выбранным существующим комплектующим клиента."""
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Клиент не найден")
    if client.is_archived:
        raise ValueError("Сначала восстановите клиента из архива")
    if not db.get(models.TstCodeRef, tsr_id):
        raise ValueError("Выбранный ТСР не найден")

    existing_link = db.execute(
        select(models.ClientTsr).where(
            models.ClientTsr.client_id == client_id,
            models.ClientTsr.tsr_id == tsr_id,
        ).order_by(models.ClientTsr.created_at, models.ClientTsr.client_tsr_id)
    ).scalars().first()
    if not existing_link:
        existing_link = models.ClientTsr(client_id=client_id, tsr_id=tsr_id)
        db.add(existing_link)
        db.flush()

    unique_ids = list(dict.fromkeys(component_ids))
    components = db.execute(
        select(models.Module).where(models.Module.module_id.in_(unique_ids))
    ).scalars().all()

    if len(components) != len(unique_ids):
        raise ValueError("Одна или несколько комплектующих не найдены")
    if any(component.client_id != client_id for component in components):
        raise ValueError("Все выбранные комплектующие должны принадлежать этому клиенту")

    for component in components:
        component.tsr_id = tsr_id
        component.client_tsr_id = existing_link.client_tsr_id

    try:
        db.flush()
        _sync_client_tsr_legacy_fields(db, client_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return db.execute(
        select(models.Module)
        .where(models.Module.module_id.in_(unique_ids))
        .options(
            selectinload(models.Module.client),
            selectinload(models.Module.tsr),
        )
    ).scalars().all()


def set_client_modules_prosthetist_state(
    db: Session,
    client_id: UUID,
    client_tsr_id: UUID,
    component_ids: List[UUID],
    *,
    at_prosthetist: bool,
) -> List[models.Module]:
    """Atomically mark selected components of one client TSR as at prosthetist.

    ``prosthetist_keep`` is the canonical warehouse counter, so updating the
    existing ``MODULES`` rows keeps the client card and warehouse in sync.
    """
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Клиент не найден")
    if client.is_archived:
        raise ValueError("Сначала восстановите клиента из архива")

    assignment = db.get(models.ClientTsr, client_tsr_id)
    if not assignment or assignment.client_id != client_id:
        raise ValueError("Выбранный ТСР не принадлежит клиенту")

    unique_ids = list(dict.fromkeys(component_ids))
    components = db.execute(
        select(models.Module)
        .where(models.Module.module_id.in_(unique_ids))
        .with_for_update()
    ).scalars().all()

    if len(components) != len(unique_ids):
        raise ValueError("Одна или несколько комплектующих не найдены")
    if any(component.client_id != client_id for component in components):
        raise ValueError("Все выбранные комплектующие должны принадлежать этому клиенту")
    if any(component.client_tsr_id != client_tsr_id for component in components):
        raise ValueError("Все выбранные комплектующие должны относиться к выбранному ТСР")
    if any(component.is_archived for component in components):
        raise ValueError("Сначала восстановите комплектующие из архива")

    for component in components:
        quantity = max(1, int(component.quantity or 1))
        component.prosthetist_keep = quantity if at_prosthetist else 0

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return db.execute(
        select(models.Module)
        .where(models.Module.module_id.in_(unique_ids))
        .options(
            selectinload(models.Module.client),
            selectinload(models.Module.tsr),
        )
    ).scalars().all()


def _parse_decimal_money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    text_value = str(value).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    text_value = re.sub(r"[^0-9.\-]", "", text_value)
    try:
        return Decimal(text_value or "0")
    except InvalidOperation:
        return Decimal("0")


def _format_decimal_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _sync_client_tsr_legacy_fields(db: Session, client_id: UUID) -> None:
    """Keep old client columns usable by legacy reports and IP templates."""
    client = db.get(models.Client, client_id)
    if not client:
        return
    links = db.execute(
        select(models.ClientTsr)
        .where(models.ClientTsr.client_id == client_id)
        .options(selectinload(models.ClientTsr.tsr))
        .order_by(models.ClientTsr.created_at, models.ClientTsr.client_tsr_id)
    ).scalars().all()
    client.tsr_code = "\n".join(
        str(link.tsr.full_tsr_code or "").strip()
        for link in links
        if link.tsr and str(link.tsr.full_tsr_code or "").strip()
    ) or None
    dated_links = [link.check_date for link in links if link.check_date is not None]
    client.check_date = max(dated_links) if dated_links else None
    total = sum((_parse_decimal_money(link.certificate_price) for link in links), Decimal("0"))
    client.certificate_price = _format_decimal_money(total) if links else None


def list_client_tsr(db: Session, client_id: UUID) -> List[models.ClientTsr]:
    if not db.get(models.Client, client_id):
        raise ValueError("Клиент не найден")
    return db.execute(
        select(models.ClientTsr)
        .where(models.ClientTsr.client_id == client_id)
        .options(selectinload(models.ClientTsr.tsr))
        .order_by(models.ClientTsr.created_at, models.ClientTsr.client_tsr_id)
    ).scalars().all()


def create_client_tsr(db: Session, client_id: UUID, payload: schemas.ClientTsrCreate) -> models.ClientTsr:
    client = db.get(models.Client, client_id)
    if not client:
        raise ValueError("Клиент не найден")
    if client.is_archived:
        raise ValueError("Сначала восстановите клиента из архива")
    tsr = db.get(models.TstCodeRef, payload.tsr_id)
    if not tsr:
        raise ValueError("Выбранный ТСР не найден")
    automatic_repeat_date = calculate_repeat_visit_date(tsr.full_tsr_code, payload.check_date)
    item = models.ClientTsr(
        client_id=client_id,
        tsr_id=payload.tsr_id,
        check_date=payload.check_date,
        certificate_price=(payload.certificate_price or None),
        prosthetist=payload.prosthetist,
        place_of_residence=schemas.PROSTHETIST_ADDRESSES.get(payload.prosthetist),
        # Повторная дата не принимается от клиента вручную: если срок для
        # выбранного ТСР есть в таблице Excel, вычисляем её; иначе оставляем пустой.
        repeat_visit_date=automatic_repeat_date,
    )
    db.add(item)
    try:
        db.flush()
        _sync_client_tsr_legacy_fields(db, client_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return db.execute(
        select(models.ClientTsr)
        .where(models.ClientTsr.client_tsr_id == item.client_tsr_id)
        .options(selectinload(models.ClientTsr.tsr))
    ).scalars().one()


def update_client_tsr(
    db: Session,
    client_id: UUID,
    client_tsr_id: UUID,
    payload: schemas.ClientTsrUpdate,
) -> Optional[models.ClientTsr]:
    item = db.execute(
        select(models.ClientTsr).where(
            models.ClientTsr.client_tsr_id == client_tsr_id,
            models.ClientTsr.client_id == client_id,
        )
    ).scalars().first()
    if not item:
        return None
    values = payload.model_dump(exclude_unset=True)
    # Поле повторной даты является серверным. Даже прямой API-запрос не должен
    # позволять вручную менять его. Для ТСР без правила сохраняем историческое
    # значение, если оно уже было в базе.
    values.pop("repeat_visit_date", None)
    for key, value in values.items():
        normalized_value = (value or None) if key == "certificate_price" else value
        setattr(item, key, normalized_value)
    if "prosthetist" in values:
        item.place_of_residence = schemas.PROSTHETIST_ADDRESSES.get(values.get("prosthetist"))

    # Для ТСР, которым соответствует нормативный срок из Excel, дата повторного
    # обращения всегда вычисляется сервером от даты пробития. Нормализация кода
    # считает 8-*, 8(1)-* и 8.1-* эквивалентными при одинаковой остальной части.
    # Ручное изменение repeat_visit_date через API игнорируется.
    tsr = db.get(models.TstCodeRef, item.tsr_id)
    if tsr and get_repeat_term_months(tsr.full_tsr_code) is not None:
        item.repeat_visit_date = calculate_repeat_visit_date(tsr.full_tsr_code, item.check_date)
    try:
        db.flush()
        _sync_client_tsr_legacy_fields(db, client_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return db.execute(
        select(models.ClientTsr)
        .where(models.ClientTsr.client_tsr_id == client_tsr_id)
        .options(selectinload(models.ClientTsr.tsr))
    ).scalars().one()


def delete_client_tsr(db: Session, client_id: UUID, client_tsr_id: UUID) -> bool:
    item = db.execute(
        select(models.ClientTsr).where(
            models.ClientTsr.client_tsr_id == client_tsr_id,
            models.ClientTsr.client_id == client_id,
        )
    ).scalars().first()
    if not item:
        return False
    used_count = db.scalar(
        select(func.count()).select_from(models.Module).where(
            models.Module.client_id == client_id,
            models.Module.client_tsr_id == item.client_tsr_id,
        )
    ) or 0
    if used_count:
        raise ValueError("Нельзя открепить ТСР: к нему привязаны комплектующие клиента")
    db.delete(item)
    try:
        db.flush()
        _sync_client_tsr_legacy_fields(db, client_id)
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
        first_name=agent_in.first_name,
        middle_name=agent_in.middle_name,
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
    # Lock the client row so two simultaneous requests cannot create duplicates.
    client = db.execute(
        select(models.Client).where(models.Client.client_id == client_id).with_for_update()
    ).scalars().first()
    if not client:
        raise ValueError("Client not found")
    if db.scalar(select(func.count()).select_from(models.Passport).where(models.Passport.client_id == client_id)):
        raise ValueError("У клиента уже сохранён паспорт. Измените существующий документ.")
    
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
    # The same lock protects the single SNILS/IPRA record from concurrent creates.
    client = db.execute(
        select(models.Client).where(models.Client.client_id == client_id).with_for_update()
    ).scalars().first()
    if not client:
        raise ValueError("Client not found")
    if db.scalar(select(func.count()).select_from(models.Snils).where(models.Snils.client_id == client_id)):
        raise ValueError("У клиента уже сохранены СНИЛС / ИПРА. Измените существующий документ.")
        
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
    client_id = snils.client_id
    remaining_count = db.scalar(
        select(func.count()).select_from(models.Snils).where(
            models.Snils.client_id == client_id,
            models.Snils.snils_id != snils_id,
        )
    ) or 0
    if remaining_count == 0:
        client = db.get(models.Client, client_id)
        if client:
            client.ipra_code = None
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

def _resolve_module_client_tsr(
    db: Session,
    *,
    client_id: UUID,
    tsr_id: UUID,
    client_tsr_id: UUID | None,
    create_if_missing: bool = True,
) -> models.ClientTsr:
    """Resolve the concrete client↔TSR instance used by a component.

    Duplicate TSR codes are allowed, therefore an explicit ``client_tsr_id`` is
    mandatory as soon as more than one matching assignment exists.
    """
    if client_tsr_id:
        assignment = db.execute(
            select(models.ClientTsr).where(
                models.ClientTsr.client_tsr_id == client_tsr_id,
                models.ClientTsr.client_id == client_id,
            )
        ).scalars().first()
        if not assignment:
            raise ValueError("Выбранный ТСР не принадлежит клиенту")
        if assignment.tsr_id != tsr_id:
            raise ValueError("Код комплектующей не совпадает с выбранным ТСР клиента")
        return assignment

    assignments = db.execute(
        select(models.ClientTsr)
        .where(
            models.ClientTsr.client_id == client_id,
            models.ClientTsr.tsr_id == tsr_id,
        )
        .order_by(models.ClientTsr.created_at, models.ClientTsr.client_tsr_id)
    ).scalars().all()
    if len(assignments) == 1:
        return assignments[0]
    if len(assignments) > 1:
        raise ValueError("У клиента несколько одинаковых ТСР. Выберите нужную карточку ТСР.")
    if not create_if_missing:
        raise ValueError("Выбранный ТСР не прикреплён к клиенту")

    assignment = models.ClientTsr(client_id=client_id, tsr_id=tsr_id)
    db.add(assignment)
    db.flush()
    _sync_client_tsr_legacy_fields(db, client_id)
    return assignment


def _validate_module_operation_quantity(source: models.Module, requested_quantity: int | None) -> tuple[int, int]:
    """Return ``(available, requested)`` for an operation over identical units."""
    available = max(1, int(source.quantity or 1))
    requested = 1 if requested_quantity is None else int(requested_quantity)
    if requested < 1:
        raise ValueError("Количество для операции должно быть не меньше 1")
    if requested > available:
        raise ValueError(f"Доступно только {available} шт.")
    return available, requested


def _split_module_count_value(
    value: int | None,
    detached_quantity: int,
) -> tuple[int, int]:
    """Split a legacy aggregate counter while preserving its total value.

    Counters such as ``ordered``/``recd`` historically live on the same row as
    ``quantity``.  Each detached physical unit receives at most one counter unit,
    which preserves the behaviour of the previous one-unit split and keeps the
    aggregate totals unchanged.
    """
    current = max(0, int(value or 0))
    detached = min(current, max(0, int(detached_quantity)))
    return current - detached, detached


def _split_module_money_value(
    value: float | None,
    total_quantity: int,
    detached_quantity: int,
) -> tuple[float | None, float | None]:
    """Return ``(remaining_total, detached_total)`` for an aggregate money field."""
    if value is None:
        return None, None
    total = float(value)
    detached = total * detached_quantity / total_quantity
    return total - detached, detached


def _detach_module_units(
    db: Session,
    source: models.Module,
    requested_quantity: int | None = None,
) -> models.Module:
    """Detach an arbitrary number of identical physical units from ``source``.

    The selected row keeps its UUID and becomes the detached portion.  When only
    part of the aggregate is selected, a new row is created for the untouched
    remainder in exactly the same warehouse/client/archive state.  Money totals
    are divided proportionally so the sum across both rows remains unchanged.
    """
    available, detached_quantity = _validate_module_operation_quantity(source, requested_quantity)

    # Normalize historical rows with quantity 0/NULL before any operation.
    if int(source.quantity or 0) != available:
        source.quantity = available

    if detached_quantity == available:
        return source

    remaining_quantity = available - detached_quantity
    remaining_cost, detached_cost = _split_module_money_value(source.cost, available, detached_quantity)
    remaining_price, detached_price = _split_module_money_value(source.price, available, detached_quantity)
    remaining_ordered, detached_ordered = _split_module_count_value(source.ordered, detached_quantity)
    remaining_recd, detached_recd = _split_module_count_value(source.recd, detached_quantity)
    remaining_pending, detached_pending = _split_module_count_value(source.pending, detached_quantity)
    remaining_keep, detached_keep = _split_module_count_value(source.prosthetist_keep, detached_quantity)

    remainder = models.Module(
        client_id=source.client_id,
        tsr_id=source.tsr_id,
        client_tsr_id=source.client_tsr_id,
        module_name_index=source.module_name_index,
        supplier=source.supplier,
        ordered=remaining_ordered,
        order_date_acc_num=source.order_date_acc_num,
        quantity=remaining_quantity,
        size=source.size,
        stiffness=source.stiffness,
        side=source.side,
        cost=remaining_cost,
        price=remaining_price,
        recd=remaining_recd,
        pending=remaining_pending,
        prosthetist_keep=remaining_keep,
        properties=source.properties,
        notes=source.notes,
        is_archived=bool(source.is_archived),
        is_manually_archived=bool(source.is_manually_archived),
        is_in_stock=bool(source.is_in_stock),
        accounting_cost_excluded=bool(source.accounting_cost_excluded),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )

    source.quantity = detached_quantity
    source.cost = detached_cost
    source.price = detached_price
    source.ordered = detached_ordered
    source.recd = detached_recd
    source.pending = detached_pending
    source.prosthetist_keep = detached_keep

    db.add(remainder)
    db.add(source)
    db.flush()
    return source


def _remove_module_units(
    db: Session,
    source: models.Module,
    requested_quantity: int | None = None,
) -> None:
    """Delete the requested number of physical units and preserve the remainder."""
    target = _detach_module_units(db, source, requested_quantity)
    db.delete(target)

def create_module(db: Session, module_in: schemas.ModuleCreate) -> models.Module:
    """Создает комплектующую. Проверяет клиента, если ID передан."""
    # Если client_id передан (не None), проверяем, существует ли такой клиент
    client = None
    if module_in.client_id:
        client = db.get(models.Client, module_in.client_id)
        if not client:
            raise ValueError(f"Client with id {module_in.client_id} not found")

    if module_in.tsr_id and not db.get(models.TstCodeRef, module_in.tsr_id):
        raise ValueError("Выбранный ТСР не найден")

    data = module_in.model_dump()
    name_ref = ensure_module_name_index(db, data.get("module_name_index"))
    data["module_name_index"] = name_ref.name_index
    if client and module_in.tsr_id:
        assignment = _resolve_module_client_tsr(
            db,
            client_id=client.client_id,
            tsr_id=module_in.tsr_id,
            client_tsr_id=module_in.client_tsr_id,
        )
        data["client_tsr_id"] = assignment.client_tsr_id
    else:
        data["client_tsr_id"] = None

    # Создаем объект модели
    db_module = models.Module(
        **data,
        is_archived=bool(client.is_archived) if client else False,
        is_manually_archived=False,
        is_in_stock=client is None,
        accounting_cost_excluded=False,
    )

    db.add(db_module)
    try:
        db.commit()
        db.refresh(db_module)
        return db_module
    except Exception:
        db.rollback()
        raise

def get_module(db: Session, module_id: UUID) -> Optional[models.Module]:
    return db.execute(
        select(models.Module)
        .where(models.Module.module_id == module_id)
        .options(
            selectinload(models.Module.client),
            selectinload(models.Module.tsr),
        )
    ).scalars().first()

def list_modules(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    q: Optional[str] = None, 
    supplier: Optional[str] = None, 
    client_id: Optional[UUID] = None,
    unassigned: bool = False,
    archived: bool = False,
    in_stock: Optional[bool] = None,
) -> List[models.Module]:
    
    stmt = select(models.Module).options(
        selectinload(models.Module.client),
        selectinload(models.Module.tsr),
    )

    # условия фильтрации
    conditions = [models.Module.is_archived.is_(archived)]
    if q:
        conditions.append(models.Module.module_name_index.ilike(f"%{q}%"))
    if supplier:
        conditions.append(models.Module.supplier.ilike(f"%{supplier}%"))
    if client_id:
        conditions.append(models.Module.client_id == client_id)
    elif unassigned:
        conditions.append(models.Module.client_id.is_(None))
    if in_stock is not None:
        conditions.append(models.Module.is_in_stock.is_(in_stock))
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(models.Module.updated_at.desc())
    stmt = stmt.offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()


def count_stock_module_units(db: Session) -> int:
    """Количество свободных единиц комплектующих на отдельной вкладке «Склад»."""
    quantity = case(
        (models.Module.quantity > 0, models.Module.quantity),
        else_=1,
    )
    value = db.scalar(
        select(func.coalesce(func.sum(quantity), 0)).where(
            models.Module.client_id.is_(None),
            models.Module.is_archived.is_(False),
            models.Module.is_in_stock.is_(True),
        )
    )
    return int(value or 0)

def update_module(
    db: Session,
    module_id: UUID,
    payload: schemas.ModuleUpdate,
    *,
    operation_quantity: int | None = None,
) -> Optional[models.Module]:
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return None

    # DBCRM_UPDATE_20260831: direct stock assignment
    # Capture the source state before splitting/moving the row.  Accounting is
    # excluded only when the user assigns the item directly from «Склад», not
    # from «Рабочий склад».
    was_in_stock = bool(db_module.is_in_stock)
    was_accounting_excluded = bool(db_module.accounting_cost_excluded)
    data = payload.model_dump(exclude_unset=True)
    
    # Если меняем владельца
    if 'client_id' in data:
        if data['client_id'] is None:
            data['is_archived'] = bool(db_module.is_manually_archived)
            data['is_in_stock'] = True
        else:
            client = db.get(models.Client, data['client_id'])
            if not client:
                raise ValueError("Target client not found")
            data['is_archived'] = bool(client.is_archived or db_module.is_manually_archived)
            data['is_in_stock'] = False

    if 'tsr_id' in data:
        if data['tsr_id'] is not None and not db.get(models.TstCodeRef, data['tsr_id']):
            raise ValueError("Выбранный ТСР не найден")

    final_client_id = data.get('client_id', db_module.client_id)
    final_tsr_id = data.get('tsr_id', db_module.tsr_id)
    explicit_assignment = 'client_tsr_id' in data
    assignment_id = data.get('client_tsr_id') if explicit_assignment else db_module.client_tsr_id
    if not explicit_assignment and (
        final_client_id != db_module.client_id or final_tsr_id != db_module.tsr_id
    ):
        assignment_id = None

    if final_client_id is None:
        data['client_tsr_id'] = None
    else:
        if final_tsr_id is None:
            data['client_tsr_id'] = None
        else:
            assignment = _resolve_module_client_tsr(
                db,
                client_id=final_client_id,
                tsr_id=final_tsr_id,
                client_tsr_id=assignment_id,
            )
            data['client_tsr_id'] = assignment.client_tsr_id
            data['tsr_id'] = assignment.tsr_id

    if 'module_name_index' in data:
        name_ref = ensure_module_name_index(db, data.get('module_name_index'))
        data['module_name_index'] = name_ref.name_index

    # A warehouse row may represent several identical physical units. When its
    # owner or concrete client↔TSR assignment changes, only the quantity selected
    # for that operation must move. Ordinary form edits are applied to the
    # aggregate first, then the selected portion is detached so money/count
    # totals remain consistent.
    client_state_changes = (
        ('client_id' in data and data.get('client_id') != db_module.client_id)
        or (
            operation_quantity is not None
            and (
                ('client_tsr_id' in data and data.get('client_tsr_id') != db_module.client_tsr_id)
                or ('tsr_id' in data and data.get('tsr_id') != db_module.tsr_id)
            )
        )
    )

    if client_state_changes:
        state_keys = {'client_id', 'tsr_id', 'client_tsr_id', 'is_archived', 'is_in_stock'}
        aggregate_data = {key: value for key, value in data.items() if key not in state_keys}
        state_data = {key: value for key, value in data.items() if key in state_keys}

        for key, value in aggregate_data.items():
            setattr(db_module, key, value)

        target_module = _detach_module_units(db, db_module, operation_quantity)
        data = state_data
    else:
        target_module = db_module

    for k, v in data.items():
        setattr(target_module, k, v)

    if 'client_id' in data and target_module.client_id is not None:
        target_module.accounting_cost_excluded = bool(was_in_stock or was_accounting_excluded)

    db.add(target_module)
    try:
        db.commit()
        db.refresh(target_module)
        return get_module(db, target_module.module_id)
    except Exception:
        db.rollback()
        raise

def delete_module(db: Session, module_id: UUID, *, quantity: int = 1) -> bool:
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return False
    try:
        _remove_module_units(db, db_module, quantity)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def set_module_archive_state(
    db: Session,
    module_id: UUID,
    *,
    is_archived: bool,
    quantity: int = 1,
) -> Optional[models.Module]:
    """Архивирует комплектующую независимо от состояния карточки клиента."""
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return None

    if not is_archived and db_module.client_id:
        owner = db.get(models.Client, db_module.client_id)
        if owner and owner.is_archived:
            raise ValueError("Сначала восстановите клиента из архива")

    target_module = _detach_module_units(db, db_module, quantity)
    target_module.is_manually_archived = is_archived
    target_module.is_archived = is_archived

    try:
        db.commit()
        db.refresh(target_module)
    except Exception:
        db.rollback()
        raise

    return get_module(db, target_module.module_id)


def set_module_stock_state(
    db: Session,
    module_id: UUID,
    *,
    is_in_stock: bool,
    quantity: int = 1,
) -> Optional[models.Module]:
    """Перемещает активную комплектующую между Рабочим складом и вкладкой «Склад».

    При отправке на «Склад» комплектующая становится бесхозной, но её ТСР (если
    он был указан) сохраняется. Возврат в Рабочий склад не назначает владельца.
    """
    db_module = db.get(models.Module, module_id)
    if not db_module:
        return None
    if db_module.is_archived:
        raise ValueError("Сначала восстановите комплектующую из Списанных комплектующих")

    target_module = _detach_module_units(db, db_module, quantity)

    if is_in_stock:
        target_module.client_id = None
        target_module.client_tsr_id = None
        target_module.is_in_stock = True
        target_module.accounting_cost_excluded = False
    else:
        target_module.is_in_stock = False
        target_module.accounting_cost_excluded = False

    try:
        db.commit()
        db.refresh(target_module)
    except Exception:
        db.rollback()
        raise

    return get_module(db, target_module.module_id)


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
    name = (name or "").strip()
    if not name:
        raise ValueError("Название вида протеза не может быть пустым.")

    exists = db.execute(select(models.ProsthesisRef).where(models.ProsthesisRef.name == name)).scalars().first()
    if exists:
        return exists

    new_prosthesis = models.ProsthesisRef(name=name)
    db.add(new_prosthesis)
    db.commit()
    db.refresh(new_prosthesis)
    return new_prosthesis

def update_prosthesis(db: Session, prosthesis_id: UUID, name: str):
    name = (name or "").strip()
    if not name:
        raise ValueError("Название вида протеза не может быть пустым.")

    item = db.get(models.ProsthesisRef, prosthesis_id)
    if not item:
        return None

    old_name = (item.name or "").strip()
    if old_name == name:
        return item

    existing = db.execute(select(models.ProsthesisRef).where(models.ProsthesisRef.name == name)).scalars().first()
    if existing and existing.prosthesis_id != prosthesis_id:
        db.query(models.Client).filter(models.Client.prosthesis_type == old_name).update(
            {models.Client.prosthesis_type: name},
            synchronize_session=False,
        )
        db.delete(item)
        db.commit()
        db.refresh(existing)
        return existing

    linked_clients = db.execute(
        select(func.count()).select_from(models.Client).where(models.Client.prosthesis_type == old_name)
    ).scalar_one()

    if linked_clients:
        replacement = models.ProsthesisRef(name=name)
        db.add(replacement)
        db.flush()
        db.query(models.Client).filter(models.Client.prosthesis_type == old_name).update(
            {models.Client.prosthesis_type: name},
            synchronize_session=False,
        )
        db.delete(item)
        db.commit()
        db.refresh(replacement)
        return replacement

    item.name = name
    db.commit()
    db.refresh(item)
    return item

def delete_prosthesis(db: Session, prosthesis_id: UUID):
    prosthesis_to_delete = db.get(models.ProsthesisRef, prosthesis_id)
    if not prosthesis_to_delete:
        return False

    linked_clients = db.execute(
        select(func.count()).select_from(models.Client).where(models.Client.prosthesis_type == prosthesis_to_delete.name)
    ).scalar_one()
    if linked_clients:
        raise ValueError("Этот вид протеза используется в карточках клиентов. Сначала замените его в клиентах или переименуйте справочник.")

    db.delete(prosthesis_to_delete)
    db.commit()
    return True

def get_tsr(db: Session):
    return db.execute(select(models.TstCodeRef).order_by(models.TstCodeRef.full_tsr_code)).scalars().all()

def create_tsr(db: Session, full_tsr_code: str):
    full_tsr_code = (full_tsr_code or "").strip()
    if not full_tsr_code:
        raise ValueError("Код ТСР не может быть пустым.")

    exists = db.execute(select(models.TstCodeRef).where(models.TstCodeRef.full_tsr_code == full_tsr_code)).scalars().first()
    if exists:
        return exists

    new_tsr = models.TstCodeRef(full_tsr_code=full_tsr_code)
    db.add(new_tsr)
    db.commit()
    db.refresh(new_tsr)
    return new_tsr

def _replace_tsr_code_in_clients(db: Session, old_code: str, new_code: str):
    if not old_code or old_code == new_code:
        return

    clients = db.execute(select(models.Client).where(models.Client.tsr_code.isnot(None))).scalars().all()
    for client in clients:
        raw_value = client.tsr_code or ""
        parts = [part.strip() for part in raw_value.replace(";", "\n").splitlines()]
        changed = False
        replaced_parts = []

        for part in parts:
            if not part:
                continue
            if part == old_code:
                replaced_parts.append(new_code)
                changed = True
            else:
                replaced_parts.append(part)

        if changed:
            client.tsr_code = "\n".join(dict.fromkeys(replaced_parts))

def update_tsr(db: Session, tsr_id: UUID, full_tsr_code: str):
    full_tsr_code = (full_tsr_code or "").strip()
    if not full_tsr_code:
        raise ValueError("Код ТСР не может быть пустым.")

    item = db.get(models.TstCodeRef, tsr_id)
    if not item:
        return None

    old_code = (item.full_tsr_code or "").strip()
    if old_code == full_tsr_code:
        return item

    existing = db.execute(select(models.TstCodeRef).where(models.TstCodeRef.full_tsr_code == full_tsr_code)).scalars().first()
    if existing and existing.tsr_id != tsr_id:
        affected_client_ids: set[UUID] = set()
        links = db.execute(
            select(models.ClientTsr).where(models.ClientTsr.tsr_id == tsr_id)
        ).scalars().all()
        for link in links:
            affected_client_ids.add(link.client_id)
            duplicate = db.execute(
                select(models.ClientTsr).where(
                    models.ClientTsr.client_id == link.client_id,
                    models.ClientTsr.tsr_id == existing.tsr_id,
                )
            ).scalars().first()
            if duplicate:
                if link.check_date and (
                    not duplicate.check_date or link.check_date > duplicate.check_date
                ):
                    duplicate.check_date = link.check_date
                combined_price = (
                    _parse_decimal_money(duplicate.certificate_price)
                    + _parse_decimal_money(link.certificate_price)
                )
                duplicate.certificate_price = (
                    _format_decimal_money(combined_price)
                    if combined_price
                    else None
                )
                db.delete(link)
            else:
                link.tsr_id = existing.tsr_id
        _replace_tsr_code_in_clients(db, old_code, full_tsr_code)
        db.execute(
            update(models.Module)
            .where(models.Module.tsr_id == tsr_id)
            .values(tsr_id=existing.tsr_id)
        )
        db.flush()
        for client_id in affected_client_ids:
            _sync_client_tsr_legacy_fields(db, client_id)
        db.delete(item)
        db.commit()
        db.refresh(existing)
        return existing

    item.full_tsr_code = full_tsr_code
    _replace_tsr_code_in_clients(db, old_code, full_tsr_code)
    db.commit()
    db.refresh(item)
    return item

def delete_tsr(db: Session, tsr_id: UUID):
    tsr_to_delete = db.get(models.TstCodeRef, tsr_id)
    if tsr_to_delete:
        linked_modules = db.execute(
            select(func.count()).select_from(models.Module).where(models.Module.tsr_id == tsr_id)
        ).scalar_one()
        if linked_modules:
            raise ValueError("Этот ТСР используется в комплектующих. Сначала назначьте им другой ТСР.")
        linked_clients = db.execute(
            select(func.count()).select_from(models.ClientTsr).where(models.ClientTsr.tsr_id == tsr_id)
        ).scalar_one()
        if linked_clients:
            raise ValueError("Этот ТСР прикреплён к клиентам. Сначала открепите его в карточках клиентов.")
        db.delete(tsr_to_delete)
        db.commit()
        return True
    else:
        return False


# -------------------------
# ModuleNameIndex
# -------------------------

def _normalize_module_name_index(value: str | None) -> str:
    return " ".join(str(value or "").split())

def get_module_name_index(db: Session):
    return db.execute(select(models.ModuleNameIndex).order_by(models.ModuleNameIndex.name_index)).scalars().all()

def _find_module_name_index(db: Session, name_index: str):
    normalized = _normalize_module_name_index(name_index)
    if not normalized:
        return None
    return db.execute(
        select(models.ModuleNameIndex).where(
            func.lower(models.ModuleNameIndex.name_index) == normalized.lower()
        )
    ).scalars().first()

def ensure_module_name_index(db: Session, name_index: str) -> models.ModuleNameIndex:
    """Вернуть запись справочника или создать её внутри текущей транзакции."""
    normalized = _normalize_module_name_index(name_index)
    if not normalized:
        raise ValueError("Название и индекс комплектующей не могут быть пустыми.")
    existing = _find_module_name_index(db, normalized)
    if existing:
        return existing
    item = models.ModuleNameIndex(name_index=normalized)
    db.add(item)
    db.flush()
    return item

def create_module_name_index(db: Session, name_index: str):
    try:
        item = ensure_module_name_index(db, name_index)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise

def update_module_name_index(db: Session, name_index_id: UUID, name_index: str):
    item = db.get(models.ModuleNameIndex, name_index_id)
    if not item:
        return None
    normalized = _normalize_module_name_index(name_index)
    if not normalized:
        raise ValueError("Название и индекс комплектующей не могут быть пустыми.")
    old_name = str(item.name_index or "")
    if old_name == normalized:
        return item

    try:
        target = _find_module_name_index(db, normalized)
        if target and target.name_index_id != name_index_id:
            replacement = target
        else:
            # В MODULES внешний ключ ссылается на текст REF_NameIndex.name_index.
            # Поэтому сначала создаём новое допустимое значение, затем переводим
            # связанные комплектующие и только после этого удаляем старую запись.
            replacement = models.ModuleNameIndex(name_index=normalized)
            db.add(replacement)
            db.flush()

        db.execute(
            update(models.Module)
            .where(models.Module.module_name_index == old_name)
            .values(module_name_index=replacement.name_index)
        )
        db.delete(item)
        db.commit()
        db.refresh(replacement)
        return replacement
    except Exception:
        db.rollback()
        raise

def delete_module_name_index(db: Session, name_index_id: UUID):
    item = db.get(models.ModuleNameIndex, name_index_id)
    if not item:
        return False
    linked = db.scalar(
        select(func.count()).select_from(models.Module).where(
            models.Module.module_name_index == item.name_index
        )
    ) or 0
    if linked:
        raise ValueError(
            f"Нельзя удалить запись: она используется в комплектующих ({linked})."
        )
    db.delete(item)
    db.commit()
    return True

# -------------------------
# Accounting Custom Fields
# -------------------------



def _parse_custom_number(value: Any, field_name: str) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if raw == "":
        return None

    normalized = (
        raw.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace(" ", "")
        .replace("−", "-")
        .replace(",", ".")
    )
    cleaned = re.sub(r"[^0-9.\-]", "", normalized)
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Поле '{field_name}' должно быть числом. Получено: {raw}") from exc

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
    for upd in updates:
        field_id = upd["field_id"]
        value = upd.get("value")
        field = db.get(models.AccountingCustomField, field_id)
        if not field:
            continue
        stmt = select(models.AccountingFieldValue).where(
            models.AccountingFieldValue.client_id == client_id,
            models.AccountingFieldValue.field_id == field_id
        )
        existing = db.execute(stmt).scalars().first()
        if field.field_type == 'number':
            parsed_number = _parse_custom_number(value, field.field_name)
            if existing:
                existing.value_number = parsed_number
                existing.value_text = None
            else:
                new_val = models.AccountingFieldValue(
                    client_id=client_id,
                    field_id=field_id,
                    value_number=parsed_number,
                    value_text=None,
                )
                db.add(new_val)
        else:
            parsed_text = str(value) if value is not None else None
            if existing:
                existing.value_text = parsed_text
                existing.value_number = None
            else:
                new_val = models.AccountingFieldValue(
                    client_id=client_id,
                    field_id=field_id,
                    value_number=None,
                    value_text=parsed_text,
                )
                db.add(new_val)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

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
