from datetime import datetime, timedelta, timezone
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.ai import AiConversationRead, AiMaterialRead, GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, NoteGenerationRequest, PlanGenerationRequest, SessionNoteGenerationRequest, T3achExecuteResult, T3achProposal, T3achRequest, T3achSpeechRequest, T3achTaskProposal
from app.schemas.study import StudySessionCreate
from app.services import ai as ai_service
from app.services import study

router = APIRouter(prefix="/ai", tags=["ai"])


def _name_key(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in plain if not unicodedata.combining(char)).split())


def _match_name(value: str | None, names) -> str | None:
    if not value:
        return None
    return next((name for name in names if _name_key(name) == _name_key(value)), None)


def _clarify(proposal: T3achProposal, question: str) -> T3achProposal:
    proposal.needs_clarification = True
    proposal.question = question
    proposal.reply = question
    proposal.tasks = []
    proposal.preview = None
    return proposal


def _prepare_t3ach_proposal(proposal: T3achProposal, subjects, topics, tasks) -> T3achProposal:
    if proposal.needs_clarification:
        return proposal
    if proposal.intent == "edit":
        if not proposal.target_kind or not proposal.target_name:
            return _clarify(proposal, "Co dokładnie mam zmienić? Podaj nazwę przedmiotu, tematu lub zadania.")
        names = ([subject.name for subject in subjects] if proposal.target_kind == "subject" else
                 [topic for subject, topic in topics if not proposal.subject_name or _name_key(subject) == _name_key(proposal.subject_name)] if proposal.target_kind == "topic" else
                 [task for subject, topic, task, *_ in tasks if (not proposal.subject_name or _name_key(subject) == _name_key(proposal.subject_name)) and (not proposal.topic_name or _name_key(topic) == _name_key(proposal.topic_name))])
        matches = [name for name in names if _name_key(name) == _name_key(proposal.target_name)]
        if len(matches) != 1:
            return _clarify(proposal, "Który dokładnie element mam zmienić? Podaj przedmiot, temat i nazwę.")
        proposal.target_name = matches[0]
        return proposal
    if proposal.intent not in {"organize", "study_plan", "notes", "session"}:
        return _clarify(proposal, "Pomagam w nauce. Powiedz proszę, czego chcesz się nauczyć lub co mam zaplanować.")
    if not proposal.subject_name:
        return _clarify(proposal, "Jakiego przedmiotu dotyczy ta prośba?")
    proposal.subject_name = _match_name(proposal.subject_name, (item.name for item in subjects)) or proposal.subject_name.strip()
    if not proposal.topic_name:
        return _clarify(proposal, "Jakiego tematu z tego przedmiotu dotyczy ta prośba?")
    proposal.topic_name = _match_name(proposal.topic_name, (topic for subject, topic in topics if _name_key(subject) == _name_key(proposal.subject_name))) or proposal.topic_name.strip()
    if proposal.intent in {"study_plan", "notes"}:
        proposal.target_name = _match_name(proposal.target_name, (task for subject, topic, task, *_ in tasks if _name_key(subject) == _name_key(proposal.subject_name) and _name_key(topic) == _name_key(proposal.topic_name)))
        if proposal.target_name:
            proposal.tasks = [T3achTaskProposal(title=proposal.target_name)]
        elif not proposal.tasks:
            proposal.tasks = [T3achTaskProposal(title=f"Nauka: {proposal.topic_name}"[:160])]
        else:
            proposal.tasks = proposal.tasks[:1]
    elif proposal.intent == "organize" and not proposal.tasks:
        return _clarify(proposal, "Jakie zadanie lub cel nauki mam dodać?")
    elif proposal.intent == "session":
        proposal.tasks = []
        proposal.session_title = proposal.session_title or f"Nauka: {proposal.topic_name}"
        proposal.session_duration_minutes = proposal.session_duration_minutes or 45
    return proposal


@router.post("/t3ach/speech")
async def t3ach_speech(payload: T3achSpeechRequest, user: models.User = Depends(get_current_user)):
    audio = await ai_service.generate_t3ach_speech(payload.text)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.post("/t3ach/propose", response_model=T3achProposal)
