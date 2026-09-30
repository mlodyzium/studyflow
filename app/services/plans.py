from app.core.i18n import tr
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.schemas.ai import GeneratedStudyPlan


@dataclass(frozen=True)
class PlanSchedule:
    start_date: date
    requested_days: int
    days: int
    total_minutes: int
    dates: tuple[date, ...]
    exam_date: date | None = None
    exam_review: bool = False
    adjustment: str | None = None


def build_schedule(start_date: date, days: int, minutes_per_day: int, exam_date: date | None = None,
                   excluded_weekdays: set[int] | None = None) -> PlanSchedule:
    total = days * minutes_per_day
    excluded = excluded_weekdays or set()
    if any(day < 0 or day > 6 for day in excluded):
        raise HTTPException(status_code=422, detail=tr('Invalid day of the week in plan constraints.'))
    if exam_date is not None and exam_date < start_date:
        raise HTTPException(status_code=422, detail=tr('The exam deadline falls before the start of the plan. Change the exam deadline or study start date.'))
    horizon_end = min(start_date + timedelta(days=days - 1), exam_date) if exam_date and exam_date >= start_date else start_date + timedelta(days=days - 1)
    calendar_days = (horizon_end - start_date).days + 1
    available = tuple(start_date + timedelta(days=offset) for offset in range(calendar_days)
                      if (start_date + timedelta(days=offset)).weekday() not in excluded)
    if not available:
        raise HTTPException(status_code=422, detail=tr('There are no available study days in the selected period. Change days off or the plan range.'))
    exam_review = exam_date in available and exam_date == horizon_end
    study_days = len(available) - int(exam_review)
    if total > study_days * 240 + (15 if exam_review else 0):
        raise HTTPException(status_code=422, detail=tr('Cannot fit {0} minutes of studying into {1} available days. Change the range, deadline, or days off.', total, study_days))
    adjustment = None
    if len(available) < days:
        skipped = sorted({(start_date + timedelta(days=offset)).weekday() for offset in range(calendar_days)
                          if (start_date + timedelta(days=offset)).weekday() in excluded})
        weekday_names = (tr('Monday'), tr('Tuesday'), tr('Wednesday'), tr('Thursday'), tr('Friday'), tr('Saturday'), tr('Sunday'))
        excluded_note = tr('Skipping {0}. ', ', '.join(weekday_names[day] for day in skipped)) if skipped else ""
        review_note = tr(' and a short review on exam day') if exam_review else ''
        adjustment = tr('{0}Keeping the total goal of {1} minutes and distributing material across {2} study days{3}; available days will be proportionally longer.', excluded_note, total, study_days, review_note)
    return PlanSchedule(start_date, days, len(available), total, available, exam_date, exam_review, adjustment)


def apply_schedule(result: GeneratedStudyPlan, schedule: PlanSchedule) -> GeneratedStudyPlan:
    if len(result.steps) != schedule.days or {step.day for step in result.steps} != set(range(1, schedule.days + 1)):
        raise HTTPException(status_code=502, detail=tr('AI returned {0} days instead of the required {1}. The plan was not saved. Please try again.', len(result.steps), schedule.days))
    result.steps.sort(key=lambda step: step.day)
    review_minutes = min(15, schedule.total_minutes) if schedule.exam_review else 0
    study_steps = result.steps[:-1] if schedule.exam_review else result.steps
    remaining = schedule.total_minutes - review_minutes
    weights = [max(1, step.duration_minutes) for step in study_steps]
    durations = [max(5, min(240, round(remaining * weight / sum(weights)))) for weight in weights] if weights else []
    difference = remaining - sum(durations)
    cursor = 0
    while difference:
        change = 1 if difference > 0 else -1
        eligible = [index for index, value in enumerate(durations) if 5 <= value + change <= 240]
        if not eligible:
            raise HTTPException(status_code=422, detail=tr('Cannot distribute study time across available days.'))
        index = eligible[cursor % len(eligible)]
        durations[index] += change
        difference -= change
        cursor += 1
    for step, duration in zip(study_steps, durations):
        step.duration_minutes = duration
    for step, scheduled_date in zip(result.steps, schedule.dates):
        step.scheduled_date = scheduled_date
    if schedule.exam_review:
        review = result.steps[-1]
        review.title = tr('Short review before the exam')
        review.objective = tr('Recall key concepts and allow time for rest before the exam.')
        review.activities = [tr('Review your own summary and key formulas or definitions.'), tr('Check 2–3 control questions; do not learn new topics.')]
        review.duration_minutes = review_minutes
    if schedule.adjustment and not result.overview.startswith(schedule.adjustment):
        result.overview = f"{schedule.adjustment} {result.overview}"[:1200]
    result.start_date = schedule.dates[0]
    return result


