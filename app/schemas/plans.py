from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanDayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    day_uid: UUID
    day_number: int
    scheduled_date: date
    scheduled_time: str | None
    title: str
    objective: str
    activities: list[str]
    duration_minutes: int
    is_done: bool
    calendar_task_uid: UUID | None


class StudyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plan_uid: UUID
    topic_uid: UUID
    material_uid: UUID | None
    title: str
    overview: str
    success_criteria: list[str]
    start_date: date
    minutes_per_day: int
    created_at: datetime
    days: list[PlanDayRead]


class PlanDayUpdate(BaseModel):
    is_done: bool | None = None
    scheduled_date: date | None = None
    scheduled_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int | None = Field(default=None, ge=10, le=240)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    objective: str | None = Field(default=None, min_length=1, max_length=1000)
    activities: list[str] | None = Field(default=None, min_length=1, max_length=8)


class PlanShift(BaseModel):
    start_date: date


class PlanCalendarRequest(BaseModel):
    create_tasks: bool = True


class PlanDayRegenerate(BaseModel):
    custom_goal: str | None = Field(default=None, max_length=500)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    review_uid: UUID
    material_uid: UUID
    topic_uid: UUID
    due_at: datetime
    interval_days: int
    streak: int
    last_reviewed_at: datetime | None


class ReviewAnswer(BaseModel):
    rating: Literal["forgot", "hard", "easy"]
