from app.core.i18n import tr
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.plans import PlanCalendarRequest, PlanDayRead, PlanDayRegenerate, PlanDayUpdate, PlanShift, ReviewAnswer, ReviewRead, StudyPlanRead
from app.services import ai as ai_service
from app.services import plans as plan_service
from app.core.config import settings
from app.core.traffic import check_limit

router = APIRouter(tags=["plans"])


@router.get("/plans", response_model=list[StudyPlanRead])
def list_plans(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return plan_service.list_plans(db, user.user_uid)


@router.get("/plans/{plan_uid}", response_model=StudyPlanRead)
def get_plan(plan_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return plan_service.get_plan(db, plan_uid, user.user_uid)


@router.post("/plans/{plan_uid}/duplicate", response_model=StudyPlanRead)
def duplicate_plan(plan_uid: UUID, payload: PlanShift, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    source = plan_service.get_plan(db, plan_uid, user.user_uid)
    plan = models.StudyPlan(user_uid=user.user_uid, topic_uid=source.topic_uid,
                            title=tr('{0} — copy', source.title)[:160], overview=source.overview,
                            success_criteria=source.success_criteria, start_date=payload.start_date,
                            minutes_per_day=source.minutes_per_day)
    db.add(plan)
    db.flush()
    for day in source.days:
        db.add(models.StudyPlanDay(plan_uid=plan.plan_uid, day_number=day.day_number,
                                   scheduled_date=payload.start_date + (day.scheduled_date - source.start_date),
                                   scheduled_time=day.scheduled_time,
                                   title=day.title, objective=day.objective, activities=day.activities,
                                   duration_minutes=day.duration_minutes))
    db.commit()
    return plan_service.get_plan(db, plan.plan_uid, user.user_uid)


@router.patch("/plans/{plan_uid}/shift", response_model=StudyPlanRead)
def shift_plan(plan_uid: UUID, payload: PlanShift, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    plan = plan_service.get_plan(db, plan_uid, user.user_uid)
    delta = payload.start_date - plan.start_date
    plan.start_date = payload.start_date
    for day in plan.days:
        day.scheduled_date += delta
        plan_service.update_calendar_task(db, day, user)
    plan_service.sync_material(db, plan)
    db.commit()
    return plan_service.get_plan(db, plan_uid, user.user_uid)


@router.patch("/plans/{plan_uid}/days/{day_uid}", response_model=PlanDayRead)
def update_day(plan_uid: UUID, day_uid: UUID, payload: PlanDayUpdate,
               db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    plan = plan_service.get_plan(db, plan_uid, user.user_uid)
    day = next((item for item in plan.days if item.day_uid == day_uid), None)
    if day is None: raise HTTPException(status_code=404, detail=tr('Plan day not found.'))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(day, key, value)
    plan_service.update_calendar_task(db, day, user)
    plan_service.sync_material(db, plan)
    db.commit()
    db.refresh(day)
    return day


@router.post("/plans/{plan_uid}/days/{day_uid}/regenerate", response_model=PlanDayRead)
async def regenerate_day(plan_uid: UUID, day_uid: UUID, payload: PlanDayRegenerate,
                         db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    plan = plan_service.get_plan(db, plan_uid, user.user_uid)
    day = next((item for item in plan.days if item.day_uid == day_uid), None)
    if day is None: raise HTTPException(status_code=404, detail=tr('Plan day not found.'))
    check_limit("ai", str(user.user_uid), settings.ai_rate_limit_per_day, 86400)
    topic = db.get(models.Topic, plan.topic_uid)
    subject = db.get(models.Subject, topic.subject_uid)
    result = await ai_service.regenerate_plan_day(subject.name, topic.name, day.day_number,
                                                   plan.minutes_per_day, day.objective, payload.custom_goal,
                                                   "Polish" if user.language == "pl" else "English")
    day.title, day.objective, day.activities, day.duration_minutes = result.title, result.objective, result.activities, result.duration_minutes
    plan_service.update_calendar_task(db, day, user)
    plan_service.sync_material(db, plan)
    db.commit()
    db.refresh(day)
    return day


@router.post("/plans/{plan_uid}/calendar-tasks", response_model=StudyPlanRead)
def calendar_tasks(plan_uid: UUID, payload: PlanCalendarRequest,
                   db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    plan = plan_service.get_plan(db, plan_uid, user.user_uid)
    if not payload.create_tasks:
        for day in plan.days:
            if day.calendar_task_uid:
                task = db.get(models.Task, day.calendar_task_uid)
                if task: db.delete(task)
                day.calendar_task_uid = None
        db.commit()
        return plan_service.get_plan(db, plan_uid, user.user_uid)
    return plan_service.create_calendar_tasks(db, plan, user)


@router.delete("/plans/{plan_uid}", status_code=204)
def delete_plan(plan_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    plan = plan_service.get_plan(db, plan_uid, user.user_uid)
    for day in plan.days:
        if day.calendar_task_uid:
            task = db.get(models.Task, day.calendar_task_uid)
            if task: db.delete(task)
    db.delete(plan)
    db.commit()
    return Response(status_code=204)


@router.get("/reviews", response_model=list[ReviewRead])
def list_reviews(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return list(db.scalars(select(models.ReviewSchedule).where(models.ReviewSchedule.user_uid == user.user_uid)
                           .order_by(models.ReviewSchedule.due_at)))


@router.post("/reviews/{review_uid}/answer", response_model=ReviewRead)
def answer_review(review_uid: UUID, payload: ReviewAnswer, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    review = db.scalar(select(models.ReviewSchedule).where(models.ReviewSchedule.review_uid == review_uid,
                                                             models.ReviewSchedule.user_uid == user.user_uid))
    if review is None: raise HTTPException(status_code=404, detail=tr('Review not found.'))
    return plan_service.answer_review(db, review, user, payload.rating)
