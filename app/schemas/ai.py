from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteGenerationRequest(BaseModel):
    language: str = Field(default="polski", min_length=2, max_length=30)
    detail_level: str = Field(default="standard", pattern="^(short|standard|detailed)$")
    task_uid: UUID | None = None
    custom_goal: str | None = Field(default=None, max_length=500)


class NoteSection(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)


class GeneratedNotes(BaseModel):
    task_title: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1200)
    sections: list[NoteSection] = Field(min_length=1, max_length=8)
    key_points: list[str] = Field(min_length=1, max_length=10)
    review_questions: list[str] = Field(default_factory=list, max_length=6)


class PlanGenerationRequest(BaseModel):
    language: str = Field(default="polski", min_length=2, max_length=30)
    task_uid: UUID | None = None
    custom_goal: str | None = Field(default=None, max_length=500)
    days: int = Field(default=7, ge=1, le=30)
    minutes_per_day: int = Field(default=45, ge=10, le=240)


class StudyPlanStep(BaseModel):
    day: int = Field(ge=1, le=30)
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=1000)
    activities: list[str] = Field(min_length=1, max_length=8)
    duration_minutes: int = Field(ge=5, le=300)


class GeneratedStudyPlan(BaseModel):
    task_title: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    overview: str = Field(min_length=1, max_length=1200)
    steps: list[StudyPlanStep] = Field(min_length=1, max_length=30)
    success_criteria: list[str] = Field(min_length=1, max_length=8)


class SessionNoteGenerationRequest(BaseModel):
    description: str = Field(min_length=3, max_length=1000)
    language: str = Field(default="polski", min_length=2, max_length=30)


class GeneratedSessionNote(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    notes: str = Field(min_length=1, max_length=3000)


class AiMaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    material_uid: UUID
    topic_uid: UUID
    task_uid: UUID | None
    material_type: str
    title: str
    content: dict[str, Any]
    created_at: datetime
