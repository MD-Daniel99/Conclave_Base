from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.api.deps import get_current_user
from app.db import get_db
from app.services.audit import log_action

router = APIRouter()

_ACTIVE_TASK_STATUSES = {"planned", "in_progress"}
_DEADLINE_NOTIFICATION_KINDS = {"due_24h", "due_2h", "overdue"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _user_payload(user: Optional[models.User]) -> dict | None:
    if user is None:
        return None
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
    }


def _task_payload(task: models.Task) -> dict:
    assignees = [assignment.user for assignment in task.assignments if assignment.user and assignment.user.is_active]
    assignees.sort(key=lambda user: (user.username or "").lower())
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "start_at": task.start_at,
        "due_at": task.due_at,
        "all_day": bool(task.all_day),
        "status": task.status,
        "priority": task.priority,
        "color": task.color,
        "created_by": task.created_by,
        "creator": _user_payload(task.creator),
        "assignees": [_user_payload(user) for user in assignees],
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


def _task_query(db: Session):
    return db.query(models.Task).options(
        joinedload(models.Task.creator),
        joinedload(models.Task.assignments).joinedload(models.TaskAssignee.user),
    )


def _get_task_or_404(db: Session, task_id: UUID) -> models.Task:
    task = _task_query(db).filter(models.Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return task


def _load_active_users(db: Session, user_ids: list[UUID]) -> dict[UUID, models.User]:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return {}
    users = (
        db.query(models.User)
        .filter(models.User.user_id.in_(unique_ids), models.User.is_active.is_(True))
        .all()
    )
    result = {user.user_id: user for user in users}
    missing = [str(user_id) for user_id in unique_ids if user_id not in result]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Один или несколько назначенных пользователей не найдены или заблокированы",
        )
    return result


def _upsert_notification(
    db: Session,
    *,
    user_id: UUID,
    task: models.Task,
    kind: str,
    title: str,
    body: str,
    reopen: bool = False,
) -> models.TaskNotification:
    notification = (
        db.query(models.TaskNotification)
        .filter(
            models.TaskNotification.task_id == task.task_id,
            models.TaskNotification.user_id == user_id,
            models.TaskNotification.kind == kind,
        )
        .first()
    )
    if notification:
        notification.title = title
        notification.body = body
        if reopen:
            notification.read_at = None
            notification.created_at = _utc_now()
        return notification

    notification = models.TaskNotification(
        user_id=user_id,
        task_id=task.task_id,
        kind=kind,
        title=title,
        body=body,
    )
    db.add(notification)
    return notification


def _notify_new_assignees(
    db: Session,
    task: models.Task,
    user_ids: set[UUID],
    actor: models.User,
) -> None:
    for user_id in user_ids:
        if user_id == actor.user_id:
            continue
        _upsert_notification(
            db,
            user_id=user_id,
            task=task,
            kind="assigned",
            title="Вам назначена новая задача",
            body=f"{task.title} · срок {_aware(task.due_at).astimezone().strftime('%d.%m.%Y %H:%M')}",
            reopen=True,
        )


def _clear_deadline_notifications(db: Session, task_id: UUID) -> None:
    (
        db.query(models.TaskNotification)
        .filter(
            models.TaskNotification.task_id == task_id,
            models.TaskNotification.kind.in_(_DEADLINE_NOTIFICATION_KINDS),
        )
        .delete(synchronize_session=False)
    )


