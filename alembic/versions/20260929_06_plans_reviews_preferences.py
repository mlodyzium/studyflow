"""Plans, reviews, subject organization and UTC timestamps.

Revision ID: 20260929_06
Revises: 20260913_05
"""
from collections.abc import Sequence
from datetime import date, timedelta
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_06"
down_revision: str | None = "20260913_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(64), server_default="Europe/Warsaw", nullable=False))
    op.add_column("users", sa.Column("preferred_minutes", sa.Integer(), server_default="45", nullable=False))
    op.add_column("users", sa.Column("preferred_study_time", sa.String(5), server_default="18:00", nullable=False))
    op.add_column("users", sa.Column("task_shortcut", sa.String(30), server_default="Alt+N", nullable=False))
    op.add_column("users", sa.Column("onboarding_complete", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE users SET onboarding_complete = true")
    op.add_column("subjects", sa.Column("color", sa.String(7), server_default="#c8f05a", nullable=False))
    op.add_column("subjects", sa.Column("tags", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False))
    op.add_column("subjects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    for table, column in (
        ("users", "created_at"), ("tasks", "deadline"),
        ("study_sessions", "started_at"), ("ai_materials", "created_at"),
        ("ai_conversations", "created_at"),
    ):
        op.alter_column(table, column, type_=sa.DateTime(timezone=True),
                        postgresql_using=f"{column} AT TIME ZONE 'UTC'")

    op.execute("""WITH duplicates AS (
      SELECT subject_uid, row_number() OVER (PARTITION BY user_uid, lower(trim(nazwa)) ORDER BY subject_uid) AS n
      FROM subjects
    ) UPDATE subjects s SET nazwa = left(s.nazwa, 88) || ' (' || left(s.subject_uid::text, 8) || ')'
      FROM duplicates d WHERE s.subject_uid = d.subject_uid AND d.n > 1""")
    op.execute("""WITH duplicates AS (
      SELECT topic_uid, row_number() OVER (PARTITION BY subject_uid, lower(trim(nazwa)) ORDER BY topic_uid) AS n
      FROM topics
    ) UPDATE topics t SET nazwa = left(t.nazwa, 88) || ' (' || left(t.topic_uid::text, 8) || ')'
      FROM duplicates d WHERE t.topic_uid = d.topic_uid AND d.n > 1""")
    op.create_index("uq_subject_user_name", "subjects", ["user_uid", sa.text("lower(trim(nazwa))")], unique=True)
    op.create_index("ix_subject_user_archived", "subjects", ["user_uid", "archived_at"])
    op.create_index("uq_topic_subject_name", "topics", ["subject_uid", sa.text("lower(trim(nazwa))")], unique=True)
    op.create_index("ix_task_topic_deadline", "tasks", ["topic_uid", "deadline"])
    op.create_index("ix_ai_material_user_created", "ai_materials", ["user_uid", "created_at"])
    op.create_index("ix_ai_conversation_user_created", "ai_conversations", ["user_uid", "created_at"])
    op.create_check_constraint("ai_material_type_valid", "ai_materials", "material_type IN ('notes', 'plan')")

    op.create_table("study_plans",
        sa.Column("plan_uid", sa.Uuid(), primary_key=True),
        sa.Column("user_uid", sa.Uuid(), sa.ForeignKey("users.user_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_uid", sa.Uuid(), sa.ForeignKey("topics.topic_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("material_uid", sa.Uuid(), sa.ForeignKey("ai_materials.material_uid", ondelete="SET NULL")),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_study_plans_user_uid", "study_plans", ["user_uid"])
    op.create_index("ix_study_plans_topic_uid", "study_plans", ["topic_uid"])
    op.create_index("ix_study_plan_user_start", "study_plans", ["user_uid", "start_date"])
    op.create_table("study_plan_days",
        sa.Column("day_uid", sa.Uuid(), primary_key=True),
        sa.Column("plan_uid", sa.Uuid(), sa.ForeignKey("study_plans.plan_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("activities", sa.JSON(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_done", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("calendar_task_uid", sa.Uuid(), sa.ForeignKey("tasks.task_uid", ondelete="SET NULL")),
        sa.UniqueConstraint("plan_uid", "day_number", name="uq_plan_day_number"),
    )
    op.create_index("ix_study_plan_days_plan_uid", "study_plan_days", ["plan_uid"])
    op.create_index("ix_study_plan_days_scheduled_date", "study_plan_days", ["scheduled_date"])
    op.create_table("review_schedules",
        sa.Column("review_uid", sa.Uuid(), primary_key=True),
        sa.Column("user_uid", sa.Uuid(), sa.ForeignKey("users.user_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("material_uid", sa.Uuid(), sa.ForeignKey("ai_materials.material_uid", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("topic_uid", sa.Uuid(), sa.ForeignKey("topics.topic_uid", ondelete="CASCADE"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_review_schedules_user_uid", "review_schedules", ["user_uid"])
    op.create_index("ix_review_schedules_due_at", "review_schedules", ["due_at"])
    op.create_index("ix_review_user_due", "review_schedules", ["user_uid", "due_at"])

    connection = op.get_bind()
    old_plans = connection.execute(sa.text("SELECT material_uid, user_uid, topic_uid, title, content, created_at FROM ai_materials WHERE material_type='plan'"))
    for material_uid, user_uid, topic_uid, title, content, created_at in old_plans:
        if not isinstance(content, dict) or not content.get("steps"):
            continue
        start = date.fromisoformat(content["start_date"]) if content.get("start_date") else created_at.date()
        plan_uid = uuid4()
        connection.execute(sa.text("""INSERT INTO study_plans
          (plan_uid,user_uid,topic_uid,material_uid,title,overview,success_criteria,start_date,minutes_per_day,created_at)
          VALUES (:id,:user,:topic,:material,:title,:overview,:criteria,:start,:minutes,:created)"""),
          {"id": plan_uid, "user": user_uid, "topic": topic_uid, "material": material_uid,
           "title": title, "overview": content.get("overview", ""),
           "criteria": sa.JSON().bind_processor(connection.dialect)(content.get("success_criteria", [])),
           "start": start, "minutes": max((step.get("duration_minutes", 45) for step in content["steps"]), default=45),
           "created": created_at})
        for step in content["steps"]:
            number = int(step.get("day", 1))
            connection.execute(sa.text("""INSERT INTO study_plan_days
              (day_uid,plan_uid,day_number,scheduled_date,title,objective,activities,duration_minutes,is_done)
              VALUES (:id,:plan,:number,:day,:title,:objective,:activities,:minutes,false)"""),
              {"id": uuid4(), "plan": plan_uid, "number": number,
               "day": start + timedelta(days=number - 1), "title": step.get("title", f"Day {number}"),
               "objective": step.get("objective", ""),
               "activities": sa.JSON().bind_processor(connection.dialect)(step.get("activities", [])),
               "minutes": int(step.get("duration_minutes", 45))})

    # Existing notes become available in the review queue after deployment.
    connection.execute(sa.text("""INSERT INTO review_schedules
      (review_uid,user_uid,material_uid,topic_uid,due_at,interval_days,streak)
      SELECT gen_random_uuid(),user_uid,material_uid,topic_uid,
             greatest(now(), created_at + interval '1 day'),1,0
      FROM ai_materials WHERE material_type='notes'"""))


def downgrade() -> None:
    op.drop_table("review_schedules")
    op.drop_table("study_plan_days")
    op.drop_table("study_plans")
    op.drop_constraint("ai_material_type_valid", "ai_materials", type_="check")
    for name, table in (("ix_ai_conversation_user_created", "ai_conversations"), ("ix_ai_material_user_created", "ai_materials"),
                        ("ix_task_topic_deadline", "tasks"), ("uq_topic_subject_name", "topics"),
                        ("ix_subject_user_archived", "subjects"), ("uq_subject_user_name", "subjects")):
        op.drop_index(name, table_name=table)
    for table, column in (("users", "created_at"), ("tasks", "deadline"), ("study_sessions", "started_at"),
                          ("ai_materials", "created_at"), ("ai_conversations", "created_at")):
        op.alter_column(table, column, type_=sa.DateTime(), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
    for field in ("archived_at", "tags", "color"):
        op.drop_column("subjects", field)
    for field in ("onboarding_complete", "task_shortcut", "preferred_study_time", "preferred_minutes", "timezone"):
        op.drop_column("users", field)
