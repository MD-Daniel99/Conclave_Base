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
from typing import List
from uuid import UUID

from app import schemas, crud
from app.db import get_db

router = APIRouter()


@router.post("/", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(client_in: schemas.ClientCreate, db: Session = Depends(get_db)):
    try:
        client_dict = crud.create_client(db, client_in)
    except ValueError as ve:
        # заранее пойманные ошибки (например, Agent not found)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="DB error: " + str(e))
    return client_dict


@router.get("/", response_model=List[schemas.ClientRead])
def read_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
    status: str | None = Query(None),
    agent_id: UUID | None = Query(None),
    current_stage: str | None = Query(None), # <--- ИЗМЕНЕНИЕ: Добавлен фильтр
    db: Session = Depends(get_db),
):
    clients = crud.list_clients(
        db, skip=skip, limit=limit, q=q, status=status, agent_id=agent_id, current_stage=current_stage
    )
    return clients


@router.get("/{client_id}", response_model=schemas.ClientRead)
def read_client(client_id: UUID = Path(...), db: Session = Depends(get_db)):
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=schemas.ClientRead)
def patch_client(client_id: UUID, payload: schemas.ClientUpdate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True) # ИЗМЕНЕНИЕ: .dict() устарел в Pydantic v2
    updated = crud.update_client(db, client_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: UUID, db: Session = Depends(get_db)):
    ok = crud.delete_client(db, client_id)
    if not ok:
        raise HTTPException(status_code = 404, detail="Client not found")
    return None


# --- Nested endpoints ---
@router.post("/{client_id}/phones", response_model=schemas.PhoneRead, status_code=status.HTTP_201_CREATED)
def create_phone_for_client(client_id: UUID, payload: schemas.PhoneCreate, db: Session = Depends(get_db)):
    try:
        phone = crud.add_phone(db, client_id, payload.number)
    except ValueError as ve:
        raise HTTPException(status_code = 404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code = 500, detail="DB error: " + str(e))
    return phone


@router.get("/{client_id}/phones", response_model=List[schemas.PhoneRead])
def get_phones_for_client(client_id: UUID, db: Session = Depends(get_db)):
    phones = crud.list_phones(db, client_id)
    return phones


# --- НОВЫЕ ЭНДПОИНТЫ ДЛЯ ДОКУМЕНТОВ ---

@router.post("/{client_id}/passports", response_model=schemas.PassportRead, status_code=status.HTTP_201_CREATED)
def create_passport_for_client(client_id: UUID, payload: schemas.PassportCreate, db: Session = Depends(get_db)):
    try:
        passport = crud.create_passport(db, client_id, payload)
        return passport
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")

@router.post("/{client_id}/snils", response_model=schemas.SnilsRead, status_code=status.HTTP_201_CREATED)
def create_snils_for_client(client_id: UUID, payload: schemas.SnilsCreate, db: Session = Depends(get_db)):
    try:
        snils = crud.create_snils(db, client_id, payload)
        return snils
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")