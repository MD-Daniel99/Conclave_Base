# app/api/phones.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_phone(
    phone_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = db.get(models.Phone, phone_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
    client_id = before.client_id
    before_snapshot = snapshot(before)
    if not crud.delete_phone(db, phone_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
    log_action(db, entity="client", entity_id=client_id, action="phone.delete", user=current_user, before=before_snapshot)
    return None


@router.patch("/{phone_id}", response_model=schemas.PhoneRead)
def api_update_phone(
    phone_id: int,
    payload: schemas.PhoneUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = db.get(models.Phone, phone_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
    client_id = before.client_id
    before_snapshot = snapshot(before)
    updated = crud.update_phone(db, phone_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
    log_action(db, entity="client", entity_id=client_id, action="phone.update", user=current_user, before=before_snapshot, after=updated)
    return updated
