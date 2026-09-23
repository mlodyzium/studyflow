from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AiConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    conversation_uid: UUID
    title: str
    user_message: str
    assistant_message: str
    proposal: dict[str, Any]
    created_at: datetime


class T3achRequest(BaseModel):
    message: str = Field(min_length=3, max_length=3000)
    language: str = Field(default="polski", min_length=2, max_length=30)


class T3achTaskProposal(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    deadline_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=1000)


class T3achProposal(BaseModel):
    reply: str = Field(min_length=1, max_length=12000)
    needs_clarification: bool = False
    question: str | None = Field(default=None, max_length=500)
    subject_name: str | None = Field(default=None, max_length=100)
    topic_name: str | None = Field(default=None, max_length=100)
    difficulty: str | None = Field(default=None, max_length=20)
    tasks: list[T3achTaskProposal] = Field(default_factory=list, max_length=10)
    intent: str = Field(default="organize", max_length=30)
    target_kind: str | None = Field(default=None, pattern="^(subject|topic|task)$")
    target_name: str | None = Field(default=None, max_length=160)
    new_name: str | None = Field(default=None, max_length=160)
    new_priority: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH)$")
    new_is_done: bool | None = None
    days: int = Field(default=7, ge=0, le=30)
    minutes_per_day: int = Field(default=45, ge=0, le=240)
    preview: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_optional_agent_fields(self):
        if self.days == 0:
            self.days = 7
        if self.minutes_per_day == 0:
            self.minutes_per_day = 45
        if self.intent not in {"organize", "study_plan", "notes", "edit"}:
            self.intent = "organize"
            self.needs_clarification = True
            self.tasks = []
            if not self.question:
                self.question = self.reply
        return self


class T3achExecuteResult(BaseModel):
    message: str
    subject_uid: UUID | None = None
    topic_uid: UUID | None = None
    task_uids: list[UUID]
    created_subject: bool
    created_topic: bool
