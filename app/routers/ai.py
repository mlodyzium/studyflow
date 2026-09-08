from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.ai import AiMaterialRead, GeneratedNotes, GeneratedStudyPlan, NoteGenerationRequest, PlanGenerationRequest
from app.services import ai as ai_service
from app.services import study

router = APIRouter(prefix="/ai", tags=["ai"])


def _goal(payload, topic_uid: UUID, db: Session, user: models.User) -> str | None:
    if payload.task_uid:
        task = study.get_task(db, payload.task_uid, user.user_uid)
        if task.topic_uid != topic_uid:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Wybrane zadanie nie należy do tego tematu.")
        return task.title
    return payload.custom_goal.strip() if payload.custom_goal and payload.custom_goal.strip() else None


def _save_material(db: Session, user_uid: UUID, topic_uid: UUID, task_uid: UUID | None, material_type: str, result):
    material = models.AiMaterial(user_uid=user_uid, topic_uid=topic_uid, task_uid=task_uid, material_type=material_type, title=result.title, content=result.model_dump(mode="json"))
    db.add(material)
    db.commit()


@router.get("/materials", response_model=list[AiMaterialRead])
def list_materials(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return list(db.scalars(select(models.AiMaterial).where(models.AiMaterial.user_uid == user.user_uid).order_by(models.AiMaterial.created_at.desc()).limit(50)))


@router.post("/topics/{topic_uid}/notes", response_model=GeneratedNotes)
async def generate_notes(
    topic_uid: UUID,
    payload: NoteGenerationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    result = await ai_service.generate_topic_notes(
        subject_name=subject.name,
        topic_name=topic.name,
        difficulty=topic.difficulty,
        language=payload.language,
        detail_level=payload.detail_level,
        goal=_goal(payload, topic_uid, db, user),
    )
    _save_material(db, user.user_uid, topic_uid, payload.task_uid, "notes", result)
    return result


@router.post("/topics/{topic_uid}/plan", response_model=GeneratedStudyPlan)
async def generate_plan(topic_uid: UUID, payload: PlanGenerationRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    result = await ai_service.generate_study_plan(subject.name, topic.name, topic.difficulty, payload.language, payload.days, payload.minutes_per_day, _goal(payload, topic_uid, db, user))
    _save_material(db, user.user_uid, topic_uid, payload.task_uid, "plan", result)
    return result
