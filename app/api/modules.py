# app/api/modules.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.post("/", response_model=schemas.ModuleRead, status_code=status.HTTP_201_CREATED)
def api_create_module(
    payload: schemas.ModuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        module = crud.create_module(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")
    log_action(db, entity="module", entity_id=module.module_id, action="create", user=current_user, after=module)
    return module


@router.get("/", response_model=List[schemas.ModuleRead])
def api_list_modules(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=100000),
    q: str | None = None,
    supplier: str | None = None,
    client_id: UUID | None = None,
    unassigned: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_modules(db, skip, limit, q, supplier, client_id, unassigned)


@router.get("/{module_id}", response_model=schemas.ModuleRead)
def api_get_module(
    module_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    module = crud.get_module(db, module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


@router.patch("/{module_id}", response_model=schemas.ModuleRead)
def api_update_module(
    module_id: UUID,
    payload: schemas.ModuleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_module(db, module_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    before_snapshot = snapshot(before)
    try:
        updated = crud.update_module(db, module_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    log_action(db, entity="module", entity_id=module_id, action="update", user=current_user, before=before_snapshot, after=updated)
    return updated


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_module(
    module_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_module(db, module_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    before_snapshot = snapshot(before)
    if not crud.delete_module(db, module_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    log_action(db, entity="module", entity_id=module_id, action="delete", user=current_user, before=before_snapshot)
    return None
