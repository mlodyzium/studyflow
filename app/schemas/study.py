from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models import Priority

class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    email: EmailStr | None = None

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    password: str | None = Field(default=None, min_length=8)
    email: EmailStr | None = None

class UserRead(OrmSchema):
    user_uid: UUID
    username: str
    email: EmailStr | None
    created_at: datetime

class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    user_uid: UUID
    exam_date: date | None = None

class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    user_uid: UUID | None = None
    exam_date: date | None = None

class SubjectRead(OrmSchema):
    subject_uid: UUID
    name: str
    user_uid: UUID
    exam_date: date | None

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject_uid: UUID
    difficulty: str | None = Field(default=None, max_length=20)

class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    subject_uid: UUID | None = None
    difficulty: str | None = Field(default=None, max_length=20)
    is_done: bool | None = None

class TopicRead(OrmSchema):
    topic_uid: UUID
    name: str
    subject_uid: UUID
    difficulty: str | None
    is_done: bool

class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    topic_uid: UUID
    deadline: datetime | None = None
    priority: Priority = Priority.MEDIUM

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    topic_uid: UUID | None = None
    is_done: bool | None = None
    deadline: datetime | None = None
    priority: Priority | None = None

class TaskRead(OrmSchema):
    task_uid: UUID
    title: str
    topic_uid: UUID
    is_done: bool
    deadline: datetime | None
    priority: Priority
