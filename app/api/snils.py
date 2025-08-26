# app/api/snils.py
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from sqlalchemy.orm import Session

from app import schemas, crud
from app.db import get_db

router = APIRouter()

@router.patch("/{snils_id}", response_model=schemas.SnilsRead)
def api_update_snils(snils_id: UUID, payload: schemas.SnilsUpdate, db: Session = Depends(get_db)):
    """
    Частичное обновление СНИЛС.
    """
    update_data = payload.model_dump(exclude_unset=True)
    updated_snils = crud.update_snils(db, snils_id, update_data)
    
    if not updated_snils:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snils not found")
        
    return updated_snils