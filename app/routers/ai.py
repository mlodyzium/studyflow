from datetime import date, datetime, timedelta, timezone
import json
import re
import unicodedata
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.ai import AiConversationRead, AiMaterialRead, FallbackPlanRequest, GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, ManualNoteRequest, MaterialApprovalRequest, NoteGenerationRequest, PlanGenerationRequest, SessionNoteGenerationRequest, T3achExecuteRequest, T3achExecuteResult, T3achPreviousProposal, T3achProposal, T3achRequest, T3achSpeechRequest, T3achTaskProposal
from app.schemas.study import StudySessionCreate
from app.services import ai as ai_service
from app.services import study
from app.services.names import normalize_name
from app.services import plans as plan_service
from app.core.config import settings
from app.core.traffic import check_limit

router = APIRouter(prefix="/ai", tags=["ai"])
WEEKDAYS_PL = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")


def _explicit_plan_preferences(message: str) -> tuple[int | None, int | None]:
    text = message.casefold()
    day = re.search(r"(?:plan\s+na\s+|przez\s+)(\d{1,2})\s*(?:dni|dnia|dzień)\b|\b(\d{1,2})\s*(?:dni|dnia|dzień)\s*(?:nauki|po\b)", text)
    minute = re.search(r"(?:po\s+)?(\d{1,3})\s*(?:minut|minuty|min|minute)\b(?:\s*(?:dziennie|każdego dnia))?", text)
    days = int(day.group(1) or day.group(2)) if day else None
    minutes = int(minute.group(1)) if minute else None
    return (days if days and 1 <= days <= 30 else None,
            minutes if minutes and 10 <= minutes <= 240 else None)


def _revision_changes_schedule(message: str) -> tuple[bool, bool]:
    text = message.casefold()
    days = bool(re.search(r"\b(?:dni|dnia|dzień|tydzień|tygodnie|tygodni|etap(?:y|ów)?|krócej|dłużej|skróć|wydłuż)\b", text))
    minutes = bool(re.search(r"\b(?:minut(?:y|ę|ami)?|min|godzin(?:y|ę)?|czasu|czas|krócej|dłużej|skróć|wydłuż)\b", text))
    return days, minutes


def _weekday_availability(message: str) -> tuple[set[int], set[int]]:
    blocked: set[int] = set()
    available: set[int] = set()
    names = (r"poniedzial\w*", r"wtor\w*", r"srod\w*", r"czwart\w*",
             r"piat\w*", r"sobot\w*", r"niedziel\w*")
    plain = "".join(char for char in unicodedata.normalize("NFKD", message.casefold()) if not unicodedata.combining(char)).replace("ł", "l")
    for clause in re.split(r"[,;.!?]|\b(?:ale|natomiast|za to)\b", plain):
        weekdays = {index for index, pattern in enumerate(names) if re.search(rf"\b{pattern}\b", clause)}
        if re.search(r"\bweekend\w*\b", clause):
            weekdays.update({5, 6})
        if not weekdays:
            continue
        if re.search(r"\b(?:nie\s+(?:moge|dam\s+rady|mam\s+czasu|ucze\s+sie|planuj)|bez|pomin|wyklucz|wolne\s+od\s+nauki)\b", clause):
            blocked.update(weekdays)
        elif re.search(r"\b(?:moge|dam\s+rade|mam\s+czas|dostepn\w*|pasuj\w*)\b", clause):
            available.update(weekdays)
    return blocked, available


def _exam_date_from_message(message: str, today: date) -> date | None:
    text = message.casefold()
    exam = r"(?:sprawdzian|egzamin|kolokwium|kartkówk)"
    relative = re.search(rf"{exam}.{{0,35}}?za\s+(\d{{1,2}})\s*(?:dni|dnia|dzień)\b|za\s+(\d{{1,2}})\s*(?:dni|dnia|dzień)\b.{{0,35}}?{exam}", text)
    if relative:
        return today + timedelta(days=int(relative.group(1) or relative.group(2)))
    exam_weekdays = ("poniedziałek", "wtorek", "środę", "czwartek", "piątek", "sobotę", "niedzielę")
    for index, weekday in enumerate(exam_weekdays):
        if re.search(rf"{exam}.{{0,35}}?\b(?:w|we)\s+{weekday}\b", text):
            days_ahead = (index - today.weekday()) % 7
            return today + timedelta(days=days_ahead)
    return None


