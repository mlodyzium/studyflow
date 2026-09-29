import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, UniqueConstraint, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw", server_default="Europe/Warsaw")
    preferred_minutes: Mapped[int] = mapped_column(Integer, default=45, server_default="45")
    preferred_study_time: Mapped[str] = mapped_column(String(5), default="18:00", server_default="18:00")
    task_shortcut: Mapped[str] = mapped_column(String(30), default="", server_default="")
    ai_shortcut: Mapped[str] = mapped_column(String(30), default="", server_default="")
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_login_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subjects: Mapped[list["Subject"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"
    subject_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column("nazwa", String(100))
    nazwa = synonym("name")
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"))
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#c8f05a", server_default="#c8f05a")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("uq_subject_user_name", "user_uid", func.lower(func.trim(name)), unique=True),
        Index("ix_subject_user_archived", "user_uid", "archived_at"),
    )
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
    __table_args__ = (Index("uq_topic_subject_name", "subject_uid", func.lower(func.trim(name)), unique=True),)
    subject: Mapped["Subject"] = relationship(back_populates="topics")
    tasks: Mapped[list["Task"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="topic")

class Task(Base):
    __tablename__ = "tasks"
    task_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    topic_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.topic_uid", ondelete="CASCADE"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[Priority] = mapped_column(PostgreSQLEnum(Priority, name="session_priority"), default=Priority.MEDIUM)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped["Topic"] = relationship(back_populates="tasks")
    study_sessions: Mapped[list["StudySession"]] = relationship(back_populates="task")
    __table_args__ = (Index("ix_task_topic_deadline", "topic_uid", "deadline"),)

class StudySession(Base):
    __tablename__ = "study_sessions"
    study_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(160), default="Sesja nauki")
    subject_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.subject_uid", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("material_type IN ('notes', 'plan')", name="ai_material_type_valid"),
        Index("ix_ai_material_user_created", "user_uid", "created_at"),
    )


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    conversation_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    user_message: Mapped[str] = mapped_column(String(3000))
    assistant_message: Mapped[str] = mapped_column(String(4000))
    proposal: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (Index("ix_ai_conversation_user_created", "user_uid", "created_at"),)


class StudyPlan(Base):
    __tablename__ = "study_plans"
    plan_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"), index=True)
    topic_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.topic_uid", ondelete="CASCADE"), index=True)
    material_uid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_materials.material_uid", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    overview: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    start_date: Mapped[date] = mapped_column(Date)
    minutes_per_day: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    days: Mapped[list["StudyPlanDay"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="StudyPlanDay.day_number")
    __table_args__ = (Index("ix_study_plan_user_start", "user_uid", "start_date"),)


class StudyPlanDay(Base):
    __tablename__ = "study_plan_days"
    day_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.plan_uid", ondelete="CASCADE"), index=True)
    day_number: Mapped[int] = mapped_column(Integer)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(Text)
    activities: Mapped[list[str]] = mapped_column(JSON)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    calendar_task_uid: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.task_uid", ondelete="SET NULL"), nullable=True)
    plan: Mapped["StudyPlan"] = relationship(back_populates="days")
    __table_args__ = (UniqueConstraint("plan_uid", "day_number", name="uq_plan_day_number"),)


class ReviewSchedule(Base):
    __tablename__ = "review_schedules"
    review_uid: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_uid", ondelete="CASCADE"), index=True)
    material_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_materials.material_uid", ondelete="CASCADE"), unique=True)
    topic_uid: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.topic_uid", ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_review_user_due", "user_uid", "due_at"),)
