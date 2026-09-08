from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Any, Iterable

from sqlalchemy.orm import Session, selectinload

from app import models


GENERATED_DOCUMENT_TYPES = frozenset({
    "llc_contract",
    "dmk_contract",
    "dmk_instrument",
    "contract_original",
    "contract_template",
    "sdv_contract",
})
CONTRACT_DOCUMENT_TYPES = frozenset({"llc_contract", "dmk_contract", "sdv_contract"})
FIXED_EXPENSE_KEYS = (
    "prosthetist_work",
    "patient_travel",
    "patient_accommodation",
    "patient_meals",
    "patient_payment",
    "other_expenses",
    "agency_expenses",
 )


def accounting_expense_entries(client: models.Client, field_key: str) -> list[dict[str, Any]]:
    store = client.accounting_expenses if isinstance(client.accounting_expenses, dict) else {}
    entries = store.get(field_key, []) if isinstance(store.get(field_key, []), list) else []
    return [item for item in entries if isinstance(item, dict)]


def accounting_expense_total(client: models.Client, field_key: str) -> float:
    entries = accounting_expense_entries(client, field_key)
    if entries:
        return sum(parse_number(item.get("amount")) for item in entries)
    return parse_number(getattr(client, field_key, 0.0)) if field_key in FIXED_EXPENSE_KEYS else 0.0


def accounting_expense_payment_state(client: models.Client, field_key: str) -> str:
    if field_key != "prosthetist_work":
        return "paid"
    entries = accounting_expense_entries(client, field_key)
    status_store = client.accounting_expense_status if isinstance(client.accounting_expense_status, dict) else {}
    legacy_paid = str(status_store.get(field_key, "paid")).lower() != "unpaid"
    if not entries:
        return "paid" if legacy_paid else "unpaid"
    states = [bool(item.get("paid", legacy_paid)) for item in entries]
    if all(states): return "paid"
    if not any(states): return "unpaid"
    return "partial"

def accounting_expense_paid(client: models.Client, field_key: str) -> bool:
    return accounting_expense_payment_state(client, field_key) == "paid"

CONTRACT_EXPENSE_HISTORY_KEY = "__expense_history__"


def _contract_history_store(accounting: models.ContractAccounting) -> dict[str, dict[str, Any]]:
    values = accounting.custom_values if isinstance(accounting.custom_values, dict) else {}
    history = values.get(CONTRACT_EXPENSE_HISTORY_KEY)
    return dict(history) if isinstance(history, dict) else {}


def _contract_field_exists(db: Session, field_key: str) -> bool:
    if field_key in FIXED_EXPENSE_KEYS:
        return True
    if not field_key.startswith("custom:"):
        return False
    try:
        field_id = UUID(field_key.split(":", 1)[1])
    except ValueError:
        return False
    field = db.get(models.AccountingCustomField, field_id)
    return bool(field and field.is_active and field.field_type == "number")


def _contract_legacy_value(accounting: models.ContractAccounting, field_key: str) -> float:
    if field_key in FIXED_EXPENSE_KEYS:
        return parse_number(getattr(accounting, field_key, 0.0))
    if field_key.startswith("custom:"):
        field_id = field_key.split(":", 1)[1]
        return parse_number((accounting.custom_values or {}).get(field_id, 0.0))
    return 0.0


def _contract_legacy_entry(field_key: str, amount: float) -> dict[str, Any] | None:
    if amount <= 0:
        return None
    return {"id": f"legacy-{field_key}", "amount": amount, "description": "Сумма до включения детализации", "created_at": None, "user_id": None, "username": None}


def _contract_expense_total(entries: list[dict[str, Any]]) -> float:
    return sum(parse_number(item.get("amount")) for item in entries)


def get_contract_expense_history(db: Session, document_id: UUID, field_key: str) -> dict[str, Any]:
    accounting = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == document_id).first()
    if not accounting:
        raise ValueError("Contract accounting row not found")
    if not _contract_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")
    store = _contract_history_store(accounting)
    state = store.get(field_key) if isinstance(store.get(field_key), dict) else {}
    raw_entries = state.get("entries", [])
    entries = [dict(item) for item in raw_entries if isinstance(item, dict)] if isinstance(raw_entries, list) else []
    if not entries:
        legacy = _contract_legacy_entry(field_key, _contract_legacy_value(accounting, field_key))
        if legacy:
            entries = [legacy]
    legacy_paid = str(state.get("paid", "paid")).lower() != "unpaid"
    if field_key == "prosthetist_work":
        for entry in entries:
            entry.setdefault("paid", legacy_paid)
        paid = all(bool(entry.get("paid", True)) for entry in entries)
    else:
        paid = True
    return {"field_key": field_key, "total": _contract_expense_total(entries), "paid": paid, "entries": entries}


def _write_contract_history(accounting: models.ContractAccounting, store: dict[str, dict[str, Any]]) -> None:
    values = dict(accounting.custom_values or {})
    values[CONTRACT_EXPENSE_HISTORY_KEY] = store
    accounting.custom_values = values


