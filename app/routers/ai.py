from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.ai import AiConversationRead, AiMaterialRead, GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, NoteGenerationRequest, PlanGenerationRequest, SessionNoteGenerationRequest, T3achExecuteResult, T3achProposal, T3achRequest
from app.services import ai as ai_service
from app.services import study

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/t3ach/propose", response_model=T3achProposal)
async def propose_t3ach_actions(payload: T3achRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    subjects = list(db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid).order_by(models.Subject.name)))
    topics = list(db.execute(select(models.Subject.name, models.Topic.name).join(models.Topic).where(models.Subject.user_uid == user.user_uid)))
    tasks = list(db.execute(select(models.Subject.name, models.Topic.name, models.Task.title, models.Task.is_done, models.Task.deadline).join(models.Topic, models.Topic.subject_uid == models.Subject.subject_uid).join(models.Task, models.Task.topic_uid == models.Topic.topic_uid).where(models.Subject.user_uid == user.user_uid)))
    materials = list(db.execute(select(models.AiMaterial.material_type, models.AiMaterial.title, models.Task.title).outerjoin(models.Task, models.Task.task_uid == models.AiMaterial.task_uid).where(models.AiMaterial.user_uid == user.user_uid).order_by(models.AiMaterial.created_at.desc()).limit(30)))
    task_context = [f"{subject} — {topic} — {task} — {'ukończone' if done else 'aktywne'} — {deadline.isoformat() if deadline else 'bez terminu'}" for subject, topic, task, done, deadline in tasks]
    material_context = [f"{kind} — {title} — {task or 'bez zadania'}" for kind, title, task in materials]
    proposal = await ai_service.generate_t3ach_proposal(payload.message, payload.language, [item.name for item in subjects], [f"{subject} — {topic}" for subject, topic in topics], task_context, material_context)
    if not proposal.needs_clarification and proposal.subject_name and proposal.topic_name:
        if proposal.intent == "study_plan":
            preview = await ai_service.generate_study_plan(
                proposal.subject_name, proposal.topic_name, proposal.difficulty,
                payload.language, proposal.days, proposal.minutes_per_day, proposal.reply,
            )
            proposal.preview = preview.model_dump(mode="json")
            proposal.reply = f"{proposal.reply}\n\n{_plan_preview_as_text(preview)}"
        elif proposal.intent == "notes":
            preview = await ai_service.generate_topic_notes(
                proposal.subject_name, proposal.topic_name, proposal.difficulty,
                payload.language, "standard", proposal.reply,
            )
            proposal.preview = preview.model_dump(mode="json")
            proposal.reply = f"{proposal.reply}\n\n{_notes_as_text(preview)}"
    last_user_message = payload.message.rsplit("Użytkownik:", 1)[-1].strip()[:3000]
    db.add(models.AiConversation(user_uid=user.user_uid, title=last_user_message[:157] or "Rozmowa z T3ACH", user_message=last_user_message, assistant_message=(proposal.question or proposal.reply)[:4000], proposal=proposal.model_dump(mode="json")))
    db.commit()
    return proposal


