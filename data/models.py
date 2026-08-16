import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base


class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class User(Base):
    __tablename__ = "users"
    user_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nazwa: Mapped[str] = mapped_column(String(100), nullable=False)
    user_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_uid", ondelete="CASCADE"))
    exam_date: Mapped[date] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship(back_populates="subjects")
    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    exam_results: Mapped[list["ExamResult"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"
    topic_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nazwa: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    difficulty: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="topics")
    tasks: Mapped[list["Task"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    task_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    topic_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.topic_uid", ondelete="CASCADE"))
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority, name="session_priority"), default=Priority.MEDIUM)

    topic: Mapped["Topic"] = relationship(back_populates="tasks")


class StudySession(Base):
    __tablename__ = "study_sessions"
    study_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("duration_minutes >= 0", name="duration_minutes_positive"),
    )

    subject: Mapped["Subject"] = relationship(back_populates="study_sessions")


class ExamResult(Base):
    __tablename__ = "exam_results"
    exam_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    exam_date: Mapped[date] = mapped_column(Date, nullable=True)
    score_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)

    __table_args__ = (
        CheckConstraint("score_percent BETWEEN 0 AND 100", name="score_percent_range"),
    )

    subject: Mapped["Subject"] = relationship(back_populates="exam_results")