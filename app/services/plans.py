from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.schemas.ai import GeneratedStudyPlan


def study_instant(day: date, user: models.User, study_time: str | None = None) -> datetime:
    hour, minute = map(int, (study_time or "00:00").split(":"))
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(user.timezone))
    return local.astimezone(timezone.utc)


def start_date_for(user: models.User, sent_at: datetime | None, minutes: int) -> date:
    now = datetime.now(timezone.utc)
    if sent_at is not None:
        if sent_at.tzinfo is None or abs((now - sent_at.astimezone(timezone.utc)).total_seconds()) > 600:
            raise HTTPException(status_code=422, detail="Czas wysłania prośby jest nieprawidłowy.")
        now = sent_at.astimezone(timezone.utc)
    local = now.astimezone(ZoneInfo(user.timezone))
    today = local.date()
    end_of_day = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=ZoneInfo(user.timezone)).astimezone(timezone.utc)
    return today if now + timedelta(minutes=minutes) <= end_of_day else today + timedelta(days=1)


def create_plan(db: Session, user: models.User, topic_uid: UUID, material_uid: UUID | None,
                result: GeneratedStudyPlan, minutes_per_day: int) -> models.StudyPlan:
    start = result.start_date or start_date_for(user, None, minutes_per_day)
    plan = models.StudyPlan(user_uid=user.user_uid, topic_uid=topic_uid, material_uid=material_uid,
                            title=result.title, overview=result.overview,
                            success_criteria=result.success_criteria, start_date=start,
                            minutes_per_day=minutes_per_day)
    db.add(plan)
    db.flush()
    used = set()
    for step in result.steps:
        if step.day in used:
            raise HTTPException(status_code=422, detail="Plan zawiera powtórzony numer dnia.")
        used.add(step.day)
        db.add(models.StudyPlanDay(plan_uid=plan.plan_uid, day_number=step.day,
                                   scheduled_date=start + timedelta(days=step.day - 1),
                                   title=step.title, objective=step.objective,
                                   activities=step.activities, duration_minutes=step.duration_minutes))
    db.flush()
    return get_plan(db, plan.plan_uid, user.user_uid)


def get_plan(db: Session, plan_uid: UUID, user_uid: UUID) -> models.StudyPlan:
    plan = db.scalar(select(models.StudyPlan).options(selectinload(models.StudyPlan.days)).where(
        models.StudyPlan.plan_uid == plan_uid, models.StudyPlan.user_uid == user_uid))
    if plan is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono planu.")
    return plan


def list_plans(db: Session, user_uid: UUID) -> list[models.StudyPlan]:
    return list(db.scalars(select(models.StudyPlan).options(selectinload(models.StudyPlan.days)).where(
        models.StudyPlan.user_uid == user_uid).order_by(models.StudyPlan.created_at.desc())))


def sync_material(db: Session, plan: models.StudyPlan) -> None:
    if not plan.material_uid:
        return
    material = db.get(models.AiMaterial, plan.material_uid)
    if material is None:
        return
    material.content = {**material.content, "start_date": plan.start_date.isoformat(), "steps": [
        {"day": day.day_number, "title": day.title, "objective": day.objective,
         "activities": day.activities, "duration_minutes": day.duration_minutes,
         "scheduled_date": day.scheduled_date.isoformat(), "scheduled_time": day.scheduled_time}
        for day in plan.days]}


def update_calendar_task(db: Session, day: models.StudyPlanDay, user: models.User) -> None:
    if not day.calendar_task_uid:
        return
    task = db.get(models.Task, day.calendar_task_uid)
    if task is None:
        day.calendar_task_uid = None
        return
    task.title = f"Dzień {day.day_number}: {day.title}"[:160]
    task.deadline = study_instant(day.scheduled_date, user, day.scheduled_time) if day.scheduled_time else None
    task.is_done = day.is_done
    task.notes = f"Cel: {day.objective}\nCzas: {day.duration_minutes} min\n" + "\n".join(f"• {item}" for item in day.activities)


def create_calendar_tasks(db: Session, plan: models.StudyPlan, user: models.User) -> models.StudyPlan:
    for day in plan.days:
        if not day.calendar_task_uid:
            task = models.Task(topic_uid=plan.topic_uid, title="", priority=models.Priority.MEDIUM)
            db.add(task)
            db.flush()
            day.calendar_task_uid = task.task_uid
        update_calendar_task(db, day, user)
    db.commit()
    return get_plan(db, plan.plan_uid, user.user_uid)


def create_review(db: Session, user: models.User, material: models.AiMaterial) -> models.ReviewSchedule:
    local_day = datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone)).date()
    review = models.ReviewSchedule(user_uid=user.user_uid, material_uid=material.material_uid,
                                   topic_uid=material.topic_uid, due_at=study_instant(local_day + timedelta(days=1), user),
                                   interval_days=1, streak=0)
    db.add(review)
    return review


def answer_review(db: Session, review: models.ReviewSchedule, user: models.User, rating: str) -> models.ReviewSchedule:
    now = datetime.now(timezone.utc)
    if rating == "forgot":
        review.streak = 0
        review.interval_days = 1
    elif rating == "hard":
        review.streak += 1
        review.interval_days = max(1, round(review.interval_days * 1.5))
    else:
        review.streak += 1
        review.interval_days = min(90, [1, 3, 7, 14, 30][min(review.streak - 1, 4)] if review.streak <= 5 else round(review.interval_days * 1.8))
    review.last_reviewed_at = now
    local_day = now.astimezone(ZoneInfo(user.timezone)).date()
    review.due_at = study_instant(local_day + timedelta(days=review.interval_days), user)
    db.commit()
    db.refresh(review)
    return review