@router.get("/t3ach/history", response_model=list[AiConversationRead])
def list_t3ach_history(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return list(db.scalars(select(models.AiConversation).where(models.AiConversation.user_uid == user.user_uid).order_by(models.AiConversation.created_at.desc()).limit(50)))


@router.delete("/t3ach/history/{conversation_uid}", status_code=204)
def delete_t3ach_history(conversation_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    value = db.scalar(select(models.AiConversation).where(models.AiConversation.conversation_uid == conversation_uid, models.AiConversation.user_uid == user.user_uid))
    if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono rozmowy.")
    db.delete(value); db.commit()


@router.post("/t3ach/execute", response_model=T3achExecuteResult)
async def execute_t3ach_actions(proposal: T3achProposal, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if proposal.needs_clarification:
        raise HTTPException(status_code=422, detail="Ta propozycja nie zawiera jeszcze działań do zapisania.")
    if proposal.intent == "edit":
        if not proposal.target_kind or not proposal.target_name:
            raise HTTPException(status_code=422, detail="Brakuje elementu, który ma zostać zmieniony.")
        name = proposal.target_name.strip().lower()
        subject_uid = topic_uid = None
        if proposal.target_kind == "subject":
            value = db.scalar(select(models.Subject).where(models.Subject.user_uid == user.user_uid, func.lower(models.Subject.name) == name))
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego przedmiotu.")
            if proposal.new_name: value.name = proposal.new_name.strip()
            subject_uid = value.subject_uid
        elif proposal.target_kind == "topic":
            value = db.scalar(select(models.Topic).join(models.Subject).where(models.Subject.user_uid == user.user_uid, func.lower(models.Topic.name) == name))
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego tematu.")
            if proposal.new_name: value.name = proposal.new_name.strip()
            if proposal.difficulty is not None: value.difficulty = proposal.difficulty
            if proposal.new_is_done is not None: value.is_done = proposal.new_is_done
            topic_uid = value.topic_uid; subject_uid = value.subject_uid
        else:
            value = db.scalar(select(models.Task).join(models.Topic).join(models.Subject).where(models.Subject.user_uid == user.user_uid, func.lower(models.Task.title) == name))
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego zadania.")
            if proposal.new_name: value.title = proposal.new_name.strip()
            if proposal.new_priority: value.priority = models.Priority(proposal.new_priority)
            if proposal.new_is_done is not None: value.is_done = proposal.new_is_done
            topic_uid = value.topic_uid; subject_uid = db.scalar(select(models.Topic.subject_uid).where(models.Topic.topic_uid == value.topic_uid))
        db.commit()
        return T3achExecuteResult(message=f"Zaktualizowano {proposal.target_kind}: {proposal.target_name}.", subject_uid=subject_uid, topic_uid=topic_uid, task_uids=[], created_subject=False, created_topic=False)
    if not proposal.subject_name or not proposal.topic_name or not proposal.tasks:
        raise HTTPException(status_code=422, detail="Ta propozycja nie zawiera jeszcze działań do zapisania.")
    subject_name = proposal.subject_name.strip()
    topic_name = proposal.topic_name.strip()
    subject = db.scalar(select(models.Subject).where(models.Subject.user_uid == user.user_uid, func.lower(models.Subject.name) == subject_name.lower()))
    created_subject = subject is None
    if subject is None:
        subject = models.Subject(name=subject_name, user_uid=user.user_uid)
        db.add(subject)
        db.flush()
    topic = db.scalar(select(models.Topic).where(models.Topic.subject_uid == subject.subject_uid, func.lower(models.Topic.name) == topic_name.lower()))
    created_topic = topic is None
    if topic is None:
        topic = models.Topic(name=topic_name, subject_uid=subject.subject_uid, difficulty=proposal.difficulty)
        db.add(topic)
        db.flush()
    now = datetime.now(timezone.utc)
    task_items = proposal.tasks if proposal.intent == "organize" else proposal.tasks[:1]
    tasks = []
    reused_task = False
    if proposal.intent in {"study_plan", "notes"} and proposal.target_name:
        existing_task = db.scalar(select(models.Task).where(models.Task.topic_uid == topic.topic_uid, func.lower(models.Task.title) == proposal.target_name.strip().lower()))
        if existing_task is not None:
            tasks.append(existing_task)
            reused_task = True
    for item in task_items:
        if reused_task:
            break
        duplicate = db.scalar(select(models.Task).where(models.Task.topic_uid == topic.topic_uid, func.lower(models.Task.title) == item.title.strip().lower()))
        if duplicate is not None:
            tasks.append(duplicate)
            continue
        deadline = now + timedelta(days=item.deadline_days) if item.deadline_days is not None else None
        task = models.Task(title=item.title.strip(), topic_uid=topic.topic_uid, priority=models.Priority(item.priority), deadline=deadline, notes=item.notes)
        db.add(task)
        tasks.append(task)
    db.flush()
    if proposal.intent == "study_plan":
        result = GeneratedStudyPlan.model_validate(proposal.preview) if proposal.preview else await ai_service.generate_study_plan(subject.name, topic.name, topic.difficulty, f"język i styl zgodny z: {proposal.reply[:200]}", proposal.days, proposal.minutes_per_day, proposal.reply)
        if not reused_task: tasks[0].title = result.task_title.strip()
        _save_material(db, user.user_uid, topic.topic_uid, tasks[0].task_uid, "plan", result)
        message = f"Utworzono plan „{result.title}” w {subject.name} → {topic.name} i przypisano go do zadania „{tasks[0].title}”."
    elif proposal.intent == "notes":
        result = GeneratedNotes.model_validate(proposal.preview) if proposal.preview else await ai_service.generate_topic_notes(subject.name, topic.name, topic.difficulty, f"język i styl zgodny z: {proposal.reply[:200]}", "standard", proposal.reply)
        if not reused_task: tasks[0].title = result.task_title.strip()
        generated_notes = _notes_as_text(result)
        tasks[0].notes = f"{tasks[0].notes}\n\n--- Notatka AI ---\n{generated_notes}" if tasks[0].notes else generated_notes
        _save_material(db, user.user_uid, topic.topic_uid, tasks[0].task_uid, "notes", result)
        message = f"Utworzono notatkę „{result.title}” w {subject.name} → {topic.name} i przypisano ją do zadania „{tasks[0].title}”."
    else:
        db.commit()
        message = f"W {subject.name} → {topic.name} zapisano {len(tasks)} zadań: {', '.join(task.title for task in tasks)}."
    return T3achExecuteResult(message=message, subject_uid=subject.subject_uid, topic_uid=topic.topic_uid, task_uids=[task.task_uid for task in tasks], created_subject=created_subject, created_topic=created_topic)


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


def _plan_preview_as_text(result: GeneratedStudyPlan) -> str:
    steps = "\n\n".join(
        f"Dzień {step.day}: {step.title} ({step.duration_minutes} min)\n{step.objective}\n"
        + "\n".join(f"• {activity}" for activity in step.activities)
        for step in result.steps
    )
    criteria = "\n".join(f"• {item}" for item in result.success_criteria)
    return f"{result.title}\n\n{result.overview}\n\n{steps}\n\nKryteria sukcesu\n{criteria}".strip()


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


@router.delete("/materials/{material_uid}", status_code=204)
def delete_material(material_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    value = db.scalar(select(models.AiMaterial).where(models.AiMaterial.material_uid == material_uid, models.AiMaterial.user_uid == user.user_uid))
    if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono materiału.")
    db.delete(value); db.commit()


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
