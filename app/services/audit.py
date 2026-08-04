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


ENTITY_LABELS = {
    "client": "Клиент",
    "component": "Комплектующая",
    "agent": "Агент",
    "user": "Пользователь",
    "reference": "Справочник",
    "accounting_field": "Поле бухгалтерии",
    "system": "Системный справочник",
}

MISSING_ID_LABELS = {
    "agent_id": "Удалённый агент",
    "client_id": "Удалённый клиент",
    "module_id": "Удалённая комплектующая",
    "component_id": "Удалённая комплектующая",
    "tsr_id": "Удалённый код ТСР",
    "user_id": "Удалённый пользователь",
    "document_id": "Удалённый документ",
    "field_id": "Удалённое поле",
    "prosthesis_id": "Удалённый вид протеза",
    "name_index_id": "Удалённое название комплектующей",
}


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


def _as_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _person_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = (value.get("last_name"), value.get("first_name"), value.get("middle_name"))
    else:
        parts = (
            getattr(value, "last_name", None),
            getattr(value, "first_name", None),
            getattr(value, "middle_name", None),
        )
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())


def _component_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("module_name_index") or value.get("properties") or "").strip()
    return str(
        getattr(value, "module_name_index", None)
        or getattr(value, "properties", None)
        or ""
    ).strip()


