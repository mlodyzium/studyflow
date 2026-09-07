from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.study import TaskCreate, TaskRead, TaskUpdate
from app.services import study

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", response_model=TaskRead, status_code=201)
def create(payload: TaskCreate, db: Session = Depends(get_db)):
    return study.create_task(db, payload)

@router.get("", response_model=list[TaskRead])
def list_all(topic_uid: UUID | None = None, db: Session = Depends(get_db)):
    return study.list_tasks(db, topic_uid)

@router.get("/{task_uid}", response_model=TaskRead)
def get_one(task_uid: UUID, db: Session = Depends(get_db)):
    return study.get_task(db, task_uid)

@router.patch("/{task_uid}", response_model=TaskRead)
def update(task_uid: UUID, payload: TaskUpdate, db: Session = Depends(get_db)):
    return study.update_task(db, task_uid, payload)

@router.delete("/{task_uid}", status_code=204)
def delete(task_uid: UUID, db: Session = Depends(get_db)):
    study.delete_task(db, task_uid)
    return Response(status_code=204)
