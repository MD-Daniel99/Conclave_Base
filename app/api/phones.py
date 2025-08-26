# app/api/phones.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db

router = APIRouter()

@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_phone(phone_id: int, db: Session = Depends(get_db)):
    """
    Удаление телефона по его ID.
    """
    ok = crud.delete_phone(db, phone_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
    return None