# app/api/status.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app import schemas, crud
from app.db import get_db
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/", response_model=List[schemas.StatusRead])
def api_list_statuses(db: Session = Depends(get_db)):
    return crud.list_statuses(db)

@router.get("/{status_code}", response_model=schemas.StatusRead)
def api_get_status(status_code: str, db: Session = Depends(get_db)):
    s = crud.get_status(db, status_code)
    if not s:
        raise HTTPException(status_code=404, detail="Status not found")
    return s

@router.post("/", response_model=schemas.StatusRead, status_code=status.HTTP_201_CREATED)
def api_create_status(payload: schemas.StatusCreate, db: Session = Depends(get_db)):
    try:
        st = crud.create_status(db, payload)
        return st
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
