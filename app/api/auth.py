# app/api/auth.py
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api.deps import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_self_or_admin,
)
from app.db import get_db
from app.schemas import UserSettingsUpdate
from app.services.audit import log_action

try:
    from app.config import settings
except ImportError:
    from config import settings

router = APIRouter()


def _users_count(db: Session) -> int:
    return db.query(models.User).count()


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, payload.username)
    if not user or not crud.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверное имя пользователя или пароль")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    access_token = create_access_token(
        subject=user.user_id,
        expires_delta=timedelta(minutes=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24)),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.user_id,
    }


@router.get("/me", response_model=schemas.UserRead)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    """Создание пользователя.

    Первый пользователь может быть создан без токена и принудительно получает роль admin.
    Все последующие регистрации доступны только администратору.
    """
    is_bootstrap = _users_count(db) == 0
    if not is_bootstrap:
        if current_user is None or str(current_user.role).lower() != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Создавать пользователей может только администратор")

    if crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь уже существует")

    create_payload = payload.model_copy(update={"role": "admin" if is_bootstrap else payload.role})
    user = crud.create_user(db, create_payload)
    log_action(
        db,
        entity="user",
        entity_id=user.user_id,
        action="create",
        user=current_user,
        after=user,
        details={"bootstrap": is_bootstrap},
    )
    return user


@router.get("/users", response_model=list[schemas.UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.patch("/users/{user_id}", response_model=schemas.UserRead)
def update_user(
    user_id: UUID,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)

    is_admin = str(current_user.role).lower() == "admin"
    if not is_admin and (payload.role is not None or payload.is_active is not None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Роль и активность может менять только администратор")

    before = crud.get_user(db, user_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id == current_user.user_id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя заблокировать самого себя")
    if user_id == current_user.user_id and payload.role is not None and payload.role != current_user.role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя изменить собственную роль")

    before_snapshot = {c.name: getattr(before, c.name) for c in before.__table__.columns if c.name != "password_hash"}
    try:
        user = crud.update_user(db, user_id, payload)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    after_snapshot = {c.name: getattr(user, c.name) for c in user.__table__.columns if c.name != "password_hash"}
    log_action(db, entity="user", entity_id=user.user_id, action="update", user=current_user, before=before_snapshot, after=after_snapshot)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if user_id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить собственный аккаунт")
    before = crud.get_user(db, user_id)
    if not before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    before_snapshot = {c.name: getattr(before, c.name) for c in before.__table__.columns if c.name != "password_hash"}
    if not crud.delete_user(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    log_action(db, entity="user", entity_id=user_id, action="delete", user=current_user, before=before_snapshot)
    return None


@router.get("/users/{user_id}/settings")
def get_user_settings(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user.settings or {}


@router.patch("/users/{user_id}/settings")
def patch_user_settings(
    user_id: UUID,
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)
    before_user = crud.get_user(db, user_id)
    if not before_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    before = before_user.settings or {}
    user = crud.update_user_settings(db, user_id, payload.model_dump(exclude_unset=True))
    log_action(db, entity="user", entity_id=user_id, action="settings.update", user=current_user, before=before, after=user.settings or {})
    return {"status": "ok"}
