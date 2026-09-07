from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import asc, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.security import hash_password
from app.schemas.study import (
    ExamResultCreate, ExamResultUpdate, StudySessionCreate, StudySessionUpdate,
    SubjectCreate, SubjectUpdate, TaskCreate, TaskUpdate, TopicCreate,
    TopicUpdate, UserCreate, UserUpdate,
)
from app.services.pagination import paginate

T = TypeVar("T")


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{name} not found")


def _save(db: Session, value: T, conflict: str = "Database conflict") -> T:
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc
    db.refresh(value)
    return value


def _update(value: object, data: object) -> None:
    for field, field_value in data.model_dump(exclude_unset=True).items():
        setattr(value, field, field_value)


def _delete(db: Session, value: object) -> None:
    db.delete(value)
    db.commit()


def create_user(db: Session, data: UserCreate):
    values = data.model_dump(exclude={"password"})
    values["password_hash"] = hash_password(data.password)
    return _save(db, models.User(**values), "Username or email already exists")


def update_user(db: Session, user: models.User, data: UserUpdate):
    for field, value in data.model_dump(exclude_unset=True, exclude={"password"}).items():
        setattr(user, field, value)
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    return _save(db, user, "Username or email already exists")


def delete_user(db: Session, user: models.User):
    _delete(db, user)


def get_subject(db: Session, uid: UUID, user_uid: UUID):
    value = db.scalar(select(models.Subject).where(
        models.Subject.subject_uid == uid, models.Subject.user_uid == user_uid
    ))
    if value is None:
        raise _not_found("Subject")
    return value


def create_subject(db: Session, data: SubjectCreate, user_uid: UUID):
    return _save(db, models.Subject(**data.model_dump(), user_uid=user_uid))


def list_subjects(db: Session, user_uid: UUID, page: int, page_size: int, search: str | None):
    query = select(models.Subject).where(models.Subject.user_uid == user_uid)
    if search:
        query = query.where(models.Subject.name.ilike(f"%{search}%"))
    return paginate(db, query.order_by(models.Subject.name, models.Subject.subject_uid), page, page_size)


def update_subject(db: Session, uid: UUID, user_uid: UUID, data: SubjectUpdate):
    value = get_subject(db, uid, user_uid); _update(value, data); return _save(db, value)


def delete_subject(db: Session, uid: UUID, user_uid: UUID):
    _delete(db, get_subject(db, uid, user_uid))


def get_topic(db: Session, uid: UUID, user_uid: UUID):
    query = select(models.Topic).join(models.Subject).where(
        models.Topic.topic_uid == uid, models.Subject.user_uid == user_uid
    )
    value = db.scalar(query)
    if value is None:
        raise _not_found("Topic")
    return value


def create_topic(db: Session, data: TopicCreate, user_uid: UUID):
    get_subject(db, data.subject_uid, user_uid)
    return _save(db, models.Topic(**data.model_dump()))


def list_topics(db: Session, user_uid: UUID, subject_uid: UUID | None, page: int, page_size: int, difficulty: str | None, is_done: bool | None):
    query = select(models.Topic).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if subject_uid: query = query.where(models.Topic.subject_uid == subject_uid)
    if difficulty: query = query.where(models.Topic.difficulty == difficulty)
    if is_done is not None: query = query.where(models.Topic.is_done == is_done)
    return paginate(db, query.order_by(models.Topic.name, models.Topic.topic_uid), page, page_size)


def update_topic(db: Session, uid: UUID, user_uid: UUID, data: TopicUpdate):
    if data.subject_uid is not None: get_subject(db, data.subject_uid, user_uid)
    value = get_topic(db, uid, user_uid); _update(value, data); return _save(db, value)


def delete_topic(db: Session, uid: UUID, user_uid: UUID):
    _delete(db, get_topic(db, uid, user_uid))


def get_task(db: Session, uid: UUID, user_uid: UUID):
    query = select(models.Task).join(models.Topic).join(models.Subject).where(
        models.Task.task_uid == uid, models.Subject.user_uid == user_uid
    )
    value = db.scalar(query)
    if value is None: raise _not_found("Task")
    return value


