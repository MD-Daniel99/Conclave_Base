# app/api/snils.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.patch("/{snils_id}", response_model=schemas.SnilsRead)
def api_update_snils(
    snils_id: UUID,
    payload: schemas.SnilsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = db.get(models.Snils, snils_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snils not found")
    client_id = before.client_id
    before_snapshot = snapshot(before)
    updated = crud.update_snils(db, snils_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snils not found")
    log_action(db, entity="client", entity_id=client_id, action="snils.update", user=current_user, before=before_snapshot, after=updated)
    return updated


@router.delete("/{snils_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_snils(
    snils_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = db.get(models.Snils, snils_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SNILS not found")
    client_id = before.client_id
    before_snapshot = snapshot(before)
    if not crud.delete_snils(db, snils_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SNILS not found")
    log_action(db, entity="client", entity_id=client_id, action="snils.delete", user=current_user, before=before_snapshot)
    return None