def _materialize_contract_expense(accounting: models.ContractAccounting, field_key: str, total: float) -> None:
    if field_key in FIXED_EXPENSE_KEYS:
        setattr(accounting, field_key, total)
        return
    if field_key.startswith("custom:"):
        values = dict(accounting.custom_values or {})
        values[field_key.split(":", 1)[1]] = total
        accounting.custom_values = values


def add_contract_expense(db: Session, document_id: UUID, payload: Any, user: models.User) -> dict[str, Any]:
    accounting = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == document_id).first()
    if not accounting:
        raise ValueError("Contract accounting row not found")
    field_key = payload.field_key.strip()
    if not _contract_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")
    store = _contract_history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = [dict(item) for item in state.get("entries", []) if isinstance(item, dict)]
    if not entries:
        legacy = _contract_legacy_entry(field_key, _contract_legacy_value(accounting, field_key))
        if legacy:
            if field_key == "prosthetist_work":
                legacy["paid"] = str(state.get("paid", "paid")).lower() != "unpaid"
            entries.append(legacy)
    entries.append({"id": str(uuid4()), "amount": float(payload.amount), "description": payload.description.strip(), "created_at": datetime.now(timezone.utc).isoformat(), "user_id": str(user.user_id), "username": user.username, "paid": (payload.paid is not False) if field_key == "prosthetist_work" else True})
    paid = True if field_key != "prosthetist_work" else all(bool(item.get("paid", True)) for item in entries)
    store[field_key] = {"entries": entries, "paid": paid}
    _write_contract_history(accounting, store)
    _materialize_contract_expense(accounting, field_key, _contract_expense_total(entries))
    db.commit()
    return get_contract_expense_history(db, document_id, field_key)


def set_contract_expense_status(db: Session, document_id: UUID, field_key: str, paid: bool) -> dict[str, Any]:
    if field_key != "prosthetist_work":
        raise ValueError("Payment status is available only for prosthetist work")
    accounting = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == document_id).first()
    if not accounting:
        raise ValueError("Contract accounting row not found")
    store = _contract_history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = [dict(item) for item in state.get("entries", []) if isinstance(item, dict)]
    if not entries:
        legacy = _contract_legacy_entry(field_key, _contract_legacy_value(accounting, field_key))
        if legacy:
            entries.append(legacy)
    for entry in entries:
        entry["paid"] = bool(paid)
    store[field_key] = {"entries": entries, "paid": bool(paid)}
    _write_contract_history(accounting, store)
    db.commit()
    return get_contract_expense_history(db, document_id, field_key)


def update_contract_expense(db: Session, document_id: UUID, field_key: str, entry_id: str, payload: Any) -> dict[str, Any]:
    accounting = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == document_id).first()
    if not accounting:
        raise ValueError("Contract accounting row not found")
    if not _contract_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")
    store = _contract_history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = [dict(item) for item in state.get("entries", []) if isinstance(item, dict)]
    if not entries:
        legacy = _contract_legacy_entry(field_key, _contract_legacy_value(accounting, field_key))
        if legacy:
            if field_key == "prosthetist_work":
                legacy["paid"] = str(state.get("paid", "paid")).lower() != "unpaid"
            entries.append(legacy)
    target = next((item for item in entries if str(item.get("id")) == entry_id), None)
    if target is None:
        raise ValueError("Expense entry not found")
    target["amount"] = float(payload.amount)
    target["description"] = payload.description.strip()
    if field_key == "prosthetist_work" and payload.paid is not None:
        target["paid"] = bool(payload.paid)
    paid = True if field_key != "prosthetist_work" else all(bool(item.get("paid", True)) for item in entries)
    store[field_key] = {"entries": entries, "paid": paid}
    _write_contract_history(accounting, store)
    _materialize_contract_expense(accounting, field_key, _contract_expense_total(entries))
    db.commit()
    return get_contract_expense_history(db, document_id, field_key)


def delete_contract_expense(db: Session, document_id: UUID, field_key: str, entry_id: str) -> dict[str, Any]:
    accounting = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == document_id).first()
    if not accounting:
        raise ValueError("Contract accounting row not found")
    if not _contract_field_exists(db, field_key):
        raise ValueError("Unknown accounting expense field")
    store = _contract_history_store(accounting)
    state = dict(store.get(field_key) or {})
    entries = [dict(item) for item in state.get("entries", []) if isinstance(item, dict)]
    if not entries:
        legacy = _contract_legacy_entry(field_key, _contract_legacy_value(accounting, field_key))
        if legacy:
            if field_key == "prosthetist_work":
                legacy["paid"] = str(state.get("paid", "paid")).lower() != "unpaid"
            entries.append(legacy)
    new_entries = [item for item in entries if str(item.get("id")) != entry_id]
    if len(new_entries) == len(entries):
        raise ValueError("Expense entry not found")
    store[field_key] = {"entries": new_entries, "paid": str(state.get("paid", "paid")).lower() != "unpaid"}
    _write_contract_history(accounting, store)
    _materialize_contract_expense(accounting, field_key, _contract_expense_total(new_entries))
    db.commit()
    return get_contract_expense_history(db, document_id, field_key)


