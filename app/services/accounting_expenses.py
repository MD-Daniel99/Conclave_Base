"""Detailed contract-accounting expense CRUD with legacy compatibility.

This module is intentionally small and isolated from the report builder.  It
supports every fixed accounting expense plus every active custom numeric field.
Old pre-detailing values are represented as ``legacy-<field_key>`` rows and are
materialized lazily when the user edits, deletes, or adds detail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app import models


FIXED_EXPENSE_KEYS = frozenset({
    "prosthetist_work",
    "patient_travel",
    "patient_accommodation",
    "patient_meals",
    "patient_payment",
    "other_expenses",
    "agency_expenses",
})
CONTRACT_EXPENSE_HISTORY_KEY = "__expense_history__"


def _parse_number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _get_accounting(db: Session, document_id: UUID) -> models.ContractAccounting:
    accounting = (
        db.query(models.ContractAccounting)
        .filter(models.ContractAccounting.document_id == document_id)
        .first()
    )
    if not accounting:
        raise ValueError("Contract accounting row not found")
    return accounting


def _field_exists(db: Session, field_key: str) -> bool:
    if field_key in FIXED_EXPENSE_KEYS:
        return True
    if not field_key.startswith("custom:"):
        return False
    try:
        field_id = UUID(field_key.split(":", 1)[1])
    except (ValueError, IndexError):
        return False
    field = db.get(models.AccountingCustomField, field_id)
    return bool(field and field.is_active and field.field_type == "number")


def _history_store(accounting: models.ContractAccounting) -> dict[str, dict[str, Any]]:
    values = accounting.custom_values if isinstance(accounting.custom_values, dict) else {}
    history = values.get(CONTRACT_EXPENSE_HISTORY_KEY)
    if not isinstance(history, dict):
        return {}
    return {
        str(key): dict(value)
        for key, value in history.items()
        if isinstance(value, dict)
    }


def _state_entries(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("entries", [])
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _is_paid(state: dict[str, Any]) -> bool:
    value = state.get("paid", "paid")
    if isinstance(value, bool):
        return value
    return str(value).lower() != "unpaid"


def _legacy_value(accounting: models.ContractAccounting, field_key: str) -> float:
    if field_key in FIXED_EXPENSE_KEYS:
        return _parse_number(getattr(accounting, field_key, 0.0))
    if field_key.startswith("custom:"):
        field_id = field_key.split(":", 1)[1]
        values = accounting.custom_values if isinstance(accounting.custom_values, dict) else {}
        return _parse_number(values.get(field_id, 0.0))
    return 0.0


def _legacy_entry(accounting: models.ContractAccounting, field_key: str) -> dict[str, Any] | None:
    amount = _legacy_value(accounting, field_key)
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


def _expense_total(entries: list[dict[str, Any]]) -> float:
    return sum(_parse_number(item.get("amount")) for item in entries)


def _write_history(accounting: models.ContractAccounting, store: dict[str, dict[str, Any]]) -> None:
    values = dict(accounting.custom_values or {})
    values[CONTRACT_EXPENSE_HISTORY_KEY] = store
    accounting.custom_values = values


def _materialize_total(accounting: models.ContractAccounting, field_key: str, total: float) -> None:
    if field_key in FIXED_EXPENSE_KEYS:
        setattr(accounting, field_key, total)
        return
    if field_key.startswith("custom:"):
        values = dict(accounting.custom_values or {})
        values[field_key.split(":", 1)[1]] = total
        accounting.custom_values = values


def _materialize_requested_legacy(
    accounting: models.ContractAccounting,
    field_key: str,
    entry_id: str,
    entries: list[dict[str, Any]],
) -> None:
    if entries or str(entry_id) != f"legacy-{field_key}":
        return
    legacy = _legacy_entry(accounting, field_key)
    if legacy:
        entries.append(legacy)


def get_contract_expense_history(db: Session, document_id: UUID, field_key: str) -> dict[str, Any]:
    field_key = field_key.strip()
    accounting = _get_accounting(db, document_id)
    if not _field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = _state_entries(state)
    if not entries:
        legacy = _legacy_entry(accounting, field_key)
        if legacy:
            entries = [legacy]

    return {
        "field_key": field_key,
        "total": _expense_total(entries),
        "paid": _is_paid(state),
        "entries": entries,
    }


def add_contract_expense(db: Session, document_id: UUID, payload: Any, user: models.User) -> dict[str, Any]:
    accounting = _get_accounting(db, document_id)
    field_key = str(payload.field_key).strip()
    if not _field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = _state_entries(state)

    # Preserve the pre-detailing amount as the first real history row.
    if not entries:
        legacy = _legacy_entry(accounting, field_key)
        if legacy:
            entries.append(legacy)

    entries.append({
        "id": str(uuid4()),
        "amount": float(payload.amount),
        "description": str(payload.description).strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user.user_id),
        "username": user.username,
    })

    paid = True if field_key != "prosthetist_work" else payload.paid is not False
    store[field_key] = {"entries": entries, "paid": paid}
    _write_history(accounting, store)
    _materialize_total(accounting, field_key, _expense_total(entries))
    db.add(accounting)
    db.commit()
    db.refresh(accounting)
    return get_contract_expense_history(db, document_id, field_key)


def set_contract_expense_status(db: Session, document_id: UUID, field_key: str, paid: bool) -> dict[str, Any]:
    field_key = field_key.strip()
    if field_key != "prosthetist_work":
        raise ValueError("Payment status is available only for prosthetist work")

    accounting = _get_accounting(db, document_id)
    store = _history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = _state_entries(state)
    if not entries:
        legacy = _legacy_entry(accounting, field_key)
        if legacy:
            entries.append(legacy)

    store[field_key] = {"entries": entries, "paid": bool(paid)}
    _write_history(accounting, store)
    db.add(accounting)
    db.commit()
    db.refresh(accounting)
    return get_contract_expense_history(db, document_id, field_key)


def update_contract_expense(
    db: Session,
    document_id: UUID,
    field_key: str,
    entry_id: str,
    payload: Any,
) -> dict[str, Any]:
    field_key = field_key.strip()
    accounting = _get_accounting(db, document_id)
    if not _field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = _state_entries(state)
    _materialize_requested_legacy(accounting, field_key, entry_id, entries)

    target = next((item for item in entries if str(item.get("id")) == str(entry_id)), None)
    if target is None:
        raise ValueError("Расход не найден")

    target["amount"] = float(payload.amount)
    target["description"] = str(payload.description).strip()
    store[field_key] = {"entries": entries, "paid": _is_paid(state)}
    _write_history(accounting, store)
    _materialize_total(accounting, field_key, _expense_total(entries))
    db.add(accounting)
    db.commit()
    db.refresh(accounting)
    return get_contract_expense_history(db, document_id, field_key)


def delete_contract_expense(db: Session, document_id: UUID, field_key: str, entry_id: str) -> dict[str, Any]:
    field_key = field_key.strip()
    accounting = _get_accounting(db, document_id)
    if not _field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")

    store = _history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = _state_entries(state)
    _materialize_requested_legacy(accounting, field_key, entry_id, entries)

    index = next((i for i, item in enumerate(entries) if str(item.get("id")) == str(entry_id)), None)
    if index is None:
        raise ValueError("Расход не найден")

    entries.pop(index)
    store[field_key] = {"entries": entries, "paid": _is_paid(state)}
    _write_history(accounting, store)
    _materialize_total(accounting, field_key, _expense_total(entries))
    db.add(accounting)
    db.commit()
    db.refresh(accounting)
    return get_contract_expense_history(db, document_id, field_key)