def _ensure_due_notifications(db: Session, current_user: models.User) -> None:
    now = _utc_now()
    tasks = (
        _task_query(db)
        .outerjoin(models.TaskAssignee, models.TaskAssignee.task_id == models.Task.task_id)
        .filter(
            models.Task.status.in_(_ACTIVE_TASK_STATUSES),
            or_(
                models.TaskAssignee.user_id == current_user.user_id,
                and_(
                    models.Task.created_by == current_user.user_id,
                    ~models.Task.assignments.any(),
                ),
            ),
        )
        .distinct()
        .all()
    )

    for task in tasks:
        due_at = _aware(task.due_at)
        remaining = due_at - now
        kind = None
        title = ""
        body = ""
        if remaining.total_seconds() <= 0:
            kind = "overdue"
            title = "Просрочена задача"
            body = f"{task.title} · срок был {due_at.astimezone().strftime('%d.%m.%Y %H:%M')}"
        elif remaining <= timedelta(hours=2):
            kind = "due_2h"
            title = "Срок задачи уже близко"
            body = f"{task.title} · до дедлайна меньше 2 часов"
        elif remaining <= timedelta(hours=24):
            kind = "due_24h"
            title = "Задача на ближайшие сутки"
            body = f"{task.title} · срок {due_at.astimezone().strftime('%d.%m.%Y %H:%M')}"

        if kind:
            _upsert_notification(
                db,
                user_id=current_user.user_id,
                task=task,
                kind=kind,
                title=title,
                body=body,
            )
    if db.new or db.dirty:
        db.commit()


@router.get("/users", response_model=list[schemas.TaskUserRead])
def list_task_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    del current_user
    return (
        db.query(models.User)
        .filter(models.User.is_active.is_(True))
        .order_by(models.User.username.asc())
        .all()
    )