def calculate_financials(
    revenue: float,
    *,
    component_cost: float,
    fixed_expenses: float,
    custom_expenses: float,
    tax_percent: float,
    acquiring_percent: float,
    vat_percent: float,
) -> dict[str, float]:
    """Calculate one independent payment operation in the required order.

    1. Extract VAT from the VAT-inclusive certificate amount.
    2. Determine revenue without VAT.
    3. Calculate acquiring from the full certificate amount.
    4. Calculate USN from ``revenue_without_vat - all deductible expenses - acquiring``.
    5. Subtract component cost, all other expenses, acquiring and USN
       from the certificate amount to obtain net profit.

    Every contract calls this function separately; values from one certificate
    never reduce another certificate.
    """
    revenue = parse_number(revenue)
    component_cost = parse_number(component_cost)
    fixed_expenses = parse_number(fixed_expenses)
    custom_expenses = parse_number(custom_expenses)
    tax_percent = max(0.0, parse_number(tax_percent))
    acquiring_percent = max(0.0, parse_number(acquiring_percent))
    vat_percent = max(0.0, parse_number(vat_percent))

    vat = revenue * (vat_percent / (100.0 + vat_percent)) if revenue and vat_percent else 0.0
    revenue_without_vat = revenue - vat
    acquiring = revenue * (acquiring_percent / 100.0)
    tax_base = max(
        0.0,
        revenue_without_vat
        - component_cost
        - fixed_expenses
        - custom_expenses
        - acquiring,
    )
    tax = tax_base * (tax_percent / 100.0)
    profit = (
        revenue_without_vat
        - component_cost
        - fixed_expenses
        - custom_expenses
        - acquiring
        - tax
    )
    return {
        "revenue_without_vat": revenue_without_vat,
        "tax_base": tax_base,
        "vat": vat,
        "tax": tax,
        "acquiring": acquiring,
        "profit": profit,
    }


def build_accounting_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    hide_failed: bool = True,
    tax_percent: float | None = None,
    tax_usn_percent: float | None = None,
    tax_osno_percent: float = 15.0,
    acquiring_percent: float = 1.0,
    vat_percent: float = 20.0,
) -> dict[str, Any]:
    """Build accounting totals per client from normalized certificate records.

    When CLIENT_TSR rows exist, their certificate prices are the source of
    truth. The legacy CLIENT.certificate_price/check_date fields are used only
    for clients that have no normalized certificate rows yet.
    """
    effective_usn_percent = resolve_usn_percent(tax_percent, tax_usn_percent)
    clients = (
        db.query(models.Client)
        .options(
            selectinload(models.Client.agent),
            selectinload(models.Client.modules),
            selectinload(models.Client.tsr_items).selectinload(models.ClientTsr.tsr),
            selectinload(models.Client.accounting_values).selectinload(models.AccountingFieldValue.field),
        )
        .all()
    )
    custom_fields = load_custom_fields(db)
    field_by_id = {field["key"]: field for field in custom_fields}

    rows: list[dict[str, Any]] = []
    totals = {
        "revenue": 0.0,
        "cost": 0.0,
        "salary": 0.0,
        "custom_expenses": 0.0,
        "vat": 0.0,
        "tax": 0.0,
        "acquiring": 0.0,
        "profit": 0.0,
    }

    for client in clients:
        if hide_failed and is_failed_client(client):
            continue

        certificate_items = client_certificate_items(client)
        visible_certificates = [
            item for item in certificate_items
            if date_in_range(item["date"], start_date, end_date)
        ]
        if (start_date or end_date) and not visible_certificates:
            continue

        revenue = sum(item["amount"] for item in visible_certificates)
        selected_certificate_ids = {
            item["certificate_id"] for item in visible_certificates if item["certificate_id"]
        }
        has_normalized_certificates = any(item["certificate_id"] for item in certificate_items)
        modules_cost = sum_client_module_cost(
            client.modules or [],
            selected_certificate_ids=selected_certificate_ids,
            date_filter_active=bool(start_date or end_date),
            has_normalized_certificates=has_normalized_certificates,
        )
        stock_reused_cost = sum_client_stock_reused_cost(
            client.modules or [],
            selected_certificate_ids=selected_certificate_ids,
            date_filter_active=bool(start_date or end_date),
            has_normalized_certificates=has_normalized_certificates,
        )

        # Payment status is informational.  Work performed by the prosthetist
        # is an expense regardless of whether that payable has already been paid.
        expenses = {
            key: accounting_expense_total(client, key)
            for key in FIXED_EXPENSE_KEYS
        }
        fixed_expenses = sum(expenses.values())
        custom_values = load_client_custom_values(client)
        normalized_custom_values: dict[str, Any] = {}
        custom_expenses = 0.0
        for field_id, raw_value in custom_values.items():
            field = field_by_id.get(field_id)
            if field is None:
                continue
            if field["type"] == "number":
                expense_key = f"custom:{field_id}"
                entries = accounting_expense_entries(client, expense_key)
                value: Any = (sum(parse_number(item.get("amount")) for item in entries) if entries else parse_number(raw_value))
                custom_expenses += value
            else:
                value = "" if raw_value is None else str(raw_value)
            normalized_custom_values[field_id] = value

        applied_tax_percent = tax_percent_for_client(
            client,
            tax_usn_percent=effective_usn_percent,
            tax_osno_percent=tax_osno_percent,
        )
        financials = calculate_financials(
            revenue,
            component_cost=modules_cost,
            fixed_expenses=fixed_expenses,
            custom_expenses=custom_expenses,
            tax_percent=applied_tax_percent,
            acquiring_percent=acquiring_percent,
            vat_percent=vat_percent,
        )
        latest_date = max(
            (item["date"] for item in visible_certificates if item["date"]),
            default=None,
        )
        row = {
            "client": serialize_client(client, latest_date),
            "amounts": {
                "revenue": revenue,
                "cost": modules_cost,
                "stock_reused_cost": stock_reused_cost,
                "salary": fixed_expenses,
                "custom_expenses": custom_expenses,
                "tax_percent": applied_tax_percent,
                **financials,
            },
            "expenses": expenses,
            "custom_values": normalized_custom_values,
            "certificates": [
                {
                    "certificate_id": item["certificate_id"],
                    "amount": item["amount"],
                    "date": item["date"].isoformat() if item["date"] else None,
                    "tsr": item["tsr"],
                }
                for item in visible_certificates
            ],
        }
        rows.append(row)
        for key in totals:
            totals[key] += row["amounts"][key]

    rows.sort(key=lambda row: (row["client"]["full_name"].casefold(), row["client"]["client_id"]))
    return {
        "filters": report_filters(
            start_date=start_date,
            end_date=end_date,
            hide_failed=hide_failed,
            tax_usn_percent=effective_usn_percent,
            tax_osno_percent=tax_osno_percent,
            acquiring_percent=acquiring_percent,
            vat_percent=vat_percent,
        ),
        "custom_fields": custom_fields,
        "rows": rows,
        "totals": totals,
    }


