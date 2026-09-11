from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.ai import AiMaterialRead, GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, NoteGenerationRequest, PlanGenerationRequest, SessionNoteGenerationRequest
from app.services import ai as ai_service
from app.services import study

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/session-note", response_model=GeneratedSessionNote)
async def generate_session_note(payload: SessionNoteGenerationRequest, user: models.User = Depends(get_current_user)):
    return await ai_service.generate_session_note(payload.description, payload.language)


def _task_and_goal(payload, topic_uid: UUID, db: Session, user: models.User):
    if payload.task_uid:
        task = study.get_task(db, payload.task_uid, user.user_uid)
        if task.topic_uid != topic_uid:
            raise HTTPException(status_code=422, detail="Wybrane zadanie nie należy do tego tematu.")
        return task, task.title
    goal = payload.custom_goal.strip() if payload.custom_goal and payload.custom_goal.strip() else None
    return None, goal


def _assign_task(db: Session, topic_uid: UUID, selected_task, result):
    if selected_task is not None:
        return selected_task
    task = models.Task(title=result.task_title.strip(), topic_uid=topic_uid, priority=models.Priority.MEDIUM)
    db.add(task)
    db.flush()
    return task


def _notes_as_text(result: GeneratedNotes) -> str:
    sections = "\n\n".join(f"{section.heading}\n{section.content}" for section in result.sections)
    key_points = "\n".join(f"• {point}" for point in result.key_points)
    questions = "\n".join(f"{number}. {question}" for number, question in enumerate(result.review_questions, 1))
    return f"{result.title}\n\n{result.summary}\n\n{sections}\n\nNajważniejsze punkty\n{key_points}\n\nPytania kontrolne\n{questions}".strip()


def _save_material(db: Session, user_uid: UUID, topic_uid: UUID, task_uid: UUID | None, material_type: str, result):
    material = models.AiMaterial(user_uid=user_uid, topic_uid=topic_uid, task_uid=task_uid, material_type=material_type, title=result.title, content=result.model_dump(mode="json"))
    db.add(material)
    db.commit()


@router.get("/materials", response_model=list[AiMaterialRead])
def list_materials(task_uid: UUID | None = Query(default=None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = select(models.AiMaterial).where(models.AiMaterial.user_uid == user.user_uid)
    if task_uid is not None:
        study.get_task(db, task_uid, user.user_uid)
        query = query.where(models.AiMaterial.task_uid == task_uid)
    return list(db.scalars(query.order_by(models.AiMaterial.created_at.desc()).limit(50)))


@router.post("/topics/{topic_uid}/notes", response_model=GeneratedNotes)
async def generate_notes(
    topic_uid: UUID,
    payload: NoteGenerationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    selected_task, goal = _task_and_goal(payload, topic_uid, db, user)
    result = await ai_service.generate_topic_notes(
        subject_name=subject.name,
        topic_name=topic.name,
        difficulty=topic.difficulty,
        language=payload.language,
        detail_level=payload.detail_level,
        goal=goal,
    )
    task = _assign_task(db, topic_uid, selected_task, result)
    generated_notes = _notes_as_text(result)
    task.notes = f"{task.notes}\n\n--- Notatka AI ---\n{generated_notes}" if task.notes else generated_notes
    _save_material(db, user.user_uid, topic_uid, task.task_uid, "notes", result)
    return result


@router.post("/topics/{topic_uid}/plan", response_model=GeneratedStudyPlan)
async def generate_plan(topic_uid: UUID, payload: PlanGenerationRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    selected_task, goal = _task_and_goal(payload, topic_uid, db, user)
    result = await ai_service.generate_study_plan(subject.name, topic.name, topic.difficulty, payload.language, payload.days, payload.minutes_per_day, goal)
    task = _assign_task(db, topic_uid, selected_task, result)
    _save_material(db, user.user_uid, topic_uid, task.task_uid, "plan", result)
    return result