@router.get("", response_model=list[schemas.TaskRead])
def list_tasks(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    assignee_id: Optional[UUID] = Query(default=None),
    mine: bool = Query(default=False),
    task_status: Optional[schemas.TaskStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = _task_query(db)
    if start is not None:
        query = query.filter(models.Task.due_at >= _aware(start))
    if end is not None:
        query = query.filter(models.Task.start_at <= _aware(end))
    if task_status is not None:
        query = query.filter(models.Task.status == task_status)
    target_user_id = current_user.user_id if mine else assignee_id
    if target_user_id is not None:
        query = query.join(models.TaskAssignee).filter(models.TaskAssignee.user_id == target_user_id)
    tasks = query.order_by(models.Task.start_at.asc(), models.Task.due_at.asc()).all()
    return [_task_payload(task) for task in tasks]


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    del current_user
    return _task_payload(_get_task_or_404(db, task_id))


@router.post("", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = _load_active_users(db, payload.assignee_ids)
    task = models.Task(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        start_at=_aware(payload.start_at),
        due_at=_aware(payload.due_at),
        all_day=payload.all_day,
        status=payload.status,
        priority=payload.priority,
        color=payload.color,
        created_by=current_user.user_id,
        completed_at=_utc_now() if payload.status == "done" else None,
    )
    db.add(task)
    db.flush()
    for user_id in users:
        db.add(models.TaskAssignee(task_id=task.task_id, user_id=user_id, assigned_by=current_user.user_id))
    db.flush()
    _notify_new_assignees(db, task, set(users), current_user)
    db.commit()
    task = _get_task_or_404(db, task.task_id)
    log_action(
        db,
        entity="task",
        entity_id=task.task_id,
        action="create",
        user=current_user,
        after=_task_payload(task),
    )
    return _task_payload(task)


@router.patch("/{task_id}", response_model=schemas.TaskRead)
def update_task(
    task_id: UUID,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_task_or_404(db, task_id)
    before = _task_payload(task)
    data = payload.model_dump(exclude_unset=True)
    assignee_ids = data.pop("assignee_ids", None)

    next_start = _aware(data.get("start_at", task.start_at))
    next_due = _aware(data.get("due_at", task.due_at))
    if next_due < next_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Срок завершения не может быть раньше начала задачи")

    timing_changed = next_start != _aware(task.start_at) or next_due != _aware(task.due_at)
    status_changed = "status" in data and data["status"] != task.status

    if "title" in data:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = data["description"].strip() if data["description"] else None
    if "start_at" in data:
        task.start_at = next_start
    if "due_at" in data:
        task.due_at = next_due
    for key in ("all_day", "priority", "color"):
        if key in data:
            setattr(task, key, data[key])
    if "status" in data:
        task.status = data["status"]
        task.completed_at = _utc_now() if task.status == "done" else None

    newly_assigned: set[UUID] = set()
    removed_assigned: set[UUID] = set()
    if assignee_ids is not None:
        users = _load_active_users(db, assignee_ids)
        existing = {assignment.user_id: assignment for assignment in task.assignments}
        wanted = set(users)
        for user_id, assignment in list(existing.items()):
            if user_id not in wanted:
                db.delete(assignment)
                removed_assigned.add(user_id)
        for user_id in wanted - set(existing):
            db.add(models.TaskAssignee(task_id=task.task_id, user_id=user_id, assigned_by=current_user.user_id))
            newly_assigned.add(user_id)

    if timing_changed or status_changed:
        _clear_deadline_notifications(db, task.task_id)
    elif removed_assigned:
        (
            db.query(models.TaskNotification)
            .filter(
                models.TaskNotification.task_id == task.task_id,
                models.TaskNotification.user_id.in_(removed_assigned),
                models.TaskNotification.kind.in_(_DEADLINE_NOTIFICATION_KINDS),
            )
            .delete(synchronize_session=False)
        )

    db.flush()
    _notify_new_assignees(db, task, newly_assigned, current_user)
    db.commit()
    task = _get_task_or_404(db, task.task_id)
    log_action(
        db,
        entity="task",
        entity_id=task.task_id,
        action="update",
        user=current_user,
        before=before,
        after=_task_payload(task),
    )
    return _task_payload(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_task_or_404(db, task_id)
    before = _task_payload(task)
    db.delete(task)
    db.commit()
    log_action(
        db,
        entity="task",
        entity_id=task_id,
        action="delete",
        user=current_user,
        before=before,
    )
    return None


@router.get("/notifications/list", response_model=list[schemas.TaskNotificationRead])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ensure_due_notifications(db, current_user)
    query = (
        db.query(models.TaskNotification)
        .options(joinedload(models.TaskNotification.task))
        .filter(models.TaskNotification.user_id == current_user.user_id)
    )
    if unread_only:
        query = query.filter(models.TaskNotification.read_at.is_(None))
    notifications = query.order_by(models.TaskNotification.created_at.desc()).limit(limit).all()
    return [
        {
            "notification_id": item.notification_id,
            "user_id": item.user_id,
            "task_id": item.task_id,
            "kind": item.kind,
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at,
            "read_at": item.read_at,
            "task_title": item.task.title if item.task else None,
            "task_due_at": item.task.due_at if item.task else None,
        }
        for item in notifications
    ]


@router.post("/notifications/{notification_id}/read", response_model=schemas.TaskNotificationRead)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = (
        db.query(models.TaskNotification)
        .options(joinedload(models.TaskNotification.task))
        .filter(
            models.TaskNotification.notification_id == notification_id,
            models.TaskNotification.user_id == current_user.user_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")
    item.read_at = _utc_now()
    db.commit()
    db.refresh(item)
    return {
        "notification_id": item.notification_id,
        "user_id": item.user_id,
        "task_id": item.task_id,
        "kind": item.kind,
        "title": item.title,
        "body": item.body,
        "created_at": item.created_at,
        "read_at": item.read_at,
        "task_title": item.task.title if item.task else None,
        "task_due_at": item.task.due_at if item.task else None,
    }


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    now = _utc_now()
    updated = (
        db.query(models.TaskNotification)
        .filter(
            models.TaskNotification.user_id == current_user.user_id,
            models.TaskNotification.read_at.is_(None),
        )
        .update({models.TaskNotification.read_at: now}, synchronize_session=False)
    )
    db.commit()
    return {"status": "ok", "updated": updated}
