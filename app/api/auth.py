# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import schemas, crud
from app.db import get_db
from uuid import UUID

router = APIRouter()

@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, payload.username)
    if not user or not crud.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")
    
    if not user.is_active:
         raise HTTPException(status_code=403, detail="Пользователь заблокирован")

    return {
        "access_token": "fake-jwt-token", 
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.user_id
    }

@router.post("/register", response_model=schemas.UserRead)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    # В реальном проде этот эндпоинт надо закрыть (доступ только админу)
    if crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    return crud.create_user(db, payload)

@router.get("/users", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db)):
    # Для админки
    from app import models
    return db.query(models.User).all()

@router.patch("/users/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: UUID, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    try:
        user = crud.update_user(db, user_id, payload)
        if not user: raise HTTPException(404, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    if not crud.delete_user(db, user_id): raise HTTPException(404, detail="User not found")