def _limit_generation(user: models.User = Depends(get_current_user)):
    check_limit("ai", str(user.user_uid), settings.ai_rate_limit_per_day, 86400)


def _limit_speech(user: models.User = Depends(get_current_user)):
    check_limit("tts", str(user.user_uid), settings.tts_rate_limit_per_day, 86400)


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
    if proposal.intent == "study_help":
        return _clarify(proposal, proposal.reply)
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
    proposal.subject_name = _match_name(proposal.subject_name, (item.name for item in subjects)) or normalize_name(proposal.subject_name)
    if not proposal.topic_name:
        return _clarify(proposal, "Jakiego tematu z tego przedmiotu dotyczy ta prośba?")
    proposal.topic_name = _match_name(proposal.topic_name, (topic for subject, topic in topics if _name_key(subject) == _name_key(proposal.subject_name))) or normalize_name(proposal.topic_name)
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


@router.post("/t3ach/speech", dependencies=[Depends(_limit_speech)])
async def t3ach_speech(payload: T3achSpeechRequest, user: models.User = Depends(get_current_user)):
    audio = await ai_service.generate_t3ach_speech(payload.text)
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.post("/t3ach/propose", response_model=T3achProposal, dependencies=[Depends(_limit_generation)])
async def propose_t3ach_actions(payload: T3achRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    subjects = list(db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid).order_by(models.Subject.name)))
    local_today = datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone)).date()
    topics = list(db.execute(select(models.Subject.name, models.Topic.name).join(models.Topic).where(models.Subject.user_uid == user.user_uid)))
    tasks = list(db.execute(select(models.Subject.name, models.Topic.name, models.Task.title, models.Task.is_done, models.Task.deadline).join(models.Topic, models.Topic.subject_uid == models.Subject.subject_uid).join(models.Task, models.Task.topic_uid == models.Topic.topic_uid).where(models.Subject.user_uid == user.user_uid)))
    materials = list(db.execute(select(models.AiMaterial.material_type, models.AiMaterial.title, models.Task.title).outerjoin(models.Task, models.Task.task_uid == models.AiMaterial.task_uid).where(models.AiMaterial.user_uid == user.user_uid).order_by(models.AiMaterial.created_at.desc()).limit(30)))
    task_context = [f"{subject} — {topic} — {task} — {'ukończone' if done else 'aktywne'} — {deadline.isoformat() if deadline else 'bez terminu'}" for subject, topic, task, done, deadline in tasks]
    material_context = [f"{kind} — {title} — {task or 'bez zadania'}" for kind, title, task in materials]
    history = [item.model_dump() for item in payload.history[-8:]]
    previous = None
    previous_conversation = None
    if payload.previous_proposal_uid:
        previous_conversation = db.scalar(select(models.AiConversation).where(models.AiConversation.conversation_uid == payload.previous_proposal_uid, models.AiConversation.user_uid == user.user_uid).with_for_update())
        if previous_conversation is None:
            raise HTTPException(status_code=404, detail="Nie znaleziono poprzedniej propozycji.")
        if previous_conversation.proposal.get("_executed") or previous_conversation.proposal.get("_superseded_by"):
            raise HTTPException(status_code=409, detail="Poprzednia propozycja nie jest już aktualna.")
        previous_proposal = T3achProposal.model_validate(previous_conversation.proposal)
        original_request = previous_conversation.proposal.get("_original_request") or previous_conversation.user_message
        previous = T3achPreviousProposal(
            original_request=original_request,
            previous_answer=previous_conversation.assistant_message,
            previous_material=json.dumps(previous_proposal.preview, ensure_ascii=False)[:6000] if previous_proposal.preview else None,
            intent=previous_proposal.intent,
            subject_name=previous_proposal.subject_name,
            topic_name=previous_proposal.topic_name,
            target_name=previous_proposal.target_name,
            target_kind=previous_proposal.target_kind,
            difficulty=previous_proposal.difficulty,
            new_name=previous_proposal.new_name,
            new_priority=previous_proposal.new_priority,
            new_is_done=previous_proposal.new_is_done,
            material_types=previous_proposal.material_types,
            days=previous_proposal.days,
            minutes_per_day=previous_proposal.minutes_per_day,
            excluded_weekdays=previous_proposal.excluded_weekdays,
            exam_date=previous_proposal.exam_date,
            requested_plan_days=previous_proposal.requested_plan_days,
            plan_total_minutes=previous_proposal.plan_total_minutes,
            session_title=previous_proposal.session_title,
            session_duration_minutes=previous_proposal.session_duration_minutes,
            session_notes=previous_proposal.session_notes[:500] if previous_proposal.session_notes else None,
            tasks=[{"title": item.title, "priority": item.priority, "deadline_days": item.deadline_days, "notes": item.notes[:200] if item.notes else None} for item in previous_proposal.tasks],
        ).model_dump(exclude_none=True)
    proposal = await ai_service.generate_t3ach_proposal(payload.message, payload.language, [item.name for item in subjects], [f"{subject} — {topic}" for subject, topic in topics], task_context, material_context, history, previous,
                                                       local_today=local_today, subject_exams=[f"{item.name}: {item.exam_date.isoformat()}" for item in subjects if item.exam_date])
    if previous:
        if proposal.intent in {"edit", "study_help", "off_topic"} and previous["intent"] in {"organize", "study_plan", "notes", "session"}:
            proposal.intent = previous["intent"]
            proposal.needs_clarification = False
            proposal.question = None
        proposal.subject_name = proposal.subject_name or previous.get("subject_name")
        proposal.topic_name = proposal.topic_name or previous.get("topic_name")
        if previous["intent"] in {"notes", "study_plan"} and not re.search(r"\b(?:tylko|bez|zamiast)\b", payload.message.casefold()):
            proposal.material_types = list(dict.fromkeys([*previous.get("material_types", []), *proposal.material_types]))
            proposal.intent = "notes" if "notes" in proposal.material_types else "study_plan"
    proposal = _prepare_t3ach_proposal(proposal, subjects, topics, tasks)
    explicit_days, explicit_minutes = _explicit_plan_preferences(payload.message)
    changes_days, changes_minutes = _revision_changes_schedule(payload.message)
    if explicit_days is not None: proposal.days = explicit_days
    elif previous and not changes_days and previous.get("requested_plan_days"): proposal.days = previous["requested_plan_days"]
    if explicit_minutes is not None: proposal.minutes_per_day = explicit_minutes
    elif previous and not changes_minutes and previous.get("minutes_per_day"): proposal.minutes_per_day = previous["minutes_per_day"]
    blocked, available = _weekday_availability(payload.message)
    excluded_weekdays = set(proposal.excluded_weekdays) | set(previous.get("excluded_weekdays", []) if previous else [])
    proposal.excluded_weekdays = sorted((excluded_weekdays | blocked) - available)
    known_subject = next((item for item in subjects if proposal.subject_name and _name_key(item.name) == _name_key(proposal.subject_name)), None)
    if proposal.intent in {"notes", "study_plan"} and "plan" in proposal.material_types:
        proposal.exam_date = _exam_date_from_message(payload.message, local_today) or proposal.exam_date or (known_subject.exam_date if known_subject else None) or (previous.get("exam_date") if previous else None)
    proposal.plan_start_date = plan_service.start_date_for(user, payload.sent_at, proposal.minutes_per_day)
    material_goal = (f"Pierwotna prośba: {previous['original_request']}. "
                     f"Poprzedni materiał do poprawienia: {previous.get('previous_material') or 'brak'}. "
                     f"Najnowsza poprawka użytkownika ma pierwszeństwo: {payload.message}") if previous else payload.message
    if not proposal.needs_clarification and proposal.subject_name and proposal.topic_name:
        schedule = None
        if "plan" in proposal.material_types:
            requested_days = proposal.days
            schedule = plan_service.build_schedule(proposal.plan_start_date, requested_days, proposal.minutes_per_day, proposal.exam_date,
                                                   set(proposal.excluded_weekdays))
            proposal.days = schedule.days
            proposal.requested_plan_days = requested_days
            proposal.plan_total_minutes = schedule.total_minutes
            if schedule.adjustment:
                proposal.reply = f"{schedule.adjustment} {proposal.reply}"[:12000]
        if set(proposal.material_types) == {"notes", "plan"}:
            note = await ai_service.generate_topic_notes(proposal.subject_name, proposal.topic_name, proposal.difficulty, payload.language, "standard", material_goal)
            plan = await ai_service.generate_study_plan(proposal.subject_name, proposal.topic_name, proposal.difficulty, payload.language, proposal.days, proposal.minutes_per_day, material_goal,
                                                        start_date=proposal.plan_start_date, scheduled_dates=schedule.dates,
                                                        total_minutes=schedule.total_minutes, exam_review=schedule.exam_review)
            if previous_conversation and previous_conversation.proposal.get("preview"):
                plan_service.carry_over_excluded_activities(plan, previous_conversation.proposal["preview"], schedule,
                                                            set(proposal.excluded_weekdays))
            plan = plan_service.apply_schedule(plan, schedule)
            proposal.preview = {"notes": note.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}
        elif proposal.intent == "study_plan":
            preview = await ai_service.generate_study_plan(
                proposal.subject_name, proposal.topic_name, proposal.difficulty,
                payload.language, proposal.days, proposal.minutes_per_day, material_goal,
                start_date=proposal.plan_start_date, scheduled_dates=schedule.dates,
                total_minutes=schedule.total_minutes, exam_review=schedule.exam_review,
            )
            if previous_conversation and previous_conversation.proposal.get("preview"):
                plan_service.carry_over_excluded_activities(preview, previous_conversation.proposal["preview"], schedule,
                                                            set(proposal.excluded_weekdays))
            preview = plan_service.apply_schedule(preview, schedule)
            proposal.preview = preview.model_dump(mode="json")
        elif proposal.intent == "notes":
            preview = await ai_service.generate_topic_notes(
                proposal.subject_name, proposal.topic_name, proposal.difficulty,
                payload.language, "standard", material_goal,
            )
            proposal.preview = preview.model_dump(mode="json")
        if schedule:
            weekday = WEEKDAYS_PL[schedule.dates[0].weekday()]
            proposal.reply = (f"{proposal.reply.strip()} "
                              f"Plan zaczyna się {schedule.dates[0].isoformat()} ({weekday}), obejmuje {schedule.days} dostępnych dni i łącznie {schedule.total_minutes} minut. "
                              f"{schedule.adjustment or ''} Sprawdź podgląd i zatwierdź, jeśli Ci odpowiada.")[:12000].strip()
            proposal.question = None
    last_user_message = payload.message.strip()[:3000]
    conversation = models.AiConversation(user_uid=user.user_uid, title=last_user_message[:157] or "Rozmowa z T3ACH", user_message=last_user_message, assistant_message=(proposal.question or proposal.reply)[:4000], proposal={})
    db.add(conversation)
    db.flush()
    proposal.proposal_uid = conversation.conversation_uid
    conversation.proposal = {**proposal.model_dump(mode="json"), "_original_request": previous["original_request"] if previous else last_user_message}
    if previous_conversation is not None:
        previous_conversation.proposal = {**previous_conversation.proposal, "_superseded_by": str(conversation.conversation_uid)}
    db.commit()
    return proposal


