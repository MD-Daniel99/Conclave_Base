# app/api/clients.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_clients(db, skip, limit, q, status, agent_id, current_stage)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    log_action(db, entity="client", entity_id=client_id, action="snils.create", user=current_user, after=snils)
    return snils
