from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

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


def build_accounting_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    hide_failed: bool = True,
    tax_percent: float | None = None,
    tax_usn_percent: float | None = None,
    tax_osno_percent: float = 20.0,
    acquiring_percent: float = 2.0,
    vat_percent: float = 20.0,
) -> dict[str, Any]:
    """Build the same accounting report that existed in Streamlit.

    Revenue is taken from Client.certificate_price, module costs are summed from
    linked modules, fixed expenses use the same seven categories as contract
    accounting, and numeric custom fields are treated as additional expenses.
    """
    effective_usn_percent = resolve_usn_percent(tax_percent, tax_usn_percent)

    clients = (
        db.query(models.Client)
        .filter(models.Client.is_archived.is_(False))
        .options(
            selectinload(models.Client.agent),
            selectinload(models.Client.modules),
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
        client_date = normalize_date(client.check_date)

        if hide_failed and is_failed_client(client):
            continue

        if (start_date or end_date) and client_date is None:
            continue

        if start_date and client_date and client_date < start_date:
            continue

        if end_date and client_date and client_date > end_date:
            continue

        custom_values = load_client_custom_values(client)
        revenue = parse_number(client.certificate_price)
        modules_cost = sum(
            parse_number(module.cost)
            for module in (client.modules or [])
            if not module.is_archived
        )
        salary = sum(parse_number(value) for value in (
            client.prosthetist_work,
            client.patient_travel,
            client.patient_accommodation,
            client.patient_meals,
            client.patient_payment,
            client.other_expenses,
            client.agency_expenses,
        ))

        normalized_custom_values: dict[str, Any] = {}
        custom_expenses = 0.0

        for field_id, raw_value in custom_values.items():
            field = field_by_id.get(field_id)

            if field is None:
                continue

            if field["type"] == "number":
                value: Any = parse_number(raw_value)
                custom_expenses += value
            else:
                value = "" if raw_value is None else str(raw_value)

            normalized_custom_values[field_id] = value

        applied_tax_percent = tax_percent_for_client(
            client,
            tax_usn_percent=effective_usn_percent,
            tax_osno_percent=tax_osno_percent,
        )
        vat = revenue * (vat_percent / (100 + vat_percent)) if revenue else 0.0
        tax = (revenue - vat) * (applied_tax_percent / 100)
        acquiring = revenue * (acquiring_percent / 100)
        has_no_accounting_basis = modules_cost == 0 and client_date is None
        profit = 0.0 if has_no_accounting_basis else revenue - vat - tax - acquiring - modules_cost - salary - custom_expenses

        row = {
            "client": serialize_client(client, client_date),
            "amounts": {
                "revenue": revenue,
                "cost": modules_cost,
                "salary": salary,
                "custom_expenses": custom_expenses,
                "vat": vat,
                "tax": tax,
                "tax_percent": applied_tax_percent,
                "acquiring": acquiring,
                "profit": profit,
            },
            "custom_values": normalized_custom_values,
        }
        rows.append(row)

        for key in totals:
            totals[key] += row["amounts"][key]

    return {
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "hide_failed": hide_failed,
            "tax_percent": effective_usn_percent,
            "tax_usn_percent": effective_usn_percent,
            "tax_osno_percent": tax_osno_percent,
            "acquiring_percent": acquiring_percent,
            "vat_percent": vat_percent,
        },
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
    tax_osno_percent: float = 20.0,
    acquiring_percent: float = 2.0,
    vat_percent: float = 20.0,
) -> dict[str, Any]:
    """Build a per-contract ledger without counting one certificate more than once.

    Contracts of one client share a single certificate balance.  The oldest
    contract starts with the full certificate, every later contract starts
    with the balance left after all earlier contract expenses.  Percentage
    expenses are charged once, on the first contract, rather than once for
    every generated document.
    """
    effective_usn_percent = resolve_usn_percent(tax_percent, tax_usn_percent)
    records = (
        db.query(models.ContractAccounting)
        .options(
            selectinload(models.ContractAccounting.document).selectinload(models.Document.client)
        )
        .order_by(models.ContractAccounting.created_at.desc())
        .all()
    )
    custom_fields = load_custom_fields(db)
    numeric_field_ids = {field["key"] for field in custom_fields if field["type"] == "number"}
    rows_by_client: dict[str, list[dict[str, Any]]] = {}

    for accounting in records:
        document = accounting.document
        if not document or not document.client:
            continue
        client = document.client
        if client.is_archived:
            continue
        if hide_failed and is_failed_client(client):
            continue

        metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
        document_date = normalize_date(metadata.get("document_date")) or normalize_date(document.created_at)
        modules_cost = parse_number(document.contract_total)
        fixed_expenses = {
            "prosthetist_work": parse_number(accounting.prosthetist_work),
            "patient_travel": parse_number(accounting.patient_travel),
            "patient_accommodation": parse_number(accounting.patient_accommodation),
            "patient_meals": parse_number(accounting.patient_meals),
            "patient_payment": parse_number(accounting.patient_payment),
            "other_expenses": parse_number(accounting.other_expenses),
            "agency_expenses": parse_number(accounting.agency_expenses),
        }
        custom_values = accounting.custom_values or {}
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
        client_id = str(client.client_id)
        rows_by_client.setdefault(client_id, []).append({
            "document": {
                "document_id": str(document.document_id),
                "filename": document.filename,
                "document_number": document.document_number,
                "document_type": document.document_type,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "date": document_date.isoformat() if document_date else None,
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
                "modules_cost": modules_cost,
                **fixed_expenses,
                "custom_expenses": custom_expenses,
                "tax_percent": applied_tax_percent,
            },
            "custom_values": custom_values,
            "_certificate_snapshot": parse_number(document.certificate_amount),
            "_client_certificate": parse_number(client.certificate_price),
            "_sort_key": (
                document.created_at.isoformat() if document.created_at else "",
                document_date.isoformat() if document_date else "",
                str(document.document_id),
            ),
        })

    ledger_rows: list[dict[str, Any]] = []

    for client_rows in rows_by_client.values():
        client_rows.sort(key=lambda row: row["_sort_key"])
        certificate = next(
            (
                row["_certificate_snapshot"]
                for row in client_rows
                if row["_certificate_snapshot"] != 0
            ),
            client_rows[0]["_client_certificate"],
        )
        remaining_certificate = certificate
        contract_count = len(client_rows)

        for contract_index, row in enumerate(client_rows, start=1):
            amounts = row["amounts"]
            percentage_basis = certificate if contract_index == 1 else 0.0
            vat = percentage_basis * (vat_percent / (100 + vat_percent)) if percentage_basis else 0.0
            tax = (percentage_basis - vat) * (amounts["tax_percent"] / 100)
            acquiring = percentage_basis * (acquiring_percent / 100)
            expenses_total = (
                amounts["modules_cost"]
                + sum(amounts[key] for key in (
                    "prosthetist_work",
                    "patient_travel",
                    "patient_accommodation",
                    "patient_meals",
                    "patient_payment",
                    "other_expenses",
                    "agency_expenses",
                ))
                + amounts["custom_expenses"]
                + vat
                + tax
                + acquiring
            )
            balance_before = remaining_certificate
            remaining_certificate = balance_before - expenses_total
            amounts.update({
                "certificate": balance_before,
                "certificate_original": certificate,
                "certificate_remaining": remaining_certificate,
                "vat": vat,
                "tax": tax,
                "acquiring": acquiring,
                "profit": remaining_certificate,
                "applies_percentage_expenses": contract_index == 1,
                "contract_index": contract_index,
                "contract_count": contract_count,
            })
            row.pop("_certificate_snapshot", None)
            row.pop("_client_certificate", None)
            row.pop("_sort_key", None)
            ledger_rows.append(row)

    rows = [
        row
        for row in ledger_rows
        if not (
            start_date
            and (
                normalize_date(row["document"]["date"]) is None
                or normalize_date(row["document"]["date"]) < start_date
            )
        )
        and not (
            end_date
            and (
                normalize_date(row["document"]["date"]) is None
                or normalize_date(row["document"]["date"]) > end_date
            )
        )
    ]
    rows.sort(
        key=lambda row: (
            row["document"]["created_at"] or "",
            row["document"]["date"] or "",
            row["document"]["document_id"],
        ),
        reverse=True,
    )

    amount_keys = [
        "certificate", "modules_cost", "prosthetist_work", "patient_travel",
        "patient_accommodation", "patient_meals", "patient_payment", "other_expenses",
        "agency_expenses", "custom_expenses", "vat", "tax", "acquiring", "profit",
    ]
    totals = {
        key: sum(row["amounts"][key] for row in rows)
        for key in amount_keys
        if key not in {"certificate", "profit"}
    }
    visible_rows_by_client: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        visible_rows_by_client.setdefault(row["client"]["client_id"], []).append(row)
    totals["certificate"] = sum(
        min(
            client_rows,
            key=lambda row: row["amounts"]["contract_index"],
        )["amounts"]["certificate"]
        for client_rows in visible_rows_by_client.values()
    )
    totals["profit"] = sum(
        max(
            client_rows,
            key=lambda row: row["amounts"]["contract_index"],
        )["amounts"]["profit"]
        for client_rows in visible_rows_by_client.values()
    )
    totals = {key: totals.get(key, 0.0) for key in amount_keys}
    return {
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "hide_failed": hide_failed,
            "tax_percent": effective_usn_percent,
            "tax_usn_percent": effective_usn_percent,
            "tax_osno_percent": tax_osno_percent,
            "acquiring_percent": acquiring_percent,
            "vat_percent": vat_percent,
        },
        "custom_fields": custom_fields,
        "rows": rows,
        "totals": totals,
    }