def build_contract_accounting_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    hide_failed: bool = True,
    tax_percent: float | None = None,
    tax_usn_percent: float | None = None,
    tax_osno_percent: float = 15.0,
    acquiring_percent: float = 1.0,
    vat_percent: float = 20.0,
) -> dict[str, Any]:
    """Build an independent accounting row for every current contract.

    A contract never consumes another contract's certificate balance. VAT,
    USN and acquiring are calculated for every payment operation. Duplicate
    generated documents for the same certificate are collapsed to the newest
    row even before the database uniqueness migration has been applied.
    """
    effective_usn_percent = resolve_usn_percent(tax_percent, tax_usn_percent)
    records = (
        db.query(models.ContractAccounting)
        .options(
            selectinload(models.ContractAccounting.document)
            .selectinload(models.Document.client)
            .selectinload(models.Client.modules),
            selectinload(models.ContractAccounting.document)
            .selectinload(models.Document.client)
            .selectinload(models.Client.tsr_items),
            selectinload(models.ContractAccounting.document)
            .selectinload(models.Document.certificate)
            .selectinload(models.ClientTsr.tsr),
        )
        .order_by(models.ContractAccounting.created_at.desc(), models.ContractAccounting.accounting_id.desc())
        .all()
    )
    custom_fields = load_custom_fields(db)
    numeric_field_ids = {field["key"] for field in custom_fields if field["type"] == "number"}
    rows: list[dict[str, Any]] = []
    seen_certificate_keys: set[str] = set()

    for accounting in records:
        document = accounting.document
        if not document or not document.client:
            continue
        if str(document.document_type or "").strip().lower() not in CONTRACT_DOCUMENT_TYPES:
            continue
        client = document.client
        if hide_failed and is_failed_client(client):
            continue

        certificate = resolve_contract_certificate(document, client)
        if certificate["key"] in seen_certificate_keys:
            continue
        seen_certificate_keys.add(certificate["key"])
        certificate_date = certificate["date"]
        if not date_in_range(certificate_date, start_date, end_date):
            continue

        metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
        modules_cost = contract_components_cost(document, client.modules or [])
        stock_reused_cost = contract_stock_reused_cost(document, client.modules or [])
        fixed_expenses_by_key = {
            key: parse_number(getattr(accounting, key, 0.0))
            for key in FIXED_EXPENSE_KEYS
        }
        contract_history = _contract_history_store(accounting)
        prosthetist_state = contract_history.get("prosthetist_work") if isinstance(contract_history.get("prosthetist_work"), dict) else {}
        prosthetist_entries = [dict(item) for item in prosthetist_state.get("entries", []) if isinstance(item, dict)]
        # Status paid/unpaid remains visible, but never removes the expense.
        fixed_expenses = sum(fixed_expenses_by_key.values())
        custom_values = accounting.custom_values or {}
        report_custom_values = {key: value for key, value in custom_values.items() if key != CONTRACT_EXPENSE_HISTORY_KEY}
        custom_expenses = sum(
            parse_number(value)
            for field_id, value in custom_values.items()
            if field_id in numeric_field_ids
        )
        applied_tax_percent = tax_percent_for_client(
            client,
            tax_usn_percent=effective_usn_percent,
            tax_osno_percent=tax_osno_percent,
        )
        financials = calculate_financials(
            certificate["amount"],
            component_cost=modules_cost,
            fixed_expenses=fixed_expenses,
            custom_expenses=custom_expenses,
            tax_percent=applied_tax_percent,
            acquiring_percent=acquiring_percent,
            vat_percent=vat_percent,
        )
        document_date = normalize_date(metadata.get("document_date")) or normalize_date(document.created_at)
        rows.append({
            "document": {
                "document_id": str(document.document_id),
                "filename": document.filename,
                "document_number": document.document_number,
                "document_type": document.document_type,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "date": document_date.isoformat() if document_date else None,
                "certificate_id": certificate["certificate_id"],
                "certificate_date": certificate_date.isoformat() if certificate_date else None,
            },
            "client": {
                "client_id": str(client.client_id),
                "full_name": " ".join(part for part in (client.last_name, client.first_name, client.middle_name) if part),
                "short_name": short_client_name(client),
                "status": client.status_code,
                "current_stage": client.current_stage,
                "taxation_system": normalize_taxation_system(client.taxation_system),
            },
            "amounts": {
                "certificate": certificate["amount"],
                "modules_cost": modules_cost,
                "stock_reused_cost": stock_reused_cost,
                **fixed_expenses_by_key,
                "custom_expenses": custom_expenses,
                "tax_percent": applied_tax_percent,
                **financials,
            },
            "custom_values": report_custom_values,
            "expense_status": {
                "prosthetist_work": (
                    "partial" if prosthetist_entries and any(bool(item.get("paid", str(prosthetist_state.get("paid", "paid")).lower() != "unpaid")) for item in prosthetist_entries) and not all(bool(item.get("paid", str(prosthetist_state.get("paid", "paid")).lower() != "unpaid")) for item in prosthetist_entries)
                    else "paid" if (all(bool(item.get("paid", str(prosthetist_state.get("paid", "paid")).lower() != "unpaid")) for item in prosthetist_entries) if prosthetist_entries else str(prosthetist_state.get("paid", "paid")).lower() != "unpaid")
                    else "unpaid"
                ),
            },
        })

    rows.sort(
        key=lambda row: (
            row["document"]["created_at"] or "",
            row["document"]["document_id"],
        ),
        reverse=True,
    )
    amount_keys = [
        "certificate", "modules_cost", "stock_reused_cost", *FIXED_EXPENSE_KEYS,
        "custom_expenses", "vat", "tax", "acquiring", "profit",
    ]
    totals = {key: sum(parse_number(row["amounts"].get(key)) for row in rows) for key in amount_keys}
    return {
        "filters": report_filters(
            start_date=start_date,
            end_date=end_date,
            hide_failed=hide_failed,
            tax_usn_percent=effective_usn_percent,
            tax_osno_percent=tax_osno_percent,
            acquiring_percent=acquiring_percent,
            vat_percent=vat_percent,
        ),
        "custom_fields": custom_fields,
        "rows": rows,
        "totals": totals,
    }


