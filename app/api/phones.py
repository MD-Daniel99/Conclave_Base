
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
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

@router.patch("/{phone_id}", response_model=schemas.PhoneRead)
def api_update_phone(phone_id: int, payload: schemas.PhoneUpdate, db: Session = Depends(get_db)):
    update_data = payload.model_dump(exclude_unset=True)
    updated_phone = crud.update_phone(db, phone_id, update_data)
    
    if not updated_phone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone not found")
        
    return updated_phone