from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.pagination import Page
from app.schemas.study import TaskCreate, TaskRead, TaskUpdate
from app.services import study

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", response_model=TaskRead, status_code=201)
def create(payload: TaskCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.create_task(db, payload, user.user_uid)

@router.get("", response_model=Page[TaskRead])
def list_all(topic_uid: UUID | None = None, priority: models.Priority | None = None, is_done: bool | None = None, search: str | None = None, sort: Literal["title", "deadline", "priority"] = "deadline", order: Literal["asc", "desc"] = "asc", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.list_tasks(db, user.user_uid, topic_uid, page, page_size, priority, is_done, search, sort, order)

@router.get("/{uid}", response_model=TaskRead)
def get_one(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.get_task(db, uid, user.user_uid)

@router.patch("/{uid}", response_model=TaskRead)
def update(uid: UUID, payload: TaskUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return study.update_task(db, uid, user.user_uid, payload)

@router.delete("/{uid}", status_code=204)
def delete(uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    study.delete_task(db, uid, user.user_uid); return Response(status_code=204)