def resolve_contract_certificate(document: models.Document, client: models.Client) -> dict[str, Any]:
    metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
    snapshots = [
        item for item in (metadata.get("selected_tsr_components") or [])
        if isinstance(item, dict)
    ] if isinstance(metadata.get("selected_tsr_components"), list) else []

    # A single generated contract may cover several concrete client↔TSR
    # certificates. Keep it as one accounting operation, but use the sum of
    # all selected certificate prices and expose every covered certificate id.
    if len(snapshots) > 1:
        linked_by_id = {str(item.client_tsr_id): item for item in (client.tsr_items or [])}
        certificate_ids: list[str] = []
        amounts: list[float] = []
        dates: list[date] = []
        for item in snapshots:
            certificate_id = str(item.get("client_tsr_id") or "").strip()
            linked = linked_by_id.get(certificate_id) if certificate_id else None
            if certificate_id:
                certificate_ids.append(certificate_id)

            amount = parse_number(linked.certificate_price) if linked else 0.0
            if amount <= 0:
                amount = parse_number(item.get("certificate_price"))
            amounts.append(amount)

            certificate_date = normalize_date(linked.check_date) if linked else None
            if certificate_date is None:
                certificate_date = normalize_date(item.get("check_date"))
            if certificate_date is not None:
                dates.append(certificate_date)

        amount = sum(amounts)
        if amount <= 0:
            amount = parse_number(document.certificate_amount)
        if amount <= 0:
            amount = parse_number(client.certificate_price)

        unique_ids = sorted(set(certificate_ids))
        key = (
            f"certificates:{','.join(unique_ids)}"
            if unique_ids
            else f"document:{document.document_id}"
        )
        return {
            "certificate_id": None,
            "certificate_ids": unique_ids,
            "amount": amount,
            "date": max(dates) if dates else normalize_date(document.created_at),
            "key": key,
        }

    snapshot = single_tsr_snapshot(metadata)
    linked = document.certificate
    certificate_id = str(document.certificate_id or "") or str(snapshot.get("client_tsr_id") or "")

    if not linked and certificate_id:
        linked = next(
            (item for item in (client.tsr_items or []) if str(item.client_tsr_id) == certificate_id),
            None,
        )
    if not linked and snapshot:
        snapshot_tsr_id = str(snapshot.get("tsr_id") or "")
        snapshot_date = normalize_date(snapshot.get("check_date"))
        snapshot_amount = parse_number(snapshot.get("certificate_price") or document.certificate_amount)
        candidates = [
            item for item in (client.tsr_items or [])
            if (not snapshot_tsr_id or str(item.tsr_id) == snapshot_tsr_id)
            and (not snapshot_date or normalize_date(item.check_date) == snapshot_date)
            and (not snapshot_amount or abs(parse_number(item.certificate_price) - snapshot_amount) < 0.01)
        ]
        if len(candidates) == 1:
            linked = candidates[0]
            certificate_id = str(linked.client_tsr_id)

    amount = parse_number(linked.certificate_price) if linked else 0.0
    if amount <= 0:
        amount = parse_number(snapshot.get("certificate_price")) if snapshot else 0.0
    if amount <= 0:
        amount = parse_number(document.certificate_amount)
    if amount <= 0:
        amount = parse_number(client.certificate_price)

    certificate_date = normalize_date(linked.check_date) if linked else None
    if certificate_date is None and snapshot:
        certificate_date = normalize_date(snapshot.get("check_date"))
    if certificate_date is None:
        certificate_date = normalize_date(client.check_date)

    if certificate_id:
        key = f"certificate:{certificate_id}"
    elif snapshot:
        tsr_id = str(snapshot.get("tsr_id") or "")
        key = f"snapshot:{client.client_id}:{tsr_id}:{certificate_date}:{amount:.2f}"
    else:
        key = f"document:{document.document_id}"
    return {
        "certificate_id": certificate_id or None,
        "certificate_ids": [certificate_id] if certificate_id else [],
        "amount": amount,
        "date": certificate_date,
        "key": key,
    }