@router.get("/t3ach/history", response_model=list[AiConversationRead])
def list_t3ach_history(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return list(db.scalars(select(models.AiConversation).where(models.AiConversation.user_uid == user.user_uid).order_by(models.AiConversation.created_at.desc())))


@router.delete("/t3ach/history/{conversation_uid}", status_code=204)
def delete_t3ach_history(conversation_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    value = db.scalar(select(models.AiConversation).where(models.AiConversation.conversation_uid == conversation_uid, models.AiConversation.user_uid == user.user_uid))
    if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono rozmowy.")
    db.delete(value); db.commit()


@router.post("/t3ach/execute", response_model=T3achExecuteResult)
async def execute_t3ach_actions(payload: T3achExecuteRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    conversation = db.scalar(select(models.AiConversation).where(models.AiConversation.conversation_uid == payload.proposal_uid, models.AiConversation.user_uid == user.user_uid).with_for_update())
    if conversation is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono propozycji.")
    if conversation.proposal.get("_executed"):
        raise HTTPException(status_code=409, detail="Ta propozycja została już zatwierdzona.")
    if conversation.proposal.get("_superseded_by"):
        raise HTTPException(status_code=409, detail="Ta propozycja została zastąpiona poprawioną wersją.")
    try:
        proposal = T3achProposal.model_validate(conversation.proposal)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Zapisana propozycja jest nieprawidłowa.") from exc
    conversation.proposal = {**conversation.proposal, "_executed": True}
    if proposal.needs_clarification:
        raise HTTPException(status_code=422, detail="Ta propozycja nie zawiera jeszcze działań do zapisania.")
    if proposal.intent == "session":
        if not proposal.subject_name or not proposal.session_title or not proposal.session_duration_minutes:
            raise HTTPException(status_code=422, detail="Brakuje danych sesji nauki.")
        subject = next((item for item in db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid)) if _name_key(item.name) == _name_key(proposal.subject_name)), None)
        created_subject = subject is None
        if subject is None:
            subject = models.Subject(name=normalize_name(proposal.subject_name), user_uid=user.user_uid, exam_date=proposal.exam_date)
            db.add(subject)
            db.flush()
        topic = next((item for item in db.scalars(select(models.Topic).where(models.Topic.subject_uid == subject.subject_uid)) if _name_key(item.name) == _name_key(proposal.topic_name)), None) if proposal.topic_name else None
        created_topic = topic is None and bool(proposal.topic_name)
        if created_topic:
            topic = models.Topic(name=normalize_name(proposal.topic_name), subject_uid=subject.subject_uid, difficulty=proposal.difficulty)
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
            if proposal.new_name: value.name = normalize_name(proposal.new_name)
            subject_uid = value.subject_uid
        elif proposal.target_kind == "topic":
            candidates = db.execute(select(models.Topic, models.Subject.name).join(models.Subject).where(models.Subject.user_uid == user.user_uid)).all()
            matches = [item for item, subject_name in candidates if _name_key(item.name) == name and (not proposal.subject_name or _name_key(subject_name) == _name_key(proposal.subject_name))]
            if len(matches) > 1: raise HTTPException(status_code=422, detail="Wiele tematów ma tę nazwę. Podaj przedmiot.")
            value = matches[0] if matches else None
            if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono wskazanego tematu.")
            if proposal.new_name: value.name = normalize_name(proposal.new_name)
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
    if proposal.intent not in {"organize", "study_plan", "notes"} or not proposal.subject_name or not proposal.topic_name or not proposal.tasks:
        raise HTTPException(status_code=422, detail="Ta propozycja nie zawiera jeszcze działań do zapisania.")
    subject_name = normalize_name(proposal.subject_name)
    topic_name = normalize_name(proposal.topic_name)
    subject = next((item for item in db.scalars(select(models.Subject).where(models.Subject.user_uid == user.user_uid)) if _name_key(item.name) == _name_key(subject_name)), None)
    created_subject = subject is None
    if subject is None:
        subject = models.Subject(name=subject_name, user_uid=user.user_uid, exam_date=proposal.exam_date)
        db.add(subject)
        db.flush()
    topic = next((item for item in db.scalars(select(models.Topic).where(models.Topic.subject_uid == subject.subject_uid)) if _name_key(item.name) == _name_key(topic_name)), None)
    created_topic = topic is None
    if topic is None:
        topic = models.Topic(name=topic_name, subject_uid=subject.subject_uid, difficulty=proposal.difficulty)
        db.add(topic)
        db.flush()
    now = datetime.now(timezone.utc)
    kinds = proposal.material_types or (["notes"] if proposal.intent == "notes" else ["plan"] if proposal.intent == "study_plan" else [])
    task_items = proposal.tasks if proposal.intent == "organize" else proposal.tasks[:1] if "notes" in kinds else []
    tasks = []
    reused_task = False
    if proposal.intent in {"study_plan", "notes"} and proposal.target_name and "notes" in kinds:
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
    if proposal.intent in {"study_plan", "notes"}:
        previews = proposal.preview or {}
        titles = []
        plan_uids = []
        for kind in kinds:
            preview = previews.get(kind) if "notes" in previews or "plan" in previews else proposal.preview
            if kind == "notes":
                try:
                    result = GeneratedNotes.model_validate(preview) if preview else await ai_service.generate_topic_notes(subject.name, topic.name, topic.difficulty, "polski", "standard", proposal.reply)
                except ValidationError as exc:
                    raise HTTPException(status_code=422, detail="Zapisana notatka jest nieprawidłowa.") from exc
                if not reused_task and tasks: tasks[0].title = result.task_title.strip()
                material = _save_material(db, user.user_uid, topic.topic_uid, tasks[0].task_uid if tasks else None, kind, result, commit=False)
                plan_service.create_review(db, user, material)
            else:
                start_date = proposal.plan_start_date or plan_service.start_date_for(user, None, proposal.minutes_per_day)
                schedule = plan_service.build_schedule(start_date, proposal.requested_plan_days or proposal.days, proposal.minutes_per_day,
                                                       proposal.exam_date, set(proposal.excluded_weekdays))
                try:
                    result = GeneratedStudyPlan.model_validate(preview) if preview else await ai_service.generate_study_plan(subject.name, topic.name, topic.difficulty, "polski", schedule.days, proposal.minutes_per_day, proposal.reply,
                                                                                                                          start_date=start_date, scheduled_dates=schedule.dates,
                                                                                                                          total_minutes=schedule.total_minutes, exam_review=schedule.exam_review)
                except ValidationError as exc:
                    raise HTTPException(status_code=422, detail="Zapisany plan jest nieprawidłowy.") from exc
                result = plan_service.apply_schedule(result, schedule)
                material = _save_material(db, user.user_uid, topic.topic_uid, tasks[0].task_uid if tasks else None, kind, result, commit=False)
                plan = plan_service.create_plan(db, user, topic.topic_uid, material.material_uid, result, proposal.minutes_per_day)
                result.plan_uid = plan.plan_uid
                material.content = result.model_dump(mode="json")
                plan_uids.append(plan.plan_uid)
            titles.append(f"{'notatkę' if kind == 'notes' else 'plan'} „{result.title}”")
        db.commit()
        message = f"Utworzono {' i '.join(titles)} w {subject.name} → {topic.name}."
        if "plan" in kinds: message += f" Dni planu są w kalendarzu od {schedule.dates[0].isoformat()}."
    else:
        db.commit()
        message = f"W {subject.name} → {topic.name} zapisano {len(tasks)} zadań: {', '.join(task.title for task in tasks)}."
    return T3achExecuteResult(message=message, subject_uid=subject.subject_uid, topic_uid=topic.topic_uid, task_uids=[task.task_uid for task in tasks], plan_uids=plan_uids if proposal.intent in {"study_plan", "notes"} else [], created_subject=created_subject, created_topic=created_topic)


@router.post("/session-note", response_model=GeneratedSessionNote, dependencies=[Depends(_limit_generation)])
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


def _save_material(db: Session, user_uid: UUID, topic_uid: UUID, task_uid: UUID | None, material_type: str, result, commit: bool = True):
    material = models.AiMaterial(user_uid=user_uid, topic_uid=topic_uid, task_uid=task_uid, material_type=material_type, title=result.title, content=result.model_dump(mode="json"))
    db.add(material)
    db.flush()
    if commit:
        db.commit()
    return material


@router.get("/materials", response_model=list[AiMaterialRead])
def list_materials(task_uid: UUID | None = Query(default=None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    query = select(models.AiMaterial).where(models.AiMaterial.user_uid == user.user_uid)
    if task_uid is not None:
        study.get_task(db, task_uid, user.user_uid)
        query = query.where(models.AiMaterial.task_uid == task_uid)
    return list(db.scalars(query.order_by(models.AiMaterial.created_at.desc())))


@router.delete("/materials/{material_uid}", status_code=204)
def delete_material(material_uid: UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    value = db.scalar(select(models.AiMaterial).where(models.AiMaterial.material_uid == material_uid, models.AiMaterial.user_uid == user.user_uid))
    if value is None: raise HTTPException(status_code=404, detail="Nie znaleziono materiału.")
    db.delete(value); db.commit()


@router.post("/topics/{topic_uid}/notes", response_model=GeneratedNotes, dependencies=[Depends(_limit_generation)])
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
    if payload.preview_only:
        return result
    task = _assign_task(db, topic_uid, selected_task, result)
    material = _save_material(db, user.user_uid, topic_uid, task.task_uid, "notes", result, commit=False)
    plan_service.create_review(db, user, material)
    db.commit()
    return result


@router.post("/topics/{topic_uid}/plan", response_model=GeneratedStudyPlan, dependencies=[Depends(_limit_generation)])
async def generate_plan(topic_uid: UUID, payload: PlanGenerationRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    selected_task, goal = _task_and_goal(payload, topic_uid, db, user)
    start_date = plan_service.start_date_for(user, payload.sent_at, payload.minutes_per_day)
    blocked, available = _weekday_availability(goal or "")
    schedule = plan_service.build_schedule(start_date, payload.days, payload.minutes_per_day, subject.exam_date, blocked - available)
    result = await ai_service.generate_study_plan(subject.name, topic.name, topic.difficulty, payload.language, schedule.days, payload.minutes_per_day, goal,
                                                  start_date=start_date, scheduled_dates=schedule.dates,
                                                  total_minutes=schedule.total_minutes, exam_review=schedule.exam_review)
    result = plan_service.apply_schedule(result, schedule)
    if payload.preview_only:
        return result
    material = _save_material(db, user.user_uid, topic_uid, selected_task.task_uid if selected_task else None, "plan", result, commit=False)
    plan = plan_service.create_plan(db, user, topic_uid, material.material_uid, result, payload.minutes_per_day)
    result.plan_uid = plan.plan_uid
    material.content = result.model_dump(mode="json")
    db.commit()
    return result


@router.post("/topics/{topic_uid}/materials/accept")
def accept_materials(topic_uid: UUID, payload: MaterialApprovalRequest,
                     db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    if payload.plan is not None:
        plan = payload.plan
        if plan.start_date is None or plan.plan_uid is not None:
            raise HTTPException(status_code=422, detail="Plan do zatwierdzenia ma nieprawidłową datę lub był już zapisany.")
        if {step.day for step in plan.steps} != set(range(1, len(plan.steps) + 1)):
            raise HTTPException(status_code=422, detail="Dni planu muszą być kolejne i nie mogą się powtarzać.")
        if subject.exam_date is not None:
            exam_step = next((step for step in plan.steps if (step.scheduled_date or plan.start_date + timedelta(days=step.day - 1)) == subject.exam_date), None)
            if exam_step is not None and exam_step.duration_minutes > 15:
                raise HTTPException(status_code=422, detail="W dniu sprawdzianu plan może zawierać najwyżej 15 minut powtórki.")
    note_uid = None
    plan_uid = None
    try:
        if payload.notes is not None:
            task = _assign_task(db, topic_uid, None, payload.notes)
            material = _save_material(db, user.user_uid, topic_uid, task.task_uid, "notes", payload.notes, commit=False)
            plan_service.create_review(db, user, material)
            note_uid = material.material_uid
        if payload.plan is not None:
            material = _save_material(db, user.user_uid, topic_uid, None, "plan", payload.plan, commit=False)
            saved_plan = plan_service.create_plan(db, user, topic_uid, material.material_uid, payload.plan, payload.minutes_per_day)
            payload.plan.plan_uid = saved_plan.plan_uid
            material.content = payload.plan.model_dump(mode="json")
            plan_uid = saved_plan.plan_uid
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"note_uid": note_uid, "plan_uid": plan_uid}


@router.post("/topics/{topic_uid}/manual-note", response_model=GeneratedNotes)
def create_manual_note(topic_uid: UUID, payload: ManualNoteRequest, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    study.get_topic(db, topic_uid, user.user_uid)
    result = GeneratedNotes(task_title=payload.title, title=payload.title,
                            summary="Notatka zapisana samodzielnie, bez użycia AI.",
                            sections=[{"heading": "Treść" if index == 0 else f"Treść — część {index + 1}", "content": payload.content[index * 4000:(index + 1) * 4000]}
                                      for index in range((len(payload.content) + 3999) // 4000)],
                            key_points=["Przeczytaj notatkę i sprawdź, co pamiętasz."], review_questions=[])
    task = _assign_task(db, topic_uid, None, result)
    material = _save_material(db, user.user_uid, topic_uid, task.task_uid, "notes", result, commit=False)
    plan_service.create_review(db, user, material)
    db.commit()
    return result


@router.post("/topics/{topic_uid}/fallback-plan", response_model=GeneratedStudyPlan)
def create_fallback_plan(topic_uid: UUID, payload: FallbackPlanRequest,
                         db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    topic = study.get_topic(db, topic_uid, user.user_uid)
    subject = study.get_subject(db, topic.subject_uid, user.user_uid)
    start_date = plan_service.start_date_for(user, payload.sent_at, payload.minutes_per_day)
    blocked, available = _weekday_availability(payload.goal)
    schedule = plan_service.build_schedule(start_date, payload.days, payload.minutes_per_day, subject.exam_date, blocked - available)
    result = GeneratedStudyPlan(
        task_title=f"Nauka: {topic.name}", title=f"Plan nauki: {topic.name}",
        overview=f"Cel: {payload.goal}. Plan przygotowano bez AI; uzupełnij etapy o własne materiały i ćwiczenia.",
        steps=[{"day": number, "title": f"Etap {number}: {topic.name}",
                "objective": "Przećwicz temat i zanotuj, co wymaga powtórki.",
                "activities": ["Przeczytaj dostępne materiały.", "Rozwiąż własne przykłady lub zadania.",
                               "Zapisz pytania i trudności."], "duration_minutes": payload.minutes_per_day}
               for number in range(1, schedule.days + 1)],
        success_criteria=["Potrafię wyjaśnić temat własnymi słowami."])
    result = plan_service.apply_schedule(result, schedule)
    material = _save_material(db, user.user_uid, topic_uid, None, "plan", result, commit=False)
    plan = plan_service.create_plan(db, user, topic_uid, material.material_uid, result, payload.minutes_per_day)
    result.plan_uid = plan.plan_uid
    material.content = result.model_dump(mode="json")
    db.commit()
    return result