def _subject_from_snapshot(entity: str, value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if entity in {"client", "agent"}:
        return _person_name(value)
    if entity == "component":
        return _component_name(value)
    if entity == "user":
        return str(value.get("username") or "").strip()
    if entity == "reference":
        return str(
            value.get("full_tsr_code")
            or value.get("name")
            or value.get("name_index")
            or value.get("description")
            or ""
        ).strip()
    if entity == "accounting_field":
        return str(value.get("field_name") or "").strip()
    if entity == "system":
        return str(
            value.get("description")
            or value.get("status_code")
            or value.get("stage_code")
            or ""
        ).strip()
    return ""


def _lookup_subject(db: Session, entity: str, entity_id: Any) -> str:
    parsed_id = _as_uuid(entity_id)
    if parsed_id is None:
        return ""

    if entity == "client":
        return _person_name(db.get(models.Client, parsed_id))
    if entity == "agent":
        return _person_name(db.get(models.Agent, parsed_id))
    if entity == "component":
        return _component_name(db.get(models.Module, parsed_id))
    if entity == "user":
        user = db.get(models.User, parsed_id)
        return str(user.username).strip() if user else ""
    if entity == "accounting_field":
        field = db.get(models.AccountingCustomField, parsed_id)
        return str(field.field_name).strip() if field else ""
    if entity == "reference":
        tsr = db.get(models.TstCodeRef, parsed_id)
        if tsr:
            return str(tsr.full_tsr_code or "").strip()
        prosthesis = db.get(models.ProsthesisRef, parsed_id)
        if prosthesis:
            return str(prosthesis.name or "").strip()
        name_index = db.get(models.ModuleNameIndex, parsed_id)
        if name_index:
            return str(name_index.name_index or "").strip()
    return ""


def _lookup_id_label(db: Session, field_name: str, value: Any) -> str | None:
    parsed_id = _as_uuid(value)
    if parsed_id is None:
        return None

    if field_name == "agent_id":
        return _person_name(db.get(models.Agent, parsed_id)) or None
    if field_name == "client_id":
        return _person_name(db.get(models.Client, parsed_id)) or None
    if field_name in {"module_id", "component_id"}:
        return _component_name(db.get(models.Module, parsed_id)) or None
    if field_name == "tsr_id":
        tsr = db.get(models.TstCodeRef, parsed_id)
        return str(tsr.full_tsr_code).strip() if tsr and tsr.full_tsr_code else None
    if field_name == "user_id":
        user = db.get(models.User, parsed_id)
        return str(user.username).strip() if user else None
    if field_name == "document_id":
        document = db.get(models.Document, parsed_id)
        return str(document.filename).strip() if document else None
    if field_name == "field_id":
        field = db.get(models.AccountingCustomField, parsed_id)
        return str(field.field_name).strip() if field else None
    if field_name == "prosthesis_id":
        prosthesis = db.get(models.ProsthesisRef, parsed_id)
        return str(prosthesis.name).strip() if prosthesis and prosthesis.name else None
    if field_name == "name_index_id":
        name_index = db.get(models.ModuleNameIndex, parsed_id)
        return str(name_index.name_index).strip() if name_index and name_index.name_index else None
    return None


def _humanize_value(db: Session, field_name: str, value: Any) -> Any:
    if value is None:
        return None

    if field_name == "status_code":
        status = db.get(models.Status, str(value))
        return status.description if status else value
    if field_name == "current_stage":
        stage = db.get(models.Stage, str(value))
        return stage.description if stage else value
    if field_name == "component_ids" and isinstance(value, list):
        return [
            _lookup_id_label(db, "component_id", item) or "Удалённая комплектующая"
            for item in value
        ]
    if field_name == "custom_values" and isinstance(value, dict):
        return {
            _lookup_id_label(db, "field_id", key) or "Удалённое поле": _humanize_value(
                db,
                "custom_value",
                nested_value,
            )
            for key, nested_value in value.items()
        }

    id_label = _lookup_id_label(db, field_name, value)
    if id_label:
        return id_label
    if field_name in MISSING_ID_LABELS and _as_uuid(value) is not None:
        return MISSING_ID_LABELS[field_name]

    if isinstance(value, dict):
        return {
            key: _humanize_value(db, str(key), nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_humanize_value(db, field_name, item) for item in value]
    return value


def _module_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names = [_component_name(item) for item in value]
    return [name for name in names if name]


def _enrich_details(
    db: Session,
    *,
    entity: str,
    entity_id: Any,
    details: Any,
) -> dict[str, Any] | None:
    raw = dict(details) if isinstance(details, dict) else {}
    before = raw.get("before")
    after = raw.get("after")
    subject_name = (
        str(raw.get("subject_name") or "").strip()
        or _lookup_subject(db, entity, entity_id)
        or _subject_from_snapshot(entity, after)
        or _subject_from_snapshot(entity, before)
    )

    raw.setdefault("subject_label", ENTITY_LABELS.get(entity, "Запись"))
    if subject_name:
        raw["subject_name"] = subject_name

    before_modules = before.get("modules") if isinstance(before, dict) else None
    after_modules = after.get("modules") if isinstance(after, dict) else None
    related_components = _module_names(after_modules) or _module_names(before_modules)
    if related_components:
        raw["related_components"] = related_components

    for key in ("before", "after"):
        if key in raw:
            raw[key] = _humanize_value(db, key, raw[key])

    for key in ("tsr_id", "component_ids", "client_id", "agent_id", "document_id", "field_id"):
        if key in raw:
            raw[key] = _humanize_value(db, key, raw[key])

    return raw or None


def _serialize_log(db: Session, log: models.AuditLog) -> dict[str, Any]:
    return {
        "log_id": log.log_id,
        "entity": log.entity,
        "entity_id": log.entity_id,
        "action": log.action,
        "user_id": log.user_id,
        "timestamp": log.timestamp,
        "details": _enrich_details(
            db,
            entity=log.entity,
            entity_id=log.entity_id,
            details=log.details,
        ),
    }


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
    payload = _enrich_details(
        db,
        entity=entity,
        entity_id=entity_id,
        details=payload,
    ) or {}

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
) -> list[dict[str, Any]]:
    stmt = (
        select(models.AuditLog)
        .where(models.AuditLog.entity == entity, models.AuditLog.entity_id == entity_id)
        .order_by(models.AuditLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return [_serialize_log(db, log) for log in db.execute(stmt).scalars().all()]


def list_recent_audit(db: Session, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    stmt = select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit)
    return [_serialize_log(db, log) for log in db.execute(stmt).scalars().all()]
