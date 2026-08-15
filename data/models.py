import enum
import uuid
from datetime import date, datetime

from database import Base
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class User(Base):
    __tablename__ = "users"
    user_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="user")


class Subject(Base):
    __tablename__ = "subjects"
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nazwa: Mapped[str] = mapped_column(String(100), nullable=False)
    user_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_uid", ondelete="CASCADE"))
    exam_date: Mapped[date] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship(back_populates="subjects")
    topics: Mapped[list["Topic"]] = relationship(back_populates="subject")


class Topic(Base):
    __tablename__ = "topics"
    topic_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nazwa: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    difficulty: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="topics")
    tasks: Mapped[list["Task"]] = relationship(back_populates="topic")


class Task(Base):
    __tablename__ = "tasks"
    task_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    topic_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.topic_uid", ondelete="CASCADE"))
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority, name="session_priority"), default=Priority.MEDIUM)

    topic: Mapped["Topic"] = relationship(back_populates="tasks")