def build_contract_coverage(db: Session) -> list[dict[str, Any]]:
    """Return whether every current client module is covered by generated contracts."""
    clients = (
        db.query(models.Client)
        .filter(models.Client.is_archived.is_(False))
        .options(
            selectinload(models.Client.modules),
            selectinload(models.Client.documents),
        )
        .all()
    )
    result: list[dict[str, Any]] = []

    for client in clients:
        modules = [
            module
            for module in (client.modules or [])
            if not module.is_archived
        ]
        module_ids = {str(module.module_id) for module in modules}
        module_names = {
            str(module.module_id): (module.module_name_index or module.properties or str(module.module_id))
            for module in modules
        }
        covered_ids: set[str] = set()
        contract_count = 0
        contract_dates: list[date] = []

        for document in client.documents or []:
            metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
            selected_modules = metadata.get("selected_modules")
            document_type = str(document.document_type or "").strip().lower()
            is_contract = document_type in GENERATED_DOCUMENT_TYPES
            if is_contract:
                contract_count += 1
                contract_date = normalize_date(metadata.get("document_date")) or normalize_date(document.created_at)
                if contract_date:
                    contract_dates.append(contract_date)
            if not isinstance(selected_modules, list):
                continue
            for item in selected_modules:
                if isinstance(item, dict) and item.get("module_id"):
                    covered_ids.add(str(item["module_id"]))

        uncovered_ids = sorted(module_ids - covered_ids)
        working = is_working_client(client)
        # Наличие договора не зависит от текущего этапа клиента: завершённая или
        # приостановленная карточка без договора всё равно требует документа.
        requires_contract = contract_count == 0
        result.append({
            "client_id": str(client.client_id),
            "is_working": working,
            "requires_contract": requires_contract,
            "contract_count": contract_count,
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
        {
            "key": str(field.field_id),
            "label": field.field_name,
            "type": field.field_type,
        }
        for field in fields
    ]


def load_client_custom_values(client: models.Client) -> dict[str, Any]:
    values: dict[str, Any] = {}

    for row in client.accounting_values or []:
        field_id = str(row.field_id)
        field = row.field

        if field and field.field_type == "number":
            values[field_id] = row.value_number
        else:
            values[field_id] = row.value_text

    return values


def serialize_client(client: models.Client, client_date: date | None) -> dict[str, Any]:
    full_name = " ".join(
        part
        for part in (client.last_name or "", client.first_name or "", client.middle_name or "")
        if part
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


def resolve_usn_percent(
    legacy_tax_percent: float | None,
    tax_usn_percent: float | None,
) -> float:
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
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None

    return None
