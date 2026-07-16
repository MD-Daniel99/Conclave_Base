# app/api/agents.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app import crud, models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action

router = APIRouter()


@router.post("/", response_model=schemas.AgentRead, status_code=status.HTTP_201_CREATED)
def api_create_agent(
    payload: schemas.AgentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        agent = crud.create_agent(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent with such INN/OGRNIP might already exist.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")
    log_action(db, entity="agent", entity_id=agent["agent_id"], action="create", user=current_user, after=agent)
    return agent


@router.get("/", response_model=List[schemas.AgentRead])
def api_list_agents(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=100000),
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.list_agents(db, skip=skip, limit=limit, q=q)


@router.get("/by-external/{external_id}", response_model=schemas.AgentRead)
def api_get_agent_by_external(
    external_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    agent = crud.get_agent_by_external(db, external_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.get("/{agent_id}", response_model=schemas.AgentRead)
def api_get_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    agent = crud.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=schemas.AgentRead)
def api_update_agent(
    agent_id: UUID,
    payload: schemas.AgentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_agent(db, agent_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    updated = crud.update_agent(db, agent_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    log_action(db, entity="agent", entity_id=agent_id, action="update", user=current_user, before=before, after=updated)
    return updated


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    before = crud.get_agent(db, agent_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    try:
        ok = crud.delete_agent(db, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    log_action(db, entity="agent", entity_id=agent_id, action="delete", user=current_user, before=before)
    return None
