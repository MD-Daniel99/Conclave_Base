''''
Роуты Endpoints для клиентов.
app/api/ — это слой HTTP/REST интерфейса приложения.
Cодержит «роутеры» — модули с набором HTTP-эндпоинтов (маршрутов), 
сгруппированных по сущностям: clients.py, documents.py, agents.py, refdata.py, auth.py и т.д.
Принимает запросы от клиента (браузера/фронтенда/скрипта), валидирует вход (Pydantic), вызывать бизнес-логику/CRUD-слой 
и возвращает ответы (JSON, статус-коды). 
Слоожную логику работы с БД осуществляет crud.py и models.py.
'''

# app/api/clients.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app import schemas, crud
from app.db import get_db

router = APIRouter()


@router.post("/", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(client_in: schemas.ClientCreate, db: Session = Depends(get_db)):
    return crud.create_client(db, client_in)


@router.get("/", response_model=List[schemas.ClientRead])
def read_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100000),
    q: str | None = Query(None),
    status: str | None = Query(None),
    agent_id: UUID | None = Query(None),
    current_stage: str | None = Query(None), 
    db: Session = Depends(get_db),
):
    return crud.list_clients(db, skip, limit, q, status, agent_id, current_stage)



@router.get("/{client_id}", response_model=schemas.ClientRead)
def read_client(client_id: UUID = Path(...), db: Session = Depends(get_db)):
    c = crud.get_client(db, client_id)
    if not c: raise HTTPException(status_code=404)
    return c


@router.patch("/{client_id}", response_model=schemas.ClientRead)
def patch_client(client_id: UUID, payload: schemas.ClientUpdate, db: Session = Depends(get_db)):
    return crud.update_client(db, client_id, payload.model_dump(exclude_unset=True))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: UUID, db: Session = Depends(get_db)):
     if not crud.delete_client(db, client_id): raise HTTPException(404)


# --- Nested endpoints ---
@router.post("/{client_id}/phones", response_model=schemas.PhoneRead, status_code=status.HTTP_201_CREATED)
def create_phone_for_client(client_id: UUID, payload: schemas.PhoneCreate, db: Session = Depends(get_db)):
    return crud.add_phone(db, client_id, payload.number)


@router.get("/{client_id}/phones", response_model=List[schemas.PhoneRead])
def get_phones_for_client(client_id: UUID, db: Session = Depends(get_db)):
    phones = crud.list_phones(db, client_id)
    return phones


@router.post("/{client_id}/passports", response_model=schemas.PassportRead, status_code=status.HTTP_201_CREATED)
def create_passport_for_client(client_id: UUID, payload: schemas.PassportCreate, db: Session = Depends(get_db)):
    return crud.create_passport(db, client_id, payload)


@router.post("/{client_id}/snils", response_model=schemas.SnilsRead, status_code=status.HTTP_201_CREATED)
def create_snils_for_client(client_id: UUID, payload: schemas.SnilsCreate, db: Session = Depends(get_db)):
    return crud.create_snils(db, client_id, payload)