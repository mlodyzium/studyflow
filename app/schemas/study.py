from app.core.i18n import tr
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models import Priority

class PatchModel(BaseModel):
    @model_validator(mode="after")
    def reject_null_required_fields(self):
        nullable = {
            "UserUpdate": {"email", "password", "confirm_password"},
            "SubjectUpdate": {"exam_date"}, "TopicUpdate": {"difficulty"},
            "TaskUpdate": {"deadline", "notes"},
            "StudySessionUpdate": {"duration_minutes", "notes", "topic_uid", "task_uid"},
            "ExamResultUpdate": {"exam_date", "score_percent"},
        }.get(type(self).__name__, set())
        for key in self.model_fields_set - nullable:
            value = getattr(self, key)
            if value is None or isinstance(value, str) and not value.strip() and key not in {"task_shortcut", "ai_shortcut"}:
                raise ValueError(tr('Field {0} cannot be empty.', key))
        return self


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = Field(default=None, exclude=True)
    email: EmailStr | None = None
    timezone: str = Field(default="Europe/Warsaw", max_length=64)
    language: Literal["en", "pl"] = "en"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError as exc: raise ValueError(tr('Unknown time zone.')) from exc
        return value

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or any(char.isspace() for char in value):
            raise ValueError(tr('Username must be at least 2 characters long and cannot contain spaces.'))
        return value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError(tr('Passwords must match.'))
        return self

class UserUpdate(PatchModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    confirm_password: str | None = Field(default=None, exclude=True)
    email: EmailStr | None = None
    timezone: str | None = Field(default=None, max_length=64)
    language: Literal["en", "pl"] | None = None
    preferred_minutes: int | None = Field(default=None, ge=10, le=240)
    preferred_study_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    task_shortcut: str | None = Field(default=None, max_length=30)
    ai_shortcut: str | None = Field(default=None, max_length=30)
    onboarding_complete: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is None: return None
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError as exc: raise ValueError(tr('Unknown time zone.')) from exc
        return value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError(tr('Passwords must match.'))
        return self

class UserRead(OrmSchema):
    user_uid: UUID
    username: str
    email: EmailStr | None
    created_at: datetime
    timezone: str
    language: Literal["en", "pl"]
    preferred_minutes: int
    preferred_study_time: str
    task_shortcut: str
    ai_shortcut: str
    onboarding_complete: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"

class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exam_date: date | None = None
    color: str = Field(default="#c8f05a", pattern=r"^#[0-9a-fA-F]{6}$")
    tags: list[str] = Field(default_factory=list, max_length=10)

class SubjectUpdate(PatchModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    exam_date: date | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    tags: list[str] | None = Field(default=None, max_length=10)
    archived: bool | None = None

class SubjectRead(OrmSchema):
    subject_uid: UUID
    name: str
    user_uid: UUID
    exam_date: date | None
    color: str
    tags: list[str]
    archived_at: datetime | None

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject_uid: UUID
    difficulty: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(tr('Topic name cannot be empty.'))
        return value

class TopicUpdate(PatchModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    subject_uid: UUID | None = None
    difficulty: str | None = Field(default=None, max_length=20)
    is_done: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError(tr('Topic name cannot be empty.'))
        return value

class TopicRead(OrmSchema):
    topic_uid: UUID
    name: str
    subject_uid: UUID
    difficulty: str | None
    is_done: bool

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    topic_uid: UUID
    deadline: datetime | None = None
    priority: Priority = Priority.MEDIUM
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(tr('Task title cannot be empty.'))
        return value

class TaskUpdate(PatchModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    topic_uid: UUID | None = None
    is_done: bool | None = None
    deadline: datetime | None = None
    priority: Priority | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError(tr('Task title cannot be empty.'))
        return value

class TaskRead(OrmSchema):
    task_uid: UUID
    title: str
    topic_uid: UUID
    is_done: bool
    deadline: datetime | None
    priority: Priority
    notes: str | None

class TaskBulkComplete(BaseModel):
    task_uids: list[UUID] = Field(min_length=1, max_length=1000)

class StudySessionCreate(BaseModel):
    subject_uid: UUID
    title: str = Field(default_factory=lambda: tr('Study session'), min_length=1, max_length=160)
    started_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None
    topic_uid: UUID | None = None
    task_uid: UUID | None = None

class StudySessionUpdate(PatchModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    subject_uid: UUID | None = None
    started_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None
    topic_uid: UUID | None = None
    task_uid: UUID | None = None

class StudySessionRead(OrmSchema):
    study_uid: UUID
    title: str
    subject_uid: UUID
    started_at: datetime
    duration_minutes: int | None
    notes: str | None
    topic_uid: UUID | None
    task_uid: UUID | None

class ExamResultCreate(BaseModel):
    subject_uid: UUID
    exam_date: date | None = None
    score_percent: Decimal | None = Field(default=None, ge=0, le=100)

class ExamResultUpdate(PatchModel):
    subject_uid: UUID | None = None
    exam_date: date | None = None
    score_percent: Decimal | None = Field(default=None, ge=0, le=100)

class ExamResultRead(OrmSchema):
    exam_uid: UUID
    subject_uid: UUID
    exam_date: date | None
    score_percent: Decimal | None
