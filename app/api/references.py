from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from app.db import get_db
from app import schemas, crud
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/prosthesis", response_model = List[schemas.ProsthesisRefRead])
def list_prosthesist(db: Session = Depends(get_db)):
    return crud.get_prosthesis(db)

@router.post("/prosthesis", response_model = schemas.ProsthesisRefRead)
def add_prosthesis(payload: schemas.ProsthesisRefCreate, db: Session = Depends(get_db)):
    return crud.create_prosthesis(db, payload.name)

@router.delete("/prosthesis/{prosthesis_id}", status_code = 204)
def remove_prosthesis(prosthesis_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_prosthesis(db, prosthesis_id):
        raise HTTPException(404)

@router.get("/tsr", response_model = List[schemas.TstCodeRefRead])
def list_tsr(db: Session = Depends(get_db)):
    return crud.get_tsr(db)

@router.post("/tsr", response_model = schemas.TstCodeRefRead)
def add_tsr(payload: schemas.TstCodeRefCreate, db: Session = Depends(get_db)):
    return crud.create_tsr(db, payload.full_tsr_code)

@router.delete("/tsr/{tsr_id}", status_code = 204)
def remove_tsr(tsr_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_tsr(db, tsr_id):
        raise HTTPException(404)

# !!!!

@router.get("/name_index", response_model = List[schemas.ModuleNameIndexRead])
def list_module_name_index(db: Session = Depends(get_db)):
    return crud.get_module_name_index(db)

@router.post("/name_index", response_model = schemas.ModuleNameIndexRead)
def add_module_name_index(payload: schemas.ModuleNameIndexCreate, db: Session = Depends(get_db)):
    return crud.create_module_name_index(db, payload.name_index)

@router.delete("/name_index/{module_id}", status_code = 204)
def remove_module_name_index(module_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_module_name_index(db, module_id):
        raise HTTPException(404)

