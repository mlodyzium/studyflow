from app.core.i18n import tr
from typing import TypeVar
from uuid import UUID
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Date, asc, cast, desc, func, select
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
from app.services.names import normalize_name

T = TypeVar("T")


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(item.strip() for item in tags if item.strip()))
    if any(len(item) > 30 for item in cleaned):
        raise HTTPException(status_code=422, detail=tr('A tag can be at most 30 characters long.'))
    return cleaned


def _utc(value: datetime | None, user: models.User) -> datetime | None:
    if value is None: return None
    local = value.replace(tzinfo=ZoneInfo(user.timezone)) if value.tzinfo is None else value
    return local.astimezone(timezone.utc)


def _not_found(name: str) -> HTTPException:
    labels = {"Subject": tr('subject'), "Topic": tr('topic'), "Task": tr('task'),
              "StudySession": tr('study session'), "ExamResult": tr('exam result')}
    return HTTPException(status_code=404, detail=tr('{0} not found.', labels.get(name, tr('item'))))


def _save(db: Session, value: T, conflict: str | None = None) -> T:
    db.add(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict or tr('Data conflict. Refresh the page and try again.')) from exc
    db.refresh(value)
    return value


def _update(value: object, data: object) -> None:
    for field, field_value in data.model_dump(exclude_unset=True).items():
        setattr(value, field, field_value)


def _delete(db: Session, value: object) -> None:
    db.delete(value)
    db.commit()


def create_user(db: Session, data: UserCreate):
    values = data.model_dump(exclude={"password", "confirm_password"})
    values["password_hash"] = hash_password(data.password)
    return _save(db, models.User(**values), tr('Username or email address is already taken.'))


def _normalize_shortcut(value: str) -> str:
    if not value:
        return ""
    parts = value.split("+")
    key = parts.pop()
    modifiers = [part.lower() for part in parts]
    allowed = ("ctrl", "alt", "meta", "shift")
    if (len(key) != 1 or key.isspace() or len(modifiers) != len(set(modifiers))
            or any(part not in allowed for part in modifiers)
            or not any(part in modifiers for part in allowed[:3])):
        raise HTTPException(status_code=422, detail=tr('Invalid keyboard shortcut.'))
    return "+".join([*(part.title() for part in allowed if part in modifiers), key.upper()])


def update_user(db: Session, user: models.User, data: UserUpdate):
    task_shortcut = _normalize_shortcut(data.task_shortcut if data.task_shortcut is not None else user.task_shortcut)
    ai_shortcut = _normalize_shortcut(data.ai_shortcut if data.ai_shortcut is not None else user.ai_shortcut)
    if task_shortcut and task_shortcut == ai_shortcut:
        raise HTTPException(status_code=422, detail=tr('Task and AI Assistant shortcuts must be different.'))
    if data.task_shortcut is not None:
        data.task_shortcut = task_shortcut
    if data.ai_shortcut is not None:
        data.ai_shortcut = ai_shortcut
    for field, value in data.model_dump(exclude_unset=True, exclude={"password", "confirm_password"}).items():
        setattr(user, field, value)
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    return _save(db, user, tr('Username or email address is already taken.'))


def delete_user(db: Session, user: models.User):
    _delete(db, user)


def get_subject(db: Session, uid: UUID, user_uid: UUID):
    value = db.scalar(select(models.Subject).where(
        models.Subject.subject_uid == uid, models.Subject.user_uid == user_uid
    ))
    if value is None:
        raise _not_found("Subject")
    return value


def _subject_name_exists(db: Session, user_uid: UUID, name: str, exclude_uid: UUID | None = None) -> bool:
    query = select(models.Subject.subject_uid).where(
        models.Subject.user_uid == user_uid,
        func.lower(func.trim(models.Subject.name)) == name.strip().lower(),
    )
    if exclude_uid is not None:
        query = query.where(models.Subject.subject_uid != exclude_uid)
    return db.scalar(query.limit(1)) is not None


def create_subject(db: Session, data: SubjectCreate, user_uid: UUID):
    if not data.name.strip():
        raise HTTPException(status_code=422, detail=tr('Subject name cannot be empty.'))
    if _subject_name_exists(db, user_uid, data.name):
        raise HTTPException(status_code=409, detail=tr('A subject with this name already exists.'))
    values = data.model_dump()
    values["name"] = normalize_name(data.name)
    values["tags"] = _clean_tags(data.tags)
    return _save(db, models.Subject(**values, user_uid=user_uid), tr('A subject with this name already exists.'))