async def propose_t3ach_actions(payload: T3achRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    subjects = list(db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid).order_by(models.Subject.name)))
    topics = list(db.execute(select(models.Subject.name, models.Topic.name).join(models.Topic).where(models.Subject.user_uid == user.user_uid)))
    tasks = list(db.execute(select(models.Subject.name, models.Topic.name, models.Task.title, models.Task.is_done, models.Task.deadline).join(models.Topic, models.Topic.subject_uid == models.Subject.subject_uid).join(models.Task, models.Task.topic_uid == models.Topic.topic_uid).where(models.Subject.user_uid == user.user_uid)))
    materials = list(db.execute(select(models.AiMaterial.material_type, models.AiMaterial.title, models.Task.title).outerjoin(models.Task, models.Task.task_uid == models.AiMaterial.task_uid).where(models.AiMaterial.user_uid == user.user_uid).order_by(models.AiMaterial.created_at.desc()).limit(30)))
    task_context = [f"{subject} — {topic} — {task} — {'ukończone' if done else 'aktywne'} — {deadline.isoformat() if deadline else 'bez terminu'}" for subject, topic, task, done, deadline in tasks]
    material_context = [f"{kind} — {title} — {task or 'bez zadania'}" for kind, title, task in materials]
    proposal = await ai_service.generate_t3ach_proposal(payload.message, payload.language, [item.name for item in subjects], [f"{subject} — {topic}" for subject, topic in topics], task_context, material_context)
    proposal = _prepare_t3ach_proposal(proposal, subjects, topics, tasks)
    if not proposal.needs_clarification and proposal.subject_name and proposal.topic_name:
        try:
            if proposal.intent == "study_plan":
                preview = await ai_service.generate_study_plan(
                    proposal.subject_name, proposal.topic_name, proposal.difficulty,
                    payload.language, proposal.days, proposal.minutes_per_day, proposal.reply,
                )
                proposal.preview = preview.model_dump(mode="json")
                proposal.reply = f"{proposal.reply}\n\n{_plan_preview_as_text(preview)}"[:12000]
            elif proposal.intent == "notes":
                preview = await ai_service.generate_topic_notes(
                    proposal.subject_name, proposal.topic_name, proposal.difficulty,
                    payload.language, "standard", proposal.reply,
                )
                proposal.preview = preview.model_dump(mode="json")
                proposal.reply = f"{proposal.reply}\n\n{_notes_as_text(preview)}"[:12000]
        except HTTPException as exc:
            if exc.status_code != 502:
                raise
            proposal = _clarify(proposal, "Rozumiem, co chcesz przygotować, ale nie udało mi się teraz wygenerować materiału. Spróbuj proszę ponownie za chwilę.")
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
    if proposal.intent == "session":
        if not proposal.subject_name or not proposal.session_title or not proposal.session_duration_minutes:
            raise HTTPException(status_code=422, detail="Brakuje danych sesji nauki.")
        subject = next((item for item in db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid)) if _name_key(item.name) == _name_key(proposal.subject_name)), None)
        created_subject = subject is None
        if subject is None:
            subject = models.Subject(name=proposal.subject_name.strip(), user_uid=user.user_uid)
            db.add(subject)
            db.flush()
        topic = next((item for item in db.scalars(select(models.Topic).where(models.Topic.subject_uid == subject.subject_uid)) if _name_key(item.name) == _name_key(proposal.topic_name)), None) if proposal.topic_name else None
        created_topic = topic is None and bool(proposal.topic_name)
        if created_topic:
            topic = models.Topic(name=proposal.topic_name.strip(), subject_uid=subject.subject_uid, difficulty=proposal.difficulty)
            db.add(topic)
            db.flush()
        session = study.create_study_session(db, StudySessionCreate(subject_uid=subject.subject_uid, topic_uid=topic.topic_uid if topic else None, title=proposal.session_title.strip(), duration_minutes=proposal.session_duration_minutes, notes=proposal.session_notes), user.user_uid)
        return T3achExecuteResult(message=f"Zapisano sesję „{session.title}” w {subject.name}.", subject_uid=subject.subject_uid, topic_uid=topic.topic_uid if topic else None, task_uids=[], created_subject=created_subject, created_topic=created_topic)
    if proposal.intent == "edit":
        if not proposal.target_kind or not proposal.target_name:
            raise HTTPException(status_code=422, detail="Brakuje elementu, który ma zostać zmieniony.")
        name = _name_key(proposal.target_name)
        subject_uid = topic_uid = None
        if proposal.target_kind == "subject":
            value = next((item for item in db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid)) if _name_key(item.name) == name), None)
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego przedmiotu.")
            if proposal.new_name: value.name = proposal.new_name.strip()
            subject_uid = value.subject_uid
        elif proposal.target_kind == "topic":
            candidates = db.execute(select(models.Topic, models.Subject.name).join(models.Subject).where(models.Subject.user_uid == user.user_uid)).all()
            matches = [item for item, subject_name in candidates if _name_key(item.name) == name and (not proposal.subject_name or _name_key(subject_name) == _name_key(proposal.subject_name))]
            if len(matches) > 1: raise HTTPException(status_code=422, detail="Wiele tematów ma tę nazwę. Podaj przedmiot.")
            value = matches[0] if matches else None
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego tematu.")
            if proposal.new_name: value.name = proposal.new_name.strip()
            if proposal.difficulty is not None: value.difficulty = proposal.difficulty
            if proposal.new_is_done is not None: value.is_done = proposal.new_is_done
            topic_uid = value.topic_uid; subject_uid = value.subject_uid
        else:
            candidates = db.execute(select(models.Task, models.Topic.name, models.Subject.name).join(models.Topic).join(models.Subject).where(models.Subject.user_uid == user.user_uid)).all()
            matches = [item for item, topic_name, subject_name in candidates if _name_key(item.title) == name and (not proposal.subject_name or _name_key(subject_name) == _name_key(proposal.subject_name)) and (not proposal.topic_name or _name_key(topic_name) == _name_key(proposal.topic_name))]
            if len(matches) > 1: raise HTTPException(status_code=422, detail="Wiele zadań ma tę nazwę. Podaj przedmiot i temat.")
            value = matches[0] if matches else None
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
    subject = next((item for item in db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid)) if _name_key(item.name) == _name_key(subject_name)), None)
    created_subject = subject is None
    if subject is None:
        subject = models.Subject(name=subject_name, user_uid=user.user_uid)
        db.add(subject)
        db.flush()
    topic = next((item for item in db.scalars(select(models.Topic).where(models.Topic.subject_uid == subject.subject_uid)) if _name_key(item.name) == _name_key(topic_name)), None)
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
        existing_task = next((item for item in db.scalars(select(models.Task).where(models.Task.topic_uid == topic.topic_uid)) if _name_key(item.title) == _name_key(proposal.target_name)), None)
        if existing_task is not None:
            tasks.append(existing_task)
            reused_task = True
    for item in task_items:
        if reused_task:
            break
        duplicate = next((task for task in db.scalars(select(models.Task).where(models.Task.topic_uid == topic.topic_uid)) if _name_key(task.title) == _name_key(item.title)), None)
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
