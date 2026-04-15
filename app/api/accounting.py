from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app import schemas, crud
from app.db import get_db

router = APIRouter()

# --- Кастомные поля ---
@router.get("/custom-fields", response_model=List[schemas.AccountingCustomFieldRead])
def list_custom_fields(db: Session = Depends(get_db)):
    return crud.get_accounting_custom_fields(db)

@router.post("/custom-fields", response_model=schemas.AccountingCustomFieldRead, status_code=201)
def create_custom_field(payload: schemas.AccountingCustomFieldCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_accounting_custom_field(db, payload.field_name, payload.field_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/custom-fields/{field_id}", status_code=204)
def delete_custom_field(field_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_accounting_custom_field(db, field_id):
        raise HTTPException(status_code=404, detail="Field not found")

@router.patch("/clients/{client_id}/custom-values")
def update_client_custom_values(
    client_id: UUID,
    payload: schemas.AccountingValuesUpdate,
    db: Session = Depends(get_db)
):
    updates = [{"field_id": v.field_id, "value": v.value} for v in payload.values]
    crud.set_client_custom_field_values(db, client_id, updates)
    return {"status": "updated"}