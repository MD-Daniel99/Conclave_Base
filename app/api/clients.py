# app/api/clients.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action, snapshot

router = APIRouter()


@router.post("/", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    client_in: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        client = crud.create_client(db, client_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    log_action(db, entity="client", entity_id=client["client_id"], action="create", user=current_user, after=client)
    return client


@router.get("/", response_model=List[schemas.ClientRead])
def read_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100000),
    q: str | None = Query(None),
    status: str | None = Query(None),
    agent_id: UUID | None = Query(None),
    current_stage: str | None = Query(None),
    archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_clients(db, skip, limit, q, status, agent_id, current_stage, archived)


@router.get("/{client_id}", response_model=schemas.ClientRead)
def read_client(
    client_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=schemas.ClientRead)
def patch_client(
    client_id: UUID,
    payload: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_client(db, client_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    updated = crud.update_client(db, client_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    log_action(db, entity="client", entity_id=client_id, action="update", user=current_user, before=before, after=updated)
    return updated


@router.patch("/{client_id}/components/tsr", response_model=List[schemas.ModuleRead])
def assign_tsr_to_client_components(
    client_id: UUID,
    payload: schemas.ClientComponentsTsrUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        components = crud.assign_tsr_to_client_modules(
            db,
            client_id,
            payload.component_ids,
            payload.tsr_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="components.tsr.assign",
        user=current_user,
        details={
            "component_ids": [str(component_id) for component_id in payload.component_ids],
            "tsr_id": str(payload.tsr_id),
        },
    )
    return components


@router.patch("/{client_id}/components/prosthetist", response_model=List[schemas.ModuleRead])
def set_client_components_prosthetist_state(
    client_id: UUID,
    payload: schemas.ClientComponentsProsthetistUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        components = crud.set_client_modules_prosthetist_state(
            db,
            client_id,
            payload.client_tsr_id,
            payload.component_ids,
            at_prosthetist=payload.at_prosthetist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action=(
            "components.prosthetist.assign"
            if payload.at_prosthetist
            else "components.prosthetist.return"
        ),
        user=current_user,
        details={
            "client_tsr_id": str(payload.client_tsr_id),
            "component_ids": [str(component_id) for component_id in payload.component_ids],
            "at_prosthetist": payload.at_prosthetist,
        },
    )
    return components


@router.get("/{client_id}/tsr", response_model=List[schemas.ClientTsrRead])
def read_client_tsr(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return crud.list_client_tsr(db, client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{client_id}/tsr", response_model=schemas.ClientTsrRead, status_code=status.HTTP_201_CREATED)
def attach_client_tsr(
    client_id: UUID,
    payload: schemas.ClientTsrCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        item = crud.create_client_tsr(db, client_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="client_tsr.create",
        user=current_user,
        after=item,
        details={
            "subject_label": "ТСР",
            "subject_name": str(item.tsr.full_tsr_code or "").strip() if item.tsr else "",
        },
    )
    return item


@router.patch("/{client_id}/tsr/{client_tsr_id}", response_model=schemas.ClientTsrRead)
def patch_client_tsr(
    client_id: UUID,
    client_tsr_id: UUID,
    payload: schemas.ClientTsrUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before_item = next(
        (item for item in crud.list_client_tsr(db, client_id) if item.client_tsr_id == client_tsr_id),
        None,
    )
    before_snapshot = snapshot(before_item) if before_item else None
    updated = crud.update_client_tsr(db, client_id, client_tsr_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ТСР клиента не найден")
    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="client_tsr.update",
        user=current_user,
        before=before_snapshot,
        after=updated,
        details={
            "subject_label": "ТСР",
            "subject_name": str(updated.tsr.full_tsr_code or "").strip() if updated.tsr else "",
        },
    )
    return updated


@router.delete("/{client_id}/tsr/{client_tsr_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_client_tsr(
    client_id: UUID,
    client_tsr_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before_item = next(
        (item for item in crud.list_client_tsr(db, client_id) if item.client_tsr_id == client_tsr_id),
        None,
    )
    before_snapshot = snapshot(before_item) if before_item else None
    subject_name = (
        str(before_item.tsr.full_tsr_code or "").strip()
        if before_item and before_item.tsr
        else ""
    )
    try:
        deleted = crud.delete_client_tsr(db, client_id, client_tsr_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ТСР клиента не найден")
    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action="client_tsr.delete",
        user=current_user,
        before=before_snapshot,
        details={
            "subject_label": "ТСР",
            "subject_name": subject_name,
        },
    )
    return None


def _change_client_archive_state(
    client_id: UUID,
    *,
    is_archived: bool,
    db: Session,
    current_user: models.User,
):
    before = crud.get_client(db, client_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    updated = crud.set_client_archive_state(db, client_id, is_archived=is_archived)
    action = "archive" if is_archived else "restore"
    log_action(
        db,
        entity="client",
        entity_id=client_id,
        action=action,
        user=current_user,
        before=before,
        after=updated,
    )
    return updated


@router.post("/{client_id}/archive", response_model=schemas.ClientRead)
def archive_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_client_archive_state(
        client_id,
        is_archived=True,
        db=db,
        current_user=current_user,
    )


@router.post("/{client_id}/restore", response_model=schemas.ClientRead)
def restore_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _change_client_archive_state(
        client_id,
        is_archived=False,
        db=db,
        current_user=current_user,
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_client(db, client_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    if not crud.delete_client(db, client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    log_action(db, entity="client", entity_id=client_id, action="delete", user=current_user, before=before)
    return None


@router.post("/{client_id}/phones", response_model=schemas.PhoneRead, status_code=status.HTTP_201_CREATED)
def create_phone_for_client(
    client_id: UUID,
    payload: schemas.PhoneCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        phone = crud.add_phone(db, client_id, payload.number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    log_action(db, entity="client", entity_id=client_id, action="phone.create", user=current_user, after=phone)
    return phone


@router.get("/{client_id}/phones", response_model=List[schemas.PhoneRead])
def get_phones_for_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_phones(db, client_id)


@router.post("/{client_id}/passports", response_model=schemas.PassportRead, status_code=status.HTTP_201_CREATED)
def create_passport_for_client(
    client_id: UUID,
    payload: schemas.PassportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        passport = crud.create_passport(db, client_id, payload)
    except ValueError as e:
        code = status.HTTP_409_CONFLICT if "уже" in str(e).lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(e))
    log_action(db, entity="client", entity_id=client_id, action="passport.create", user=current_user, after=passport)
    return passport


@router.post("/{client_id}/snils", response_model=schemas.SnilsRead, status_code=status.HTTP_201_CREATED)
def create_snils_for_client(
    client_id: UUID,
    payload: schemas.SnilsCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        snils = crud.create_snils(db, client_id, payload)
    except ValueError as e:
        code = status.HTTP_409_CONFLICT if "уже" in str(e).lower() else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=str(e))
    log_action(db, entity="client", entity_id=client_id, action="snils.create", user=current_user, after=snils)
    return snils
