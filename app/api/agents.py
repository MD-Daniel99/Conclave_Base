from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID

from app import schemas, crud
from app.db import get_db
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/", response_model=schemas.AgentRead, status_code=status.HTTP_201_CREATED)
def api_create_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    try:
        agent = crud.create_agent(db, payload)
        return agent
    except Exception as e:
        # можно уточнить ошибки IntegrityError -> 400, другое -> 500 и т.д.
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


@router.get("/", response_model=List[schemas.AgentRead])
def api_list_agents(skip: int = 0, limit: int = 50, q: Optional[str] = None, db: Session = Depends(get_db)):
    return crud.list_agents(db, skip=skip, limit=limit, q=q)


@router.get("/by-external/{external_id}", response_model=schemas.AgentRead)
def api_get_agent_by_external(external_id: int, db: Session = Depends(get_db)):
    ag = crud.get_agent_by_external(db, external_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ag


@router.get("/{agent_id}", response_model=schemas.AgentRead)
def api_get_agent(agent_id: UUID, db: Session = Depends(get_db)):
    ag = crud.get_agent(db, agent_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ag


@router.patch("/{agent_id}", response_model=schemas.AgentRead)
def api_update_agent(agent_id: UUID, payload: schemas.AgentUpdate, db: Session = Depends(get_db)):
    res = crud.update_agent(db, agent_id, payload.model_dump(exclude_unset=True))
    if not res:
        raise HTTPException(status_code=404, detail="Agent not found")
    return res


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_delete_agent(agent_id: UUID, db: Session = Depends(get_db)):
    try:
        ok = crud.delete_agent(db, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return None
