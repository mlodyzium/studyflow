from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.security import hash_password
from app.schemas.study import (
    SubjectCreate, SubjectUpdate, TaskCreate, TaskUpdate,
    TopicCreate, TopicUpdate, UserCreate, UserUpdate,
)

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], uid: UUID) -> T:
    value = db.get(model, uid)
    if value is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return value


def _save(db: Session, value: T, conflict_detail: str | None = None) -> T:
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail or "Database conflict") from exc
    db.refresh(value)
    return value


def _apply_update(value: object, data: object) -> None:
    for field, field_value in data.model_dump(exclude_unset=True).items():
        setattr(value, field, field_value)


def _delete(db: Session, value: object) -> None:
    db.delete(value)
    db.commit()


def create_user(db: Session, data: UserCreate):
    user_data = data.model_dump(exclude={"password"})
    user_data["password_hash"] = hash_password(data.password)
    return _save(db, models.User(**user_data), "Username or email already exists")


def list_users(db: Session):
    return list(db.scalars(select(models.User).order_by(models.User.username)))


def get_user(db: Session, user_uid: UUID):
    return get_or_404(db, models.User, user_uid)


def update_user(db: Session, user_uid: UUID, data: UserUpdate):
    value = get_user(db, user_uid)
    update_data = data.model_dump(exclude_unset=True, exclude={"password"})
    for field, field_value in update_data.items():
        setattr(value, field, field_value)
    if data.password is not None:
        value.password_hash = hash_password(data.password)
    return _save(db, value, "Username or email already exists")


def delete_user(db: Session, user_uid: UUID):
    _delete(db, get_user(db, user_uid))


def create_subject(db: Session, data: SubjectCreate):
    get_user(db, data.user_uid)
    return _save(db, models.Subject(**data.model_dump()))


def list_subjects(db: Session, user_uid: UUID | None):
    query = select(models.Subject).order_by(models.Subject.name)
    if user_uid is not None:
        query = query.where(models.Subject.user_uid == user_uid)
    return list(db.scalars(query))


def get_subject(db: Session, subject_uid: UUID):
    return get_or_404(db, models.Subject, subject_uid)


def update_subject(db: Session, subject_uid: UUID, data: SubjectUpdate):
    if data.user_uid is not None:
        get_user(db, data.user_uid)
    value = get_subject(db, subject_uid)
    _apply_update(value, data)
    return _save(db, value)


def delete_subject(db: Session, subject_uid: UUID):
    _delete(db, get_subject(db, subject_uid))


def create_topic(db: Session, data: TopicCreate):
    get_subject(db, data.subject_uid)
    return _save(db, models.Topic(**data.model_dump()))


def list_topics(db: Session, subject_uid: UUID | None):
    query = select(models.Topic).order_by(models.Topic.name)
    if subject_uid is not None:
        query = query.where(models.Topic.subject_uid == subject_uid)
    return list(db.scalars(query))


def get_topic(db: Session, topic_uid: UUID):
    return get_or_404(db, models.Topic, topic_uid)


def update_topic(db: Session, topic_uid: UUID, data: TopicUpdate):
    if data.subject_uid is not None:
        get_subject(db, data.subject_uid)
    value = get_topic(db, topic_uid)
    _apply_update(value, data)
    return _save(db, value)


def delete_topic(db: Session, topic_uid: UUID):
    _delete(db, get_topic(db, topic_uid))


def create_task(db: Session, data: TaskCreate):
    get_topic(db, data.topic_uid)
    return _save(db, models.Task(**data.model_dump()))


def list_tasks(db: Session, topic_uid: UUID | None):
    query = select(models.Task).order_by(models.Task.deadline, models.Task.title)
    if topic_uid is not None:
        query = query.where(models.Task.topic_uid == topic_uid)
    return list(db.scalars(query))


def get_task(db: Session, task_uid: UUID):
    return get_or_404(db, models.Task, task_uid)


def update_task(db: Session, task_uid: UUID, data: TaskUpdate):
    if data.topic_uid is not None:
        get_topic(db, data.topic_uid)
    value = get_task(db, task_uid)
    _apply_update(value, data)
    return _save(db, value)


def delete_task(db: Session, task_uid: UUID):
    _delete(db, get_task(db, task_uid))