def list_subjects(db: Session, user_uid: UUID, page: int, page_size: int, search: str | None, archived: bool = False):
    query = select(models.Subject).where(models.Subject.user_uid == user_uid)
    query = query.where(models.Subject.archived_at.is_not(None) if archived else models.Subject.archived_at.is_(None))
    if search:
        query = query.where(models.Subject.name.ilike(f"%{search}%"))
    return paginate(db, query.order_by(models.Subject.name, models.Subject.subject_uid), page, page_size)


def update_subject(db: Session, uid: UUID, user_uid: UUID, data: SubjectUpdate):
    value = get_subject(db, uid, user_uid)
    if data.name is not None:
        if not data.name.strip():
            raise HTTPException(status_code=422, detail=tr('Subject name cannot be empty.'))
        if _subject_name_exists(db, user_uid, data.name, uid):
            raise HTTPException(status_code=409, detail=tr('A subject with this name already exists.'))
        data = data.model_copy(update={"name": normalize_name(data.name)})
    if data.tags is not None: data = data.model_copy(update={"tags": _clean_tags(data.tags)})
    values = data.model_dump(exclude_unset=True, exclude={"archived"})
    for field, field_value in values.items(): setattr(value, field, field_value)
    if data.archived is not None: value.archived_at = datetime.now(timezone.utc) if data.archived else None
    return _save(db, value, tr('A subject with this name already exists.'))


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
    name = normalize_name(data.name)
    if _topic_name_exists(db, data.subject_uid, name):
        raise HTTPException(status_code=409, detail=tr('A topic with this name already exists in this subject.'))
    return _save(db, models.Topic(**data.model_dump(exclude={"name"}), name=name), tr('A topic with this name already exists in this subject.'))


def _topic_name_exists(db: Session, subject_uid: UUID, name: str, exclude_uid: UUID | None = None) -> bool:
    query = select(models.Topic.topic_uid).where(
        models.Topic.subject_uid == subject_uid,
        func.lower(func.trim(models.Topic.name)) == name.strip().lower(),
    )
    if exclude_uid is not None:
        query = query.where(models.Topic.topic_uid != exclude_uid)
    return db.scalar(query.limit(1)) is not None


def list_topics(db: Session, user_uid: UUID, subject_uid: UUID | None, page: int, page_size: int, difficulty: str | None, is_done: bool | None):
    query = select(models.Topic).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if subject_uid: query = query.where(models.Topic.subject_uid == subject_uid)
    if difficulty: query = query.where(models.Topic.difficulty == difficulty)
    if is_done is not None: query = query.where(models.Topic.is_done == is_done)
    return paginate(db, query.order_by(models.Topic.name, models.Topic.topic_uid), page, page_size)


def update_topic(db: Session, uid: UUID, user_uid: UUID, data: TopicUpdate):
    value = get_topic(db, uid, user_uid)
    if data.subject_uid is not None: get_subject(db, data.subject_uid, user_uid)
    name = normalize_name(data.name) if data.name is not None else value.name
    subject_uid = data.subject_uid if data.subject_uid is not None else value.subject_uid
    if _topic_name_exists(db, subject_uid, name, uid):
        raise HTTPException(status_code=409, detail=tr('A topic with this name already exists in this subject.'))
    if data.name is not None: data = data.model_copy(update={"name": name})
    _update(value, data)
    return _save(db, value, tr('A topic with this name already exists in this subject.'))


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
    user = db.get(models.User, user_uid)
    values = data.model_dump()
    values["deadline"] = _utc(data.deadline, user)
    return _save(db, models.Task(**values))


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
    value = get_task(db, uid, user_uid)
    if "deadline" in data.model_fields_set: data = data.model_copy(update={"deadline": _utc(data.deadline, db.get(models.User, user_uid))})
    _update(value, data)
    day = db.scalar(select(models.StudyPlanDay).join(models.StudyPlan).where(
        models.StudyPlanDay.calendar_task_uid == uid, models.StudyPlan.user_uid == user_uid))
    if day is not None:
        from app.services import plans
        day.is_done = value.is_done
        if "deadline" in data.model_fields_set:
            if value.deadline:
                local = value.deadline.astimezone(ZoneInfo(db.get(models.User, user_uid).timezone))
                day.scheduled_date = local.date()
                day.scheduled_time = local.strftime("%H:%M")
            else:
                day.scheduled_time = None
        if "title" in data.model_fields_set:
            day.title = value.title
        if "topic_uid" in data.model_fields_set and value.topic_uid != day.plan.topic_uid:
            raise HTTPException(status_code=422, detail=tr('The task belongs to a plan. Change the topic of the entire plan instead of a single task.'))
        plans.sync_material(db, day.plan)
    return _save(db, value)