def _contract_component_cost_breakdown(
    document: models.Document,
    client_modules: Iterable[models.Module],
) -> tuple[float, float]:
    """Return (new expense cost, previously bought Stock cost)."""
    metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
    current_by_id = {str(module.module_id): module for module in client_modules}

    def split(items: list[dict[str, Any]]) -> tuple[float, float]:
        included = 0.0
        reused = 0.0
        for item in items:
            cost = parse_number(item.get("cost"))
            component_id = str(item.get("component_id") or item.get("module_id") or "")
            current = current_by_id.get(component_id)
            # The provenance flag may have been corrected after an old contract
            # was generated. Prefer the current immutable provenance state when
            # the component still exists; fall back to the document snapshot.
            excluded = (
                bool(getattr(current, "accounting_cost_excluded", False))
                if current is not None
                else bool(item.get("accounting_cost_excluded"))
            )
            if excluded:
                reused += cost
            else:
                included += cost
        return included, reused

    selected = metadata.get("selected_components")
    if isinstance(selected, list):
        selected_dicts = [item for item in selected if isinstance(item, dict)]
        if selected == [] or any("cost" in item for item in selected_dicts):
            return split(selected_dicts)

    snapshots = metadata.get("selected_tsr_components")
    if isinstance(snapshots, list):
        nested: list[dict[str, Any]] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            components = snapshot.get("components")
            if isinstance(components, list):
                nested.extend(item for item in components if isinstance(item, dict) and "cost" in item)
        if nested:
            return split(nested)

    selected_ids = contract_component_ids(metadata)
    if selected_ids:
        included = 0.0
        reused = 0.0
        for module in client_modules:
            if str(module.module_id) not in selected_ids or module.is_archived:
                continue
            if bool(getattr(module, "accounting_cost_excluded", False)):
                reused += parse_number(module.cost)
            else:
                included += parse_number(module.cost)
        return included, reused

    # Last-resort compatibility for documents whose selected component IDs are
    # no longer available in the current client card.
    if "components_cost" in metadata or "stock_reused_cost" in metadata:
        return (
            max(0.0, parse_number(metadata.get("components_cost"))),
            max(0.0, parse_number(metadata.get("stock_reused_cost"))),
        )
    return 0.0, 0.0


