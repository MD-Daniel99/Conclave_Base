# app/api/passports.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app import schemas, crud
from app.db import get_db

router = APIRouter()

@router.patch("/{passport_id}", response_model=schemas.PassportRead)
def api_update_passport(passport_id: UUID, payload: schemas.PassportUpdate, db: Session = Depends(get_db)):
    """
    Частичное обновление паспорта.
    """
    # Преобразуем Pydantic модель в словарь, исключая неустановленные значения
    update_data = payload.model_dump(exclude_unset=True)
    
    # Вызываем CRUD функцию для обновления
    updated_passport = crud.update_passport(db, passport_id, update_data)
    
    if not updated_passport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found")
        
    return updated_passport

@router.delete("/{passport_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_passport(passport_id: UUID, db: Session = Depends(get_db)):
    ok = crud.delete_passport(db, passport_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found")
    return None