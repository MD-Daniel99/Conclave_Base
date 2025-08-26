# app/api/stages.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app import schemas, crud
from app.db import get_db
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/", response_model=List[schemas.StageRead])
def api_list_stages(db: Session = Depends(get_db)):
    return crud.list_stages(db)

@router.get("/{stage_code}", response_model=schemas.StageRead)
def api_get_stage(stage_code: str, db: Session = Depends(get_db)):
    s = crud.get_stage(db, stage_code)
    if not s:
        raise HTTPException(status_code=404, detail="Stage not found")
    return s

@router.post("/", response_model=schemas.StageRead, status_code=status.HTTP_201_CREATED)
def api_create_stage(payload: schemas.StageCreate, db: Session = Depends(get_db)):
    try:
        stage = crud.create_stage(db, payload)
        return stage
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