def contract_components_cost(document: models.Document, client_modules: Iterable[models.Module]) -> float:
    return _contract_component_cost_breakdown(document, client_modules)[0]


def contract_stock_reused_cost(document: models.Document, client_modules: Iterable[models.Module]) -> float:
    return _contract_component_cost_breakdown(document, client_modules)[1]


def contract_component_ids(metadata: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("selected_components", "selected_modules"):
        items = metadata.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            value = item.get("component_id") or item.get("module_id")
            if value:
                ids.add(str(value))
    return ids


def single_tsr_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    snapshots = metadata.get("selected_tsr_components")
    if isinstance(snapshots, list) and len(snapshots) == 1 and isinstance(snapshots[0], dict):
        return snapshots[0]
    return {}


def client_certificate_items(client: models.Client) -> list[dict[str, Any]]:
    normalized = []
    for item in client.tsr_items or []:
        amount = parse_number(item.certificate_price)
        if amount <= 0:
            continue
        normalized.append({
            "certificate_id": str(item.client_tsr_id),
            "amount": amount,
            "date": normalize_date(item.check_date),
            "tsr": item.tsr.full_tsr_code if item.tsr else None,
        })
    if normalized:
        return normalized
    return [{
        "certificate_id": None,
        "amount": parse_number(client.certificate_price),
        "date": normalize_date(client.check_date),
        "tsr": client.tsr_code,
    }]


def sum_client_module_cost(
    modules: Iterable[models.Module],
    *,
    selected_certificate_ids: set[str],
    date_filter_active: bool,
    has_normalized_certificates: bool,
) -> float:
    # DBCRM_UPDATE_20260831: accounting stock cost
    total = 0.0
    for module in modules:
        if module.is_archived or bool(getattr(module, "accounting_cost_excluded", False)):
            continue
        if date_filter_active and has_normalized_certificates:
            module_certificate_id = str(module.client_tsr_id or "")
            if not module_certificate_id or module_certificate_id not in selected_certificate_ids:
                continue
        total += parse_number(module.cost)
    return total


def sum_client_stock_reused_cost(
    modules: Iterable[models.Module],
    *,
    selected_certificate_ids: set[str],
    date_filter_active: bool,
    has_normalized_certificates: bool,
) -> float:
    total = 0.0
    for module in modules:
        if module.is_archived or not bool(getattr(module, "accounting_cost_excluded", False)):
            continue
        if date_filter_active and has_normalized_certificates:
            module_certificate_id = str(module.client_tsr_id or "")
            if not module_certificate_id or module_certificate_id not in selected_certificate_ids:
                continue
        total += parse_number(module.cost)
    return total


def date_in_range(value: date | None, start_date: date | None, end_date: date | None) -> bool:
    if not start_date and not end_date:
        return True
    if value is None:
        return False
    if start_date and value < start_date:
        return False
    if end_date and value > end_date:
        return False
    return True


def report_filters(
    *,
    start_date: date | None,
    end_date: date | None,
    hide_failed: bool,
    tax_usn_percent: float,
    tax_osno_percent: float,
    acquiring_percent: float,
    vat_percent: float,
) -> dict[str, Any]:
    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "hide_failed": hide_failed,
        "tax_percent": tax_usn_percent,
        "tax_usn_percent": tax_usn_percent,
        "tax_osno_percent": tax_osno_percent,
        "acquiring_percent": acquiring_percent,
        "vat_percent": vat_percent,
    }


def build_contract_coverage(db: Session) -> list[dict[str, Any]]:
    """Return contract coverage per client and per normalized certificate."""
    clients = (
        db.query(models.Client)
        .filter(models.Client.is_archived.is_(False))
        .options(
            selectinload(models.Client.modules),
            selectinload(models.Client.documents).selectinload(models.Document.certificate),
            selectinload(models.Client.tsr_items),
        )
        .all()
    )
    result: list[dict[str, Any]] = []
    for client in clients:
        modules = [module for module in (client.modules or []) if not module.is_archived]
        module_ids = {str(module.module_id) for module in modules}
        module_names = {
            str(module.module_id): (module.module_name_index or module.properties or str(module.module_id))
            for module in modules
        }
        covered_ids: set[str] = set()
        covered_certificate_ids: set[str] = set()
        distinct_contract_keys: set[str] = set()
        contract_dates: list[date] = []

        for document in sorted(
            client.documents or [],
            key=lambda item: ((item.created_at.isoformat() if item.created_at else ""), str(item.document_id)),
            reverse=True,
        ):
            metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
            document_type = str(document.document_type or "").strip().lower()
            if document_type not in GENERATED_DOCUMENT_TYPES:
                continue
            certificate = resolve_contract_certificate(document, client)
            if certificate["key"] in distinct_contract_keys:
                continue
            distinct_contract_keys.add(certificate["key"])
            for certificate_id in certificate.get("certificate_ids", []):
                if certificate_id:
                    covered_certificate_ids.add(str(certificate_id))
            contract_date = normalize_date(metadata.get("document_date")) or normalize_date(document.created_at)
            if contract_date:
                contract_dates.append(contract_date)
            covered_ids.update(contract_component_ids(metadata))

        certificate_ids = {str(item.client_tsr_id) for item in (client.tsr_items or [])}
        # The red accounting warning answers one simple question: does the
        # patient have a generated contract at all?  Contract-to-certificate
        # links are useful for coverage diagnostics below, but old contracts
        # may legitimately lack those normalized links.  Treating a missing
        # certificate link as a missing contract caused false warnings for
        # patients whose contract document already exists.
        requires_contract = not bool(distinct_contract_keys)
        uncovered_ids = sorted(module_ids - covered_ids)
        result.append({
            "client_id": str(client.client_id),
            "is_working": is_working_client(client),
            "requires_contract": requires_contract,
            "contract_count": len(distinct_contract_keys),
            "total_certificates": len(certificate_ids),
            "covered_certificates": len(certificate_ids & covered_certificate_ids),
            "total_modules": len(module_ids),
            "covered_modules": len(module_ids & covered_ids),
            "latest_contract_date": max(contract_dates).isoformat() if contract_dates else None,
            "uncovered_module_ids": uncovered_ids,
            "uncovered_module_names": [module_names[module_id] for module_id in uncovered_ids],
        })
    return result


