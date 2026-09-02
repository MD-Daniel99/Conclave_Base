from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app import models, schemas
from app.services.accounting_report import (
    build_accounting_report,
    build_contract_accounting_report,
    build_contract_coverage,
)
from app.services.accounting_expenses import (
    get_contract_expense_history as get_contract_expense_history_service,
    add_contract_expense as add_contract_expense_service,
    set_contract_expense_status as set_contract_expense_status_service,
    update_contract_expense as update_contract_expense_service,
    delete_contract_expense as delete_contract_expense_service,
)
from app.services.audit import log_action, snapshot

router = APIRouter(prefix="/accounting", tags=["accounting"])


@router.get("/report")
def get_accounting_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    hide_failed: bool = Query(default=True),
    tax_percent: float | None = Query(default=None, ge=0),
    tax_usn_percent: float | None = Query(default=None, ge=0),
    tax_osno_percent: float = Query(default=15.0, ge=0),
    acquiring_percent: float = Query(default=1.0, ge=0),
    vat_percent: float = Query(default=20.0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    return build_accounting_report(
        db,
        start_date=start_date,
        end_date=end_date,
        hide_failed=hide_failed,
        tax_percent=tax_percent,
        tax_usn_percent=tax_usn_percent,
        tax_osno_percent=tax_osno_percent,
        acquiring_percent=acquiring_percent,
        vat_percent=vat_percent,
    )


@router.get("/contracts")
def get_contract_accounting_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    hide_failed: bool = Query(default=True),
    tax_percent: float | None = Query(default=None, ge=0),
    tax_usn_percent: float | None = Query(default=None, ge=0),
    tax_osno_percent: float = Query(default=15.0, ge=0),
    acquiring_percent: float = Query(default=1.0, ge=0),
    vat_percent: float = Query(default=20.0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    return build_contract_accounting_report(
        db,
        start_date=start_date,
        end_date=end_date,
        hide_failed=hide_failed,
        tax_percent=tax_percent,
        tax_usn_percent=tax_usn_percent,
        tax_osno_percent=tax_osno_percent,
        acquiring_percent=acquiring_percent,
        vat_percent=vat_percent,
    )


@router.get("/contract-coverage")
def get_contract_coverage(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return build_contract_coverage(db)


@router.patch("/contracts/{document_id}")
def update_contract_accounting(
    document_id: str,
    payload: schemas.ContractAccountingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    try:
        from uuid import UUID
        parsed_id = UUID(document_id)
    except ValueError:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document id")

    row = db.query(models.ContractAccounting).filter(models.ContractAccounting.document_id == parsed_id).first()
    if not row:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract accounting row not found")
    before = snapshot(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "custom_values" and isinstance(value, dict):
            existing = dict(row.custom_values or {})
            history = existing.get("__expense_history__")
            value = dict(value)
            if history is not None:
                value["__expense_history__"] = history
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    document = row.document
    if document and document.client_id:
        log_action(
            db,
            entity="client",
            entity_id=document.client_id,
            action="accounting.contract.update",
            user=current_user,
            before=before,
            after=row,
            details={
                "document_name": document.filename,
                "document_number": document.document_number,
            },
        )
    return {"status": "updated"}

@router.get("/contracts/{document_id}/expenses/{field_key}")
def get_contract_expense_history(
    document_id: str,
    field_key: str,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    from uuid import UUID
    from fastapi import HTTPException, status
    try:
        parsed_id = UUID(document_id)
        return get_contract_expense_history_service(db, parsed_id, field_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/contracts/{document_id}/expenses")
def add_contract_expense(
    document_id: str,
    payload: schemas.AccountingExpenseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    from uuid import UUID
    from fastapi import HTTPException, status
    try:
        parsed_id = UUID(document_id)
        result = add_contract_expense_service(db, parsed_id, payload, current_user)
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/contracts/{document_id}/expenses/{field_key}/status")
def update_contract_expense_status(
    document_id: str,
    field_key: str,
    payload: dict,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    from uuid import UUID
    from fastapi import HTTPException, status
    try:
        parsed_id = UUID(document_id)
        return set_contract_expense_status_service(db, parsed_id, field_key, bool(payload.get("paid")))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/contracts/{document_id}/expenses/{field_key}/{entry_id}")
def update_contract_expense_entry(
    document_id: str,
    field_key: str,
    entry_id: str,
    payload: schemas.AccountingExpenseUpdate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    from uuid import UUID
    from fastapi import HTTPException, status
    try:
        parsed_id = UUID(document_id)
        return update_contract_expense_service(db, parsed_id, field_key, entry_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/contracts/{document_id}/expenses/{field_key}/{entry_id}")
def delete_contract_expense_entry(
    document_id: str,
    field_key: str,
    entry_id: str,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    from uuid import UUID
    from fastapi import HTTPException, status
    try:
        parsed_id = UUID(document_id)
        return delete_contract_expense_service(db, parsed_id, field_key, entry_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
