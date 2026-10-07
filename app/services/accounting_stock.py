from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


# Accounting payloads evolved across several project revisions. Keep the adapter deliberately
# tolerant so both client reports and contract snapshots can identify the exact components.
_ID_KEYS = (
    "module_ids",
    "component_ids",
    "selected_module_ids",
    "selected_component_ids",
    "modules_ids",
    "components_ids",
)
_ASSIGNMENT_KEYS = (
    "client_tsr_id",
    "client_tsr_ids",
    "certificate_id",
    "certificate_ids",
    "assignment_id",
    "assignment_ids",
)


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


def _recursive_values(row: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    wanted = set(keys)
    result: list[Any] = []
    for key, value in _walk(row):
        if key not in wanted or value in (None, "", []):
            continue
        if isinstance(value, (list, tuple, set)):
            result.extend(item for item in value if item not in (None, ""))
        else:
            result.append(value)
    return result


def _first_recursive(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    values = _recursive_values(row, keys)
    return values[0] if values else None


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _uuid_values(values: Iterable[Any]) -> list[UUID | str]:
    result: list[UUID | str] = []
    for value in _dedupe_strings(values):
        try:
            result.append(UUID(value))
        except (TypeError, ValueError, AttributeError):
            # Some older installations used non-UUID identifiers in serialized snapshots.
            # Let SQLAlchemy/database coercion handle them instead of dropping the reference.
            result.append(value)
    return result


def _client_id(row: dict[str, Any]) -> UUID | str | None:
    value = _first_recursive(row, ("client_id",))
    if not value:
        return None
    values = _uuid_values([value])
    return values[0] if values else None


def _is_contract_row(row: dict[str, Any]) -> bool:
    document = row.get("document")
    if isinstance(document, dict) and document.get("document_id"):
        return True
    return bool(_first_recursive(row, ("document_id", "contract_id")))


def _module_ids(row: dict[str, Any]) -> list[UUID | str]:
    return _uuid_values(_recursive_values(row, _ID_KEYS))


def _assignment_ids(row: dict[str, Any]) -> list[UUID | str]:
    return _uuid_values(_recursive_values(row, _ASSIGNMENT_KEYS))


def _module_cost(module: models.Module) -> float:
    try:
        return float(module.cost or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _eligible_modules(db: Session, row: dict[str, Any]) -> list[models.Module]:
    statement = select(models.Module)
    conditions = []

    ids = _module_ids(row)
    assignments = _assignment_ids(row)
    client = _client_id(row)

    if ids:
        # Contract snapshots normally contain the selected component ids; this is the most
        # precise source and therefore takes precedence over every broader association.
        conditions.append(models.Module.module_id.in_(ids))
    elif assignments and hasattr(models.Module, "client_tsr_id"):
        # Client accounting may aggregate several CLIENT_TSR records for the chosen period.
        # Use every assignment found in the row rather than only the first one.
        conditions.append(models.Module.client_tsr_id.in_(assignments))
    elif client and not _is_contract_row(row):
        # A legacy client row without explicit CLIENT_TSR references legitimately represents
        # all active components of that patient. Contract rows NEVER use this fallback because
        # it could subtract one reused component from several different contracts.
        conditions.append(models.Module.client_id == client)
    else:
        return []

    if hasattr(models.Module, "is_archived"):
        conditions.append(models.Module.is_archived.is_(False))

    return list(db.execute(statement.where(*conditions)).scalars().all())


def _money_container(row: dict[str, Any]) -> dict[str, Any]:
    amounts = row.get("amounts")
    return amounts if isinstance(amounts, dict) else row


def apply_stock_reuse_adjustments(db: Session, report: Any) -> Any:
    """Exclude previously purchased MAIN-Warehouse components from a patient's new expense.

    ``accounting_cost_excluded`` is permanent provenance: the component keeps its real cost
    for audit and display, but that cost is not charged to the next patient/certificate again.
    The report still exposes ``stock_reused_modules_cost`` so the UI can show the reused sum in
    parentheses next to the normal component cost.
    """
    if not isinstance(report, dict):
        return report

    rows = report.get("rows")
    if not isinstance(rows, list):
        return report

    for row in rows:
        if not isinstance(row, dict) or row.get("stock_reuse_adjusted"):
            continue

        modules = _eligible_modules(db, row)
        reused = sum(
            _module_cost(module)
            for module in modules
            if bool(getattr(module, "accounting_cost_excluded", False))
        )

        amounts = _money_container(row)
        raw_total = amounts.get("modules_cost", 0.0)
        try:
            current_total = float(raw_total or 0.0)
        except (TypeError, ValueError):
            current_total = 0.0

        # Snapshot/legacy reports can contain a narrower component total than the live module
        # query. Never subtract more than the report itself currently considers as component
        # expense; this prevents a negative/over-adjusted historical row.
        reused_for_row = min(max(reused, 0.0), max(current_total, 0.0))
        amounts["modules_cost"] = max(0.0, current_total - reused_for_row)
        amounts["stock_reused_modules_cost"] = reused_for_row
        row["stock_reused_modules_cost"] = reused_for_row
        row["stock_reuse_adjusted"] = True

    return report
