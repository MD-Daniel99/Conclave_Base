from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.post("/", response_model=schemas.ModuleComponentRead, status_code=status.HTTP_201_CREATED)
def create_component(
    payload: schemas.ModuleComponentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        item = crud.create_component(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(db, entity="component", entity_id=item.component_id, action="create", user=current_user, after=item)
    return item


@router.get("/", response_model=List[schemas.ModuleComponentRead])
def list_components(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=100000),
    q: str | None = None,
    supplier: str | None = None,
    module_id: UUID | None = None,
    unassigned: bool = False,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    return crud.list_components(db, skip, limit, q, supplier, module_id, unassigned)


@router.patch("/{component_id}", response_model=schemas.ModuleComponentRead)
def update_component(
    component_id: UUID,
    payload: schemas.ModuleComponentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_component(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    before_snapshot = snapshot(before)
    try:
        item = crud.update_component(db, component_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(db, entity="component", entity_id=component_id, action="update", user=current_user, before=before_snapshot, after=item)
    return item


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_component(
    component_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_component(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    before_snapshot = snapshot(before)
    crud.delete_component(db, component_id)
    log_action(db, entity="component", entity_id=component_id, action="delete", user=current_user, before=before_snapshot)
    return None
