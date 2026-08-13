# app/api/references.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.get("/prosthesis", response_model=List[schemas.ProsthesisRefRead])
def list_prosthesis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_prosthesis(db)


@router.post("/prosthesis", response_model=schemas.ProsthesisRefRead, status_code=status.HTTP_201_CREATED)
def add_prosthesis(
    payload: schemas.ProsthesisRefCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        item = crud.create_prosthesis(db, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_action(db, entity="reference", entity_id=item.prosthesis_id, action="prosthesis.upsert", user=current_user, after=item)
    return item


@router.put("/prosthesis/{prosthesis_id}", response_model=schemas.ProsthesisRefRead)
def update_prosthesis(
    prosthesis_id: UUID,
    payload: schemas.ProsthesisRefUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.ProsthesisRef, prosthesis_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prosthesis reference not found")
    before_snapshot = snapshot(before)
    try:
        item = crud.update_prosthesis(db, prosthesis_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prosthesis reference not found")
    log_action(db, entity="reference", entity_id=item.prosthesis_id, action="prosthesis.update", user=current_user, before=before_snapshot, after=item)
    return item


@router.delete("/prosthesis/{prosthesis_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_prosthesis(
    prosthesis_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.ProsthesisRef, prosthesis_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prosthesis reference not found")
    before_snapshot = snapshot(before)
    try:
        deleted = crud.delete_prosthesis(db, prosthesis_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prosthesis reference not found")
    log_action(db, entity="reference", entity_id=prosthesis_id, action="prosthesis.delete", user=current_user, before=before_snapshot)
    return None


@router.get("/tsr", response_model=List[schemas.TstCodeRefRead])
def list_tsr(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_tsr(db)


@router.post("/tsr", response_model=schemas.TstCodeRefRead, status_code=status.HTTP_201_CREATED)
def add_tsr(
    payload: schemas.TstCodeRefCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        item = crud.create_tsr(db, payload.full_tsr_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_action(db, entity="reference", entity_id=item.tsr_id, action="tsr.upsert", user=current_user, after=item)
    return item


@router.put("/tsr/{tsr_id}", response_model=schemas.TstCodeRefRead)
def update_tsr(
    tsr_id: UUID,
    payload: schemas.TstCodeRefUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.TstCodeRef, tsr_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TSR reference not found")
    before_snapshot = snapshot(before)
    try:
        item = crud.update_tsr(db, tsr_id, payload.full_tsr_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TSR reference not found")
    log_action(db, entity="reference", entity_id=item.tsr_id, action="tsr.update", user=current_user, before=before_snapshot, after=item)
    return item


@router.delete("/tsr/{tsr_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tsr(
    tsr_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.TstCodeRef, tsr_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TSR reference not found")
    before_snapshot = snapshot(before)
    try:
        deleted = crud.delete_tsr(db, tsr_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TSR reference not found")
    log_action(db, entity="reference", entity_id=tsr_id, action="tsr.delete", user=current_user, before=before_snapshot)
    return None


@router.get("/name_index", response_model=List[schemas.ModuleNameIndexRead])
def list_module_name_index(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_module_name_index(db)


@router.post("/name_index", response_model=schemas.ModuleNameIndexRead, status_code=status.HTTP_201_CREATED)
def add_module_name_index(
    payload: schemas.ModuleNameIndexCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        item = crud.create_module_name_index(db, payload.name_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_action(db, entity="reference", entity_id=item.name_index_id, action="name_index.upsert", user=current_user, after=item)
    return item


@router.put("/name_index/{name_index_id}", response_model=schemas.ModuleNameIndexRead)
def update_module_name_index(
    name_index_id: UUID,
    payload: schemas.ModuleNameIndexUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.ModuleNameIndex, name_index_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Name index reference not found")
    before_snapshot = snapshot(before)
    try:
        item = crud.update_module_name_index(db, name_index_id, payload.name_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Name index reference not found")
    log_action(
        db,
        entity="reference",
        entity_id=item.name_index_id,
        action="name_index.update",
        user=current_user,
        before=before_snapshot,
        after=item,
    )
    return item


@router.delete("/name_index/{name_index_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_module_name_index(
    name_index_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    before = db.get(models.ModuleNameIndex, name_index_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Name index reference not found")
    before_snapshot = snapshot(before)
    try:
        deleted = crud.delete_module_name_index(db, name_index_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Name index reference not found")
    log_action(db, entity="reference", entity_id=name_index_id, action="name_index.delete", user=current_user, before=before_snapshot)
    return None
