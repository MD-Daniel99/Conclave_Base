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
def api_create_component(
    payload: schemas.ModuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        component = crud.create_module(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")
    log_action(db, entity="component", entity_id=component.module_id, action="create", user=current_user, after=component)
    return component


@router.get("/", response_model=List[schemas.ModuleRead])
def api_list_components(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=100000),
    q: str | None = None,
    supplier: str | None = None,
    client_id: UUID | None = None,
    unassigned: bool = False,
    archived: bool = False,
    in_stock: bool | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_modules(db, skip, limit, q, supplier, client_id, unassigned, archived, in_stock)


@router.get("/stock/count", response_model=int)
def api_count_stock_components(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.count_stock_module_units(db)


@router.get("/{component_id}", response_model=schemas.ModuleRead)
def api_get_component(
    component_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    component = crud.get_module(db, component_id)
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    return component


@router.patch("/{component_id}", response_model=schemas.ModuleRead)
def api_update_component(
    component_id: UUID,
    payload: schemas.ModuleUpdate,
    operation_quantity: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_module(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    before_snapshot = snapshot(before)
    try:
        updated = crud.update_module(db, component_id, payload, operation_quantity=operation_quantity)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    log_action(db, entity="component", entity_id=component_id, action="update", user=current_user, before=before_snapshot, after=updated)
    return updated


def _change_component_archive_state(
    component_id: UUID,
    *,
    is_archived: bool,
    quantity: int,
    db: Session,
    current_user: models.User,
):
    before = crud.get_module(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    before_snapshot = snapshot(before)

    try:
        updated = crud.set_module_archive_state(
            db,
            component_id,
            is_archived=is_archived,
            quantity=quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        entity="component",
        entity_id=component_id,
        action="component.archive" if is_archived else "component.restore",
        user=current_user,
        before=before_snapshot,
        after=updated,
    )
    return updated


@router.post("/{component_id}/archive", response_model=schemas.ModuleRead)
def api_archive_component(
    component_id: UUID,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_component_archive_state(
        component_id,
        is_archived=True,
        quantity=quantity,
        db=db,
        current_user=current_user,
    )


@router.post("/{component_id}/restore", response_model=schemas.ModuleRead)
def api_restore_component(
    component_id: UUID,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_component_archive_state(
        component_id,
        is_archived=False,
        quantity=quantity,
        db=db,
        current_user=current_user,
    )


def _change_component_stock_state(
    component_id: UUID,
    *,
    is_in_stock: bool,
    quantity: int,
    db: Session,
    current_user: models.User,
):
    before = crud.get_module(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    before_snapshot = snapshot(before)

    try:
        updated = crud.set_module_stock_state(db, component_id, is_in_stock=is_in_stock, quantity=quantity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        entity="component",
        entity_id=component_id,
        action="component.stock" if is_in_stock else "component.work_stock",
        user=current_user,
        before=before_snapshot,
        after=updated,
    )
    return updated


@router.post("/{component_id}/stock", response_model=schemas.ModuleRead)
def api_move_component_to_stock(
    component_id: UUID,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_component_stock_state(
        component_id,
        is_in_stock=True,
        quantity=quantity,
        db=db,
        current_user=current_user,
    )


@router.post("/{component_id}/work-stock", response_model=schemas.ModuleRead)
def api_move_component_to_work_stock(
    component_id: UUID,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_component_stock_state(
        component_id,
        is_in_stock=False,
        quantity=quantity,
        db=db,
        current_user=current_user,
    )


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_component(
    component_id: UUID,
    quantity: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_module(db, component_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    before_snapshot = snapshot(before)
    try:
        deleted = crud.delete_module(db, component_id, quantity=quantity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Комплектующая не найдена")
    log_action(db, entity="component", entity_id=component_id, action="delete", user=current_user, before=before_snapshot)
    return None
