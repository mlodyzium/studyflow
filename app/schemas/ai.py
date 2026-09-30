from app.core.i18n import tr
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NoteGenerationRequest(BaseModel):
    language: str = Field(default="English", min_length=2, max_length=30)
    detail_level: str = Field(default="standard", pattern="^(short|standard|detailed)$")
    task_uid: UUID | None = None
    custom_goal: str | None = Field(default=None, max_length=500)
    preview_only: bool = False


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
    language: str = Field(default="English", min_length=2, max_length=30)
    task_uid: UUID | None = None
    custom_goal: str | None = Field(default=None, max_length=500)
    days: int = Field(default=7, ge=1, le=30)
    minutes_per_day: int = Field(default=45, ge=10, le=240)
    local_date: date | None = None
    local_hour: int | None = Field(default=None, ge=0, le=23)
    sent_at: datetime | None = None
    preview_only: bool = False


class StudyPlanStep(BaseModel):
    day: int = Field(ge=1, le=30)
    scheduled_date: date | None = None
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
    start_date: date | None = None
    plan_uid: UUID | None = None


class MaterialApprovalRequest(BaseModel):
    notes: GeneratedNotes | None = None
    plan: GeneratedStudyPlan | None = None
    minutes_per_day: int = Field(default=45, ge=10, le=240)

    @model_validator(mode="after")
    def require_material(self):
        if self.notes is None and self.plan is None:
            raise ValueError(tr('Select a note or plan to save.'))
        return self


class ManualNoteRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    content: str = Field(min_length=10, max_length=12000)


class FallbackPlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=500)
    days: int = Field(default=7, ge=1, le=30)
    minutes_per_day: int = Field(default=45, ge=10, le=240)
    sent_at: datetime | None = None


class SessionNoteGenerationRequest(BaseModel):
    description: str = Field(min_length=3, max_length=1000)
    language: str = Field(default="English", min_length=2, max_length=30)


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


class AiHistoryBulkDelete(BaseModel):
    kind: Literal["materials", "chats"]
    ids: list[UUID] = Field(min_length=1, max_length=1000)


class T3achHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class T3achPreviousTask(BaseModel):
    title: str = Field(max_length=160)
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    deadline_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=200)


class T3achPreviousProposal(BaseModel):
    session_date: date | None = None
    session_completed: bool = False
    original_request: str | None = Field(default=None, max_length=3000)
    previous_answer: str | None = Field(default=None, max_length=4000)
    previous_material: str | None = None
    plan_start_date: date | None = None
    intent: str = Field(max_length=30)
    subject_name: str | None = Field(default=None, max_length=100)
    topic_name: str | None = Field(default=None, max_length=100)
    target_name: str | None = Field(default=None, max_length=160)
    target_kind: Literal["subject", "topic", "task"] | None = None
    difficulty: str | None = Field(default=None, max_length=20)
    new_name: str | None = Field(default=None, max_length=160)
    new_priority: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    new_is_done: bool | None = None
    material_types: list[Literal["notes", "plan"]] = Field(default_factory=list, max_length=2)
    days: int | None = Field(default=None, ge=1, le=30)
    minutes_per_day: int | None = Field(default=None, ge=10, le=240)
    excluded_weekdays: list[int] = Field(default_factory=list, max_length=7)
    exam_date: date | None = None
    requested_plan_days: int | None = Field(default=None, ge=1, le=30)
    plan_total_minutes: int | None = Field(default=None, ge=10, le=7200)
    session_title: str | None = Field(default=None, max_length=160)
    session_duration_minutes: int | None = Field(default=None, ge=1, le=240)
    session_notes: str | None = Field(default=None, max_length=500)
    tasks: list[T3achPreviousTask] = Field(default_factory=list, max_length=10)


class T3achRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    language: str = Field(default="English", min_length=2, max_length=30)
    history: list[T3achHistoryTurn] = Field(default_factory=list, max_length=30)
    previous_proposal_uid: UUID | None = None
    local_date: date | None = None
    local_hour: int | None = Field(default=None, ge=0, le=23)
    sent_at: datetime | None = None


class T3achExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_uid: UUID


class T3achSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


