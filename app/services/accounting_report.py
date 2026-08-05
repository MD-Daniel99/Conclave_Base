from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
        .filter(models.Client.is_archived.is_(False))
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

        expenses = {
            key: parse_number(getattr(client, key, 0.0))
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
        if client.is_archived or (hide_failed and is_failed_client(client)):
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
        fixed_expenses_by_key = {
            key: parse_number(getattr(accounting, key, 0.0))
            for key in FIXED_EXPENSE_KEYS
        }
        fixed_expenses = sum(fixed_expenses_by_key.values())
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
                **fixed_expenses_by_key,
                "custom_expenses": custom_expenses,
                "tax_percent": applied_tax_percent,
                **financials,
            },
            "custom_values": custom_values,
        })

    rows.sort(
        key=lambda row: (
            row["document"]["created_at"] or "",
            row["document"]["document_id"],
        ),
        reverse=True,
    )
    amount_keys = [
        "certificate", "modules_cost", *FIXED_EXPENSE_KEYS,
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
        "amount": amount,
        "date": certificate_date,
        "key": key,
    }


def contract_components_cost(document: models.Document, client_modules: Iterable[models.Module]) -> float:
    """Read component cost, never the certificate/contract selling amount."""
    metadata = document.contract_metadata if isinstance(document.contract_metadata, dict) else {}
    if "components_cost" in metadata:
        return max(0.0, parse_number(metadata.get("components_cost")))

    selected = metadata.get("selected_components")
    if isinstance(selected, list):
        selected_dicts = [item for item in selected if isinstance(item, dict)]
        if selected == [] or any("cost" in item for item in selected_dicts):
            return sum(parse_number(item.get("cost")) for item in selected_dicts)

    snapshots = metadata.get("selected_tsr_components")
    if isinstance(snapshots, list):
        nested_costs: list[float] = []
        has_cost_key = False
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            components = snapshot.get("components")
            if not isinstance(components, list):
                continue
            for component in components:
                if isinstance(component, dict) and "cost" in component:
                    has_cost_key = True
                    nested_costs.append(parse_number(component.get("cost")))
        if has_cost_key:
            return sum(nested_costs)

    selected_ids = contract_component_ids(metadata)
    if selected_ids:
        return sum(
            parse_number(module.cost)
            for module in client_modules
            if str(module.module_id) in selected_ids and not module.is_archived
        )
    # contract_total in historical documents often contains the certificate or
    # selling price. It is intentionally not used as component cost.
    return 0.0


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
    total = 0.0
    for module in modules:
        if module.is_archived:
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
            if certificate["certificate_id"]:
                covered_certificate_ids.add(str(certificate["certificate_id"]))
            contract_date = normalize_date(metadata.get("document_date")) or normalize_date(document.created_at)
            if contract_date:
                contract_dates.append(contract_date)
            covered_ids.update(contract_component_ids(metadata))

        certificate_ids = {str(item.client_tsr_id) for item in (client.tsr_items or [])}
        requires_contract = bool(certificate_ids - covered_certificate_ids) if certificate_ids else not distinct_contract_keys
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
