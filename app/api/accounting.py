# app/api/accounting.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import require_admin
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.get("/custom-fields", response_model=List[schemas.AccountingCustomFieldRead])
def list_custom_fields(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return crud.get_accounting_custom_fields(db)


@router.post("/custom-fields", response_model=schemas.AccountingCustomFieldRead, status_code=status.HTTP_201_CREATED)
def create_custom_field(
    payload: schemas.AccountingCustomFieldCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if payload.field_type not in {"number", "text"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="field_type must be 'number' or 'text'")
    try:
        field = crud.create_accounting_custom_field(db, payload.field_name, payload.field_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    log_action(db, entity="accounting_field", entity_id=field.field_id, action="create", user=current_user, after=field)
    return field


@router.delete("/custom-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field(
    field_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.AccountingCustomField, field_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    before_snapshot = snapshot(before)
    if not crud.delete_accounting_custom_field(db, field_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    log_action(db, entity="accounting_field", entity_id=field_id, action="delete", user=current_user, before=before_snapshot)
    return None


@router.patch("/clients/{client_id}/custom-values")
def update_client_custom_values(
    client_id: UUID,
    payload: schemas.AccountingValuesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if not crud.get_client(db, client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    before = crud.get_client_custom_field_values(db, client_id)
    updates = [{"field_id": v.field_id, "value": v.value} for v in payload.values]
    try:
        crud.set_client_custom_field_values(db, client_id, updates)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    after = crud.get_client_custom_field_values(db, client_id)
    log_action(db, entity="client", entity_id=client_id, action="accounting.custom_values.update", user=current_user, before=before, after=after)
    return {"status": "updated"}


@router.get("/clients/{client_id}/expenses/{field_key}")
def get_client_expense_history(
    client_id: UUID,
    field_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        return crud.get_accounting_expense_history(db, client_id, field_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/clients/{client_id}/expenses")
def add_client_expense(
    client_id: UUID,
    payload: schemas.AccountingExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        result = crud.add_accounting_expense(db, client_id, payload, current_user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(
        db, entity="client", entity_id=client_id, action="accounting.expense.add",
        user=current_user, after={"field_key": payload.field_key, "amount": payload.amount, "description": payload.description, "paid": payload.paid},
    )
    return result


@router.patch("/clients/{client_id}/expenses/{field_key}/status")
def update_client_expense_status(
    client_id: UUID,
    field_key: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        result = crud.set_accounting_expense_status(db, client_id, field_key, bool(payload.get("paid")))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(db, entity="client", entity_id=client_id, action="accounting.expense.status", user=current_user, after={"field_key": field_key, "paid": bool(payload.get("paid"))})
    return result

@router.patch("/clients/{client_id}/expenses/{field_key}/{entry_id}")
def update_client_expense(
    client_id: UUID,
    field_key: str,
    entry_id: str,
    payload: schemas.AccountingExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        result = crud.update_accounting_expense(db, client_id, field_key, entry_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(
        db, entity="client", entity_id=client_id, action="accounting.expense.update",
        user=current_user, after={"field_key": field_key, "entry_id": entry_id, "amount": payload.amount, "description": payload.description},
    )
    return result


@router.delete("/clients/{client_id}/expenses/{field_key}/{entry_id}")
def delete_client_expense(
    client_id: UUID,
    field_key: str,
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        result = crud.delete_accounting_expense(db, client_id, field_key, entry_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(
        db, entity="client", entity_id=client_id, action="accounting.expense.delete",
        user=current_user, after={"field_key": field_key, "entry_id": entry_id},
    )
    return result
