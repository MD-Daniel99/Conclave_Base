# app/services/audit.py
"""Сервис аудита изменений для CRM.

Лог пишется в существующую таблицу AUDIT_LOG. Из-за текущей архитектуры CRUD-функции
сами выполняют commit(), поэтому аудит фиксируется отдельной транзакцией после успешного
изменения. При переходе на сервисный слой можно будет объединить изменение и аудит в одну
транзакцию.
"""
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__table__"):
        data = {}
        for column in value.__table__.columns:
            try:
                data[column.name] = _safe_json(getattr(value, column.name))
            except Exception:
                data[column.name] = None
        return data
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(v) for v in value]
    try:
        return jsonable_encoder(value)
    except Exception:
        return str(value)


def snapshot(value: Any) -> Any:
    """Публичная обертка для фиксации состояния объекта до изменения/удаления."""
    return _safe_json(value)


def log_action(
    db: Session,
    *,
    entity: str,
    entity_id: UUID,
    action: str,
    user: Optional[models.User],
    before: Any = None,
    after: Any = None,
    details: Optional[dict[str, Any]] = None,
) -> models.AuditLog:
    payload = details.copy() if details else {}
    if user is not None:
        payload.setdefault("actor_username", user.username)
        payload.setdefault("actor_role", user.role)
    if before is not None:
        payload["before"] = _safe_json(before)
    if after is not None:
        payload["after"] = _safe_json(after)

    log = models.AuditLog(
        entity=entity,
        entity_id=entity_id,
        action=action,
        user_id=str(user.user_id) if user is not None else "system",
        details=payload or None,
    )
    db.add(log)
    try:
        db.commit()
        db.refresh(log)
        return log
    except Exception:
        db.rollback()
        raise


def list_audit_for_entity(
    db: Session,
    *,
    entity: str,
    entity_id: UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[models.AuditLog]:
    stmt = (
        select(models.AuditLog)
        .where(models.AuditLog.entity == entity, models.AuditLog.entity_id == entity_id)
        .order_by(models.AuditLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def list_recent_audit(db: Session, *, skip: int = 0, limit: int = 100) -> list[models.AuditLog]:
    stmt = select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()