def create_task(db: Session, data: TaskCreate, user_uid: UUID):
    get_topic(db, data.topic_uid, user_uid)
    return _save(db, models.Task(**data.model_dump()))


def list_tasks(db: Session, user_uid: UUID, topic_uid: UUID | None, page: int, page_size: int, priority: models.Priority | None, is_done: bool | None, search: str | None, sort: str, order: str):
    query = select(models.Task).join(models.Topic).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if topic_uid: query = query.where(models.Task.topic_uid == topic_uid)
    if priority: query = query.where(models.Task.priority == priority)
    if is_done is not None: query = query.where(models.Task.is_done == is_done)
    if search: query = query.where(models.Task.title.ilike(f"%{search}%"))
    column = {"title": models.Task.title, "deadline": models.Task.deadline, "priority": models.Task.priority}[sort]
    direction = desc if order == "desc" else asc
    return paginate(db, query.order_by(direction(column), models.Task.task_uid), page, page_size)


def update_task(db: Session, uid: UUID, user_uid: UUID, data: TaskUpdate):
    if data.topic_uid is not None: get_topic(db, data.topic_uid, user_uid)
    value = get_task(db, uid, user_uid); _update(value, data); return _save(db, value)


def delete_task(db: Session, uid: UUID, user_uid: UUID):
    _delete(db, get_task(db, uid, user_uid))


def get_study_session(db: Session, uid: UUID, user_uid: UUID):
    value = db.scalar(select(models.StudySession).join(models.Subject).where(
        models.StudySession.study_uid == uid, models.Subject.user_uid == user_uid
    ))
    if value is None: raise _not_found("StudySession")
    return value


def create_study_session(db: Session, data: StudySessionCreate, user_uid: UUID):
    get_subject(db, data.subject_uid, user_uid)
    return _save(db, models.StudySession(**data.model_dump(exclude_none=True)))


def list_study_sessions(db: Session, user_uid: UUID, subject_uid: UUID | None, page: int, page_size: int):
    query = select(models.StudySession).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if subject_uid: query = query.where(models.StudySession.subject_uid == subject_uid)
    return paginate(db, query.order_by(desc(models.StudySession.started_at), models.StudySession.study_uid), page, page_size)


def update_study_session(db: Session, uid: UUID, user_uid: UUID, data: StudySessionUpdate):
    if data.subject_uid is not None: get_subject(db, data.subject_uid, user_uid)
    value = get_study_session(db, uid, user_uid); _update(value, data); return _save(db, value)


def delete_study_session(db: Session, uid: UUID, user_uid: UUID):
    _delete(db, get_study_session(db, uid, user_uid))


def get_exam_result(db: Session, uid: UUID, user_uid: UUID):
    value = db.scalar(select(models.ExamResult).join(models.Subject).where(
        models.ExamResult.exam_uid == uid, models.Subject.user_uid == user_uid
    ))
    if value is None: raise _not_found("ExamResult")
    return value


def create_exam_result(db: Session, data: ExamResultCreate, user_uid: UUID):
    get_subject(db, data.subject_uid, user_uid)
    return _save(db, models.ExamResult(**data.model_dump()))


def list_exam_results(db: Session, user_uid: UUID, subject_uid: UUID | None, page: int, page_size: int):
    query = select(models.ExamResult).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if subject_uid: query = query.where(models.ExamResult.subject_uid == subject_uid)
    return paginate(db, query.order_by(desc(models.ExamResult.exam_date), models.ExamResult.exam_uid), page, page_size)


def update_exam_result(db: Session, uid: UUID, user_uid: UUID, data: ExamResultUpdate):
    if data.subject_uid is not None: get_subject(db, data.subject_uid, user_uid)
    value = get_exam_result(db, uid, user_uid); _update(value, data); return _save(db, value)


def delete_exam_result(db: Session, uid: UUID, user_uid: UUID):
    _delete(db, get_exam_result(db, uid, user_uid))
