import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
from app.db.database import Base

class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class User(Base):
    __tablename__ = "users"
    user_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    subjects: Mapped[list["Subject"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"
    subject_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column("nazwa", String(100))
    nazwa = synonym("name")
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"))
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    user: Mapped["User"] = relationship(back_populates="subjects")
    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    exam_results: Mapped[list["ExamResult"]] = relationship(back_populates="subject", cascade="all, delete-orphan")

class Topic(Base):
    __tablename__ = "topics"
    topic_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column("nazwa", String(100))
    nazwa = synonym("name")
    subject_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_done: Mapped[bool] = mapped_column("status", Boolean, default=False)
    status = synonym("is_done")
    subject: Mapped["Subject"] = relationship(back_populates="topics")
    tasks: Mapped[list["Task"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="topic")

class Task(Base):
    __tablename__ = "tasks"
    task_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    topic_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.topic_uid", ondelete="CASCADE"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[Priority] = mapped_column(PostgreSQLEnum(Priority, name="session_priority"), default=Priority.MEDIUM)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped["Topic"] = relationship(back_populates="tasks")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="task")

class StudySession(Base):
    __tablename__ = "study_sessions"
    study_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_uid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.topic_uid", ondelete="SET NULL"), nullable=True)
    task_uid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.task_uid", ondelete="SET NULL"), nullable=True)
    __table_args__ = (
        CheckConstraint("duration_minutes >= 0", name="duration_minutes_positive"),
    )
    subject: Mapped["Subject"] = relationship(back_populates="study_sessions")
    topic: Mapped["Topic | None"] = relationship(back_populates="study_sessions")
    task: Mapped["Task | None"] = relationship(back_populates="study_sessions")

class ExamResult(Base):
    __tablename__ = "exam_results"
    exam_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    score_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    __table_args__ = (
        CheckConstraint("score_percent BETWEEN 0 AND 100", name="score_percent_range"),
    )
    subject: Mapped["Subject"] = relationship(back_populates="exam_results")


class AiMaterial(Base):
    __tablename__ = "ai_materials"
    material_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"), index=True)
    topic_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.topic_uid", ondelete="CASCADE"), index=True)
    task_uid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.task_uid", ondelete="SET NULL"), nullable=True)
    material_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
