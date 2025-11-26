# app/api/modules.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app import schemas, crud
from app.db import get_db

router = APIRouter()

@router.post("/", response_model=schemas.ModuleRead, status_code=201)
def api_create_module(payload: schemas.ModuleCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_module(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

@router.get("/", response_model=List[schemas.ModuleRead])
def api_list_modules(
    skip: int = 0, limit: int = Query(100, ge=1, le=100000),  
    q: str = None, supplier: str = None, client_id: UUID = None, 
    db: Session = Depends(get_db)
):
    return crud.list_modules(db, skip, limit, q, supplier, client_id)

@router.get("/{module_id}", response_model=schemas.ModuleRead)
def api_get_module(module_id: UUID, db: Session = Depends(get_db)):
    m = crud.get_module(db, module_id)
    if not m: raise HTTPException(status_code=404, detail="Module not found")
    return m
# -----------------------------------------------

@router.patch("/{module_id}", response_model=schemas.ModuleRead)
def api_update_module(module_id: UUID, pl: schemas.ModuleUpdate, db: Session = Depends(get_db)):
    try:
        m = crud.update_module(db, module_id, pl)
        if not m: raise HTTPException(404, detail="Module not found")
        return m
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

@router.delete("/{module_id}", status_code=204)
def api_delete_module(module_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_module(db, module_id): raise HTTPException(404, detail="Module not found")