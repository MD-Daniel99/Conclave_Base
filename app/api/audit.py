# app/api/audit.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app import models, schemas
from app.db import get_db
from app.api.deps import get_current_user, require_admin
from app.services.audit import list_audit_for_entity, list_recent_audit

router = APIRouter()


@router.get("/entity/{entity}/{entity_id}", response_model=List[schemas.AuditLogRead])
def api_entity_audit(
    entity: str,
    entity_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return list_audit_for_entity(db, entity=entity, entity_id=entity_id, skip=skip, limit=limit)


@router.get("/recent", response_model=List[schemas.AuditLogRead])
def api_recent_audit(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return list_recent_audit(db, skip=skip, limit=limit)