def carry_over_excluded_activities(result: GeneratedStudyPlan, previous_preview: dict,
                                   schedule: PlanSchedule, excluded_weekdays: set[int]) -> None:
    if not excluded_weekdays:
        return
    previous_data = previous_preview.get("plan", previous_preview)
    if not isinstance(previous_data, dict) or "steps" not in previous_data:
        return
    try:
        previous = GeneratedStudyPlan.model_validate(previous_data)
    except ValueError:
        return
    study_count = schedule.days - int(schedule.exam_review)
    targets = {step.day: step for step in result.steps if step.day <= study_count}
    if not targets:
        return
    known_activities = {activity.strip().casefold() for step in targets.values() for activity in step.activities}
    for old_step in previous.steps:
        old_date = old_step.scheduled_date or (previous.start_date + timedelta(days=old_step.day - 1) if previous.start_date else None)
        if old_date is None or old_date.weekday() not in excluded_weekdays or old_date in schedule.dates:
            continue
        index = min(range(study_count), key=lambda item: abs((schedule.dates[item] - old_date).days))
        target = targets.get(index + 1)
        if target is None:
            continue
        if old_step.objective and old_step.objective.casefold() not in target.objective.casefold():
            target.objective = tr('{0} Catching up: {1}', target.objective, old_step.objective)[:1000]
        for activity in old_step.activities:
            key = activity.strip().casefold()
            if not key or key in known_activities:
                continue
            if len(target.activities) < 8:
                target.activities.append(activity)
            else:
                target.activities[-1] = f"{target.activities[-1]}; {activity}"
            known_activities.add(key)


def study_instant(day: date, user: models.User, study_time: str | None = None) -> datetime:
    hour, minute = map(int, (study_time or "00:00").split(":"))
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(user.timezone))
    return local.astimezone(timezone.utc)


def start_date_for(user: models.User, sent_at: datetime | None, minutes: int) -> date:
    now = datetime.now(timezone.utc)
    if sent_at is not None:
        if sent_at.tzinfo is None or abs((now - sent_at.astimezone(timezone.utc)).total_seconds()) > 600:
            raise HTTPException(status_code=422, detail=tr('The request send time is invalid.'))
        now = sent_at.astimezone(timezone.utc)
    local = now.astimezone(ZoneInfo(user.timezone))
    today = local.date()
    end_of_day = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=ZoneInfo(user.timezone)).astimezone(timezone.utc)
    return today if now + timedelta(minutes=minutes) <= end_of_day else today + timedelta(days=1)


def create_plan(db: Session, user: models.User, topic_uid: UUID, material_uid: UUID | None,
                result: GeneratedStudyPlan, minutes_per_day: int) -> models.StudyPlan:
    start = result.start_date or min((step.scheduled_date for step in result.steps if step.scheduled_date), default=None) or start_date_for(user, None, minutes_per_day)
    plan = models.StudyPlan(user_uid=user.user_uid, topic_uid=topic_uid, material_uid=material_uid,
                            title=result.title, overview=result.overview,
                            success_criteria=result.success_criteria, start_date=start,
                            minutes_per_day=minutes_per_day)
    db.add(plan)
    db.flush()
    used = set()
    for step in result.steps:
        if step.day in used:
            raise HTTPException(status_code=422, detail=tr('The plan contains a repeated day number.'))
        used.add(step.day)
        db.add(models.StudyPlanDay(plan_uid=plan.plan_uid, day_number=step.day,
                                   scheduled_date=step.scheduled_date or start + timedelta(days=step.day - 1),
                                   title=step.title, objective=step.objective,
                                   activities=step.activities, duration_minutes=step.duration_minutes))
    db.flush()
    return get_plan(db, plan.plan_uid, user.user_uid)


def get_plan(db: Session, plan_uid: UUID, user_uid: UUID) -> models.StudyPlan:
    plan = db.scalar(select(models.StudyPlan).options(selectinload(models.StudyPlan.days)).where(
        models.StudyPlan.plan_uid == plan_uid, models.StudyPlan.user_uid == user_uid))
    if plan is None:
        raise HTTPException(status_code=404, detail=tr('Plan not found.'))
    return plan


def list_plans(db: Session, user_uid: UUID) -> list[models.StudyPlan]:
    return list(db.scalars(select(models.StudyPlan).options(selectinload(models.StudyPlan.days)).where(
        models.StudyPlan.user_uid == user_uid).order_by(models.StudyPlan.created_at.desc())))


def sync_material(db: Session, plan: models.StudyPlan) -> None:
    if plan.days:
        plan.start_date = min(day.scheduled_date for day in plan.days)
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
    task.title = tr('Day {0}: {1}', day.day_number, day.title)[:160]
    task.deadline = study_instant(day.scheduled_date, user, day.scheduled_time) if day.scheduled_time else None
    task.is_done = day.is_done
    task.notes = tr('Goal: {0}\nTime: {1} min\n', day.objective, day.duration_minutes) + "\n".join(f"• {item}" for item in day.activities)


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