def bulk_complete_tasks(db: Session, task_uids: list[UUID], user_uid: UUID) -> int:
    unique_uids = set(task_uids)
    tasks = list(db.scalars(select(models.Task).join(models.Topic).join(models.Subject).where(
        models.Task.task_uid.in_(unique_uids), models.Subject.user_uid == user_uid)))
    if len(tasks) != len(unique_uids):
        raise HTTPException(status_code=404, detail=tr('All selected tasks were not found.'))
    linked_days = list(db.scalars(select(models.StudyPlanDay).join(models.StudyPlan).where(
        models.StudyPlanDay.calendar_task_uid.in_(unique_uids), models.StudyPlan.user_uid == user_uid)))
    for task in tasks:
        task.is_done = True
    for day in linked_days:
        day.is_done = True
    db.commit()
    return len(unique_uids)


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
    if data.topic_uid is not None:
        topic = get_topic(db, data.topic_uid, user_uid)
        if topic.subject_uid != data.subject_uid:
            raise HTTPException(status_code=422, detail=tr('The topic does not belong to the selected subject.'))
    if data.task_uid is not None:
        task = get_task(db, data.task_uid, user_uid)
        if data.topic_uid is None or task.topic_uid != data.topic_uid:
            raise HTTPException(status_code=422, detail=tr('The task does not belong to the selected topic.'))
    values = data.model_dump(exclude_none=True)
    if data.started_at: values["started_at"] = _utc(data.started_at, db.get(models.User, user_uid))
    return _save(db, models.StudySession(**values))


def list_study_sessions(db: Session, user_uid: UUID, subject_uid: UUID | None, page: int, page_size: int):
    query = select(models.StudySession).join(models.Subject).where(models.Subject.user_uid == user_uid)
    if subject_uid: query = query.where(models.StudySession.subject_uid == subject_uid)
    return paginate(db, query.order_by(desc(models.StudySession.started_at), models.StudySession.study_uid), page, page_size)


def study_session_summary(db: Session, user: models.User) -> dict[str, int]:
    zone = ZoneInfo(user.timezone)
    today = datetime.now(timezone.utc).astimezone(zone).date()
    week_start = today - timedelta(days=6)
    owned = models.StudySession.subject_uid.in_(select(models.Subject.subject_uid)
                                                 .where(models.Subject.user_uid == user.user_uid))
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        local_date = cast(func.timezone(user.timezone, models.StudySession.started_at), Date)
        rows = db.execute(select(local_date, func.sum(func.coalesce(models.StudySession.duration_minutes, 0)))
                          .where(owned).group_by(local_date)).all()
    else:
        raw_rows = db.execute(select(models.StudySession.started_at, models.StudySession.duration_minutes)
                              .where(owned)).all()
        rows = [((started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)).astimezone(zone).date(), minutes or 0)
                for started_at, minutes in raw_rows]
    days: set = set()
    today_minutes = week_minutes = 0
    for day, minutes in rows:
        days.add(day)
        if day == today:
            today_minutes += minutes or 0
        if week_start <= day <= today:
            week_minutes += minutes or 0
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return {"today_minutes": today_minutes, "week_minutes": week_minutes, "streak": streak}


def update_study_session(db: Session, uid: UUID, user_uid: UUID, data: StudySessionUpdate):
    value = get_study_session(db, uid, user_uid)
    subject_uid = data.subject_uid if data.subject_uid is not None else value.subject_uid
    topic_uid = data.topic_uid if "topic_uid" in data.model_fields_set else value.topic_uid
    task_uid = data.task_uid if "task_uid" in data.model_fields_set else value.task_uid
    get_subject(db, subject_uid, user_uid)
    if topic_uid is not None:
        topic = get_topic(db, topic_uid, user_uid)
        if topic.subject_uid != subject_uid:
            raise HTTPException(status_code=422, detail=tr('The topic does not belong to the selected subject.'))
    if task_uid is not None:
        task = get_task(db, task_uid, user_uid)
        if topic_uid is None or task.topic_uid != topic_uid:
            raise HTTPException(status_code=422, detail=tr('The task does not belong to the selected topic.'))
    if data.started_at: data = data.model_copy(update={"started_at": _utc(data.started_at, db.get(models.User, user_uid))})
    _update(value, data); return _save(db, value)


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
