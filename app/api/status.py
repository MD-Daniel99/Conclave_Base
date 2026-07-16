# app/api/status.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas
from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.services.audit import log_action

router = APIRouter()


@router.get("/", response_model=List[schemas.StatusRead])
def api_list_statuses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_statuses(db)


@router.get("/{status_code}", response_model=schemas.StatusRead)
def api_get_status(
    status_code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    status_obj = crud.get_status(db, status_code)
    if not status_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status not found")
    return status_obj


@router.post("/", response_model=schemas.StatusRead, status_code=status.HTTP_201_CREATED)
def api_create_status(
    payload: schemas.StatusCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        status_obj = crud.create_status(db, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")
    log_action(db, entity="system", entity_id=current_user.user_id, action="status.create", user=current_user, after={"status_code": status_obj.status_code, "description": status_obj.description})
    return status_obj