class MaterialDraftRequest(BaseModel):
    subject_uid: UUID
    topic_name: str = Field(min_length=1, max_length=100)
    mode: Literal["notes", "plan"]
    detail_level: Literal["short", "standard", "detailed"] = "standard"
    custom_goal: str | None = Field(default=None, max_length=500)
    task_uid: UUID | None = None
    days: int = Field(default=7, ge=1, le=30)
    minutes_per_day: int = Field(default=45, ge=10, le=240)
    sent_at: datetime | None = None
    fallback: bool = False
    manual_content: str | None = Field(default=None, min_length=10, max_length=12000)

    @field_validator("topic_name")
    @classmethod
    def strip_topic(cls, value):
        if not value.strip(): raise ValueError(tr('Enter the topic name.'))
        return value.strip()


class T3achTaskProposal(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    deadline_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value):
        if isinstance(value, str):
            return {"niski": "LOW", "średni": "MEDIUM", "sredni": "MEDIUM", "wysoki": "HIGH"}.get(value.strip().casefold(), value.strip().upper())
        return value


class T3achProposal(BaseModel):
    revision_changes_content: bool = False
    session_date: date | None = None
    session_completed: bool = False
    proposal_uid: UUID | None = None
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
    excluded_weekdays: list[int] = Field(default_factory=list, max_length=7)
    exam_date: date | None = None
    requested_plan_days: int | None = Field(default=None, ge=1, le=30)
    plan_total_minutes: int | None = Field(default=None, ge=10, le=7200)
    session_title: str | None = Field(default=None, max_length=160)
    session_notes: str | None = Field(default=None, max_length=3000)
    session_duration_minutes: int | None = Field(default=None, ge=1, le=240)
    preview: dict[str, Any] | None = None
    material_types: list[Literal["notes", "plan"]] = Field(default_factory=list, max_length=2)
    plan_start_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def discard_unrelated_edit_fields(cls, value):
        if isinstance(value, dict) and value.get("intent") != "edit":
            value = {**value, "target_kind": None, "new_priority": None}
        return value

    @field_validator("target_kind", mode="before")
    @classmethod
    def normalize_target_kind(cls, value):
        if isinstance(value, str):
            return {"przedmiot": "subject", "temat": "topic", "zadanie": "task"}.get(value.strip().casefold(), value.strip().casefold())
        return value

    @field_validator("new_priority", mode="before")
    @classmethod
    def normalize_new_priority(cls, value):
        if isinstance(value, str):
            return {"niski": "LOW", "średni": "MEDIUM", "sredni": "MEDIUM", "wysoki": "HIGH"}.get(value.strip().casefold(), value.strip().upper())
        return value

    @field_validator("excluded_weekdays")
    @classmethod
    def validate_excluded_weekdays(cls, value):
        if any(day < 0 or day > 6 for day in value):
            raise ValueError(tr('Days of the week must have values from 0 to 6.'))
        return sorted(set(value))

    @model_validator(mode="after")
    def normalize_optional_agent_fields(self):
        if self.intent == "notes_plan":
            self.intent = "notes"
            self.material_types = ["notes", "plan"]
        if self.intent == "notes" and "notes" not in self.material_types:
            self.material_types.insert(0, "notes")
        if self.intent == "study_plan" and "plan" not in self.material_types:
            self.material_types.insert(0, "plan")
        self.material_types = list(dict.fromkeys(self.material_types))
        if self.days == 0:
            self.days = 7
        if self.minutes_per_day == 0:
            self.minutes_per_day = 45
        if self.intent == "other":
            self.intent = "off_topic"
        if self.intent == "off_topic":
            self.needs_clarification = True
            self.reply = tr('I help with studying and organizing your studies. Please tell me what you want to learn or what I should plan.')
            self.question = self.reply
            self.subject_name = self.topic_name = None
            self.tasks = []
        elif self.intent == "study_help":
            self.needs_clarification = True
            self.question = self.reply
            self.tasks = []
        elif self.intent not in {"organize", "study_plan", "notes", "edit", "session"}:
            self.intent = "organize"
            self.needs_clarification = True
            self.tasks = []
            if not self.question:
                self.question = self.reply
        if self.needs_clarification:
            self.tasks = []
            self.preview = None
        return self


class T3achExecuteResult(BaseModel):
    message: str
    subject_uid: UUID | None = None
    topic_uid: UUID | None = None
    task_uids: list[UUID]
    plan_uids: list[UUID] = Field(default_factory=list)
    created_subject: bool
    created_topic: bool