def short_client_name(client: models.Client) -> str:
    initials = "".join(
        f"{value.strip()[0]}." for value in (client.first_name, client.middle_name) if value and value.strip()
    )
    return f"{client.last_name or ''} {initials}".strip()


def load_custom_fields(db: Session) -> list[dict[str, str]]:
    fields = (
        db.query(models.AccountingCustomField)
        .filter(models.AccountingCustomField.is_active.is_(True))
        .order_by(models.AccountingCustomField.field_name)
        .all()
    )
    return [
        {"key": str(field.field_id), "label": field.field_name, "type": field.field_type}
        for field in fields
    ]


def load_client_custom_values(client: models.Client) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for row in client.accounting_values or []:
        field_id = str(row.field_id)
        field = row.field
        values[field_id] = row.value_number if field and field.field_type == "number" else row.value_text
    return values


def serialize_client(client: models.Client, client_date: date | None) -> dict[str, Any]:
    full_name = " ".join(
        part for part in (client.last_name or "", client.first_name or "", client.middle_name or "") if part
    ).strip() or "Без имени"
    agent_name = None
    if client.agent:
        agent_name = " ".join(
            part
            for part in (client.agent.last_name or "", client.agent.first_name or "", client.agent.middle_name or "")
            if part
        ).strip()
    return {
        "client_id": str(client.client_id),
        "external_id": client.external_id,
        "full_name": full_name,
        "status": client.status_code,
        "current_stage": client.current_stage,
        "agent_id": str(client.agent_id) if client.agent_id else None,
        "agent_name": agent_name,
        "date": client_date.isoformat() if client_date else None,
        "taxation_system": normalize_taxation_system(client.taxation_system),
    }


def normalize_taxation_system(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    return "ОСНО" if normalized == "ОСНО" else "УСН"


def resolve_usn_percent(legacy_tax_percent: float | None, tax_usn_percent: float | None) -> float:
    if tax_usn_percent is not None:
        return float(tax_usn_percent)
    if legacy_tax_percent is not None:
        return float(legacy_tax_percent)
    return 6.0


def tax_percent_for_client(
    client: models.Client,
    *,
    tax_usn_percent: float,
    tax_osno_percent: float,
) -> float:
    # Historical DB value "ОСНО" is used by the UI as the second configured tax rate.
    if normalize_taxation_system(client.taxation_system) == "ОСНО":
        return float(tax_osno_percent)
    return float(tax_usn_percent)


def is_failed_client(client: models.Client) -> bool:
    text = f"{client.status_code or ''} {client.current_stage or ''}".lower()
    return any(token in text for token in ("fail", "hold", "cancel", "отказ", "отлож", "отмен"))


def is_working_client(client: models.Client) -> bool:
    status = str(client.status_code or "").strip().lower().replace("-", "_").replace(" ", "_")
    if is_failed_client(client):
        return False
    return (
        status in {"work", "working", "in_work", "inwork", "in_progress", "inprogress"}
        or "работ" in status
        or "выполня" in status
    )


def parse_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(" ", "").replace("\xa0", "").replace(",", ".")
        parts = normalized.split(".")
        if len(parts) > 2:
            normalized = "".join(parts[:-1]) + "." + parts[-1]
        normalized = "".join(char for char in normalized if char.isdigit() or char in ".-")
        try:
            return float(normalized) if normalized else 0.0
        except ValueError:
            return 0.0
    return 0.0


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        normalized = value.strip()
        for candidate in (normalized[:10], normalized):
            try:
                return datetime.fromisoformat(candidate).date()
            except ValueError:
                pass
        for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(normalized, fmt).date()
            except ValueError:
                pass
    return None

