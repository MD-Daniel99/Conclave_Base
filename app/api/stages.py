# app/api/stages.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas
from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.services.audit import log_action

router = APIRouter()


@router.get("/", response_model=List[schemas.StageRead])
def api_list_stages(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_stages(db)


@router.get("/{stage_code}", response_model=schemas.StageRead)
def api_get_stage(
    stage_code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stage = crud.get_stage(db, stage_code)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found")
    return stage


@router.post("/", response_model=schemas.StageRead, status_code=status.HTTP_201_CREATED)
def api_create_stage(
    payload: schemas.StageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    try:
        stage = crud.create_stage(db, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"DB error: {e}")
    log_action(db, entity="system", entity_id=current_user.user_id, action="stage.create", user=current_user, after={"stage_code": stage.stage_code, "description": stage.description})
    return stage
