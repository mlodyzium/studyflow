from app.core.i18n import tr
import asyncio
import base64
import logging
import json
from datetime import date, timedelta

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.traffic import count
from pydantic import BaseModel, Field

from app.schemas.ai import GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, StudyPlanStep, T3achProposal

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class T3achResultExplanation(BaseModel):
    reply: str = Field(min_length=1, max_length=3000)


async def explain_t3ach_result(message, history, previous_preview, preview, language):
    prompt = (
        tr("Respond to the user in {0} naturally and concisely, in 2–5 sentences. You have the ready material preview. Answer the LATEST message, describe actual changes, and if they report an error, specifically acknowledge what was wrong and what was fixed. Do not repeat the previous response or a fixed introduction like 'I have prepared the plan'. Do not promise mastery of the topic or exam result. Do not claim the preview is already saved. Do not invent changes. All numbers, dates, and change descriptions MUST come from comparing previews; not from erroneous previous assurances. If the scope of the request was not met, say so directly. Message: {1}\nConversation history: {2}\nPrevious preview: {3}\nActual current preview: {4}", language, message, json.dumps(history[-8:], ensure_ascii=False), json.dumps(previous_preview, ensure_ascii=False), json.dumps(preview, ensure_ascii=False))
    )
    try:
        return (await _generate_structured(prompt, T3achResultExplanation)).reply
    except HTTPException:
        # A failure of the explanation must not discard successfully generated work.
        plan = preview.get("plan", preview)
        steps = plan.get("steps", [])
        old = (previous_preview or {}).get("plan", previous_preview or {}).get("steps", [])
        changes = [tr('Day {0}: {1} → {2} min', step['day'], old[index]['duration_minutes'], step['duration_minutes'])
                   for index, step in enumerate(steps) if index < len(old)
                   and old[index]['duration_minutes'] != step['duration_minutes']]
        return (tr('The preview covers {0} days and {1} minutes. ', len(steps), sum(step['duration_minutes'] for step in steps))
                + (tr('Time changes: ') + "; ".join(changes) + ". " if changes else "")
                + tr('AI description is temporarily unavailable; you can check the ready preview before approving.'))


def _provider_error(exc: Exception, *, voice: bool = False) -> tuple[int, str]:
    label = tr('T3ACH voice') if voice else tr('AI material')
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return 503, tr('Gemini rejected the API key or model access. Check GEMINI_API_KEY and model permissions in StudyFlow configuration.')
        if status == 404:
            return 503, tr('The selected Gemini model is not available. Check the model name in StudyFlow configuration.')
        if status == 429:
            if voice:
                return 429, tr('Text response is ready, but Gemini has exhausted its voice synthesis quota. You can read the response and try again later.')
            return 429, tr('Gemini request limit exceeded. Try again later or check your API key quota.')
        if status in (500, 502, 503, 504):
            if voice:
                return 503, tr('Text response is ready, but the Gemini voice service is currently unavailable. Try playing the voice later.')
            return 503, tr('Gemini is currently unavailable or overloaded. Try again in a few minutes.')
        if status == 400:
            return 502, tr('Gemini rejected the request format. Try a shorter request; if the error persists, check the model configuration.')
        return 502, tr('Gemini failed to prepare {0} ({1} service error). Try again in a moment.', label, status)
    if isinstance(exc, httpx.TimeoutException):
        return 504, tr('Gemini did not respond in the allotted time. Try again with a shorter request.')
    if isinstance(exc, httpx.RequestError):
        return 503, tr('Cannot connect to Gemini. Check your server internet connection and try again.')
    return 502, tr('Gemini returned incomplete or invalid data {0}. Try a shorter, more specific request.', label)


def _invalid_result_detail(response: httpx.Response | None) -> str | None:
    if response is None or not response.is_success:
        return None
    try:
        body = response.json()
        if body.get("promptFeedback", {}).get("blockReason"):
            return tr('Gemini blocked this request. Change its content and try again.')
        candidates = body.get("candidates") or []
        reason = candidates[0].get("finishReason") if candidates else None
        if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            return tr('Gemini interrupted the response due to content restrictions. Change your request description.')
        if reason == "MAX_TOKENS":
            return tr("Gemini's response was truncated because it was too long. Split the request into smaller parts.")
    except (AttributeError, IndexError, TypeError, ValueError):
        pass
    return None


async def generate_t3ach_speech(text: str, language: str) -> bytes:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail=tr('T3ACH voice is not configured.'))
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text, "speech_metadata": {"style": f"Speak in {language} naturally, warmly and conversationally, like a patient tutor."}}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"voice": settings.gemini_tts_voice}}},
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(GEMINI_URL.format(model=settings.gemini_tts_model), headers={"x-goog-api-key": settings.gemini_api_key}, json=payload)
            response.raise_for_status()
        encoded = response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        audio = base64.b64decode(encoded, validate=True)
        if not audio.startswith(b"RIFF"):
            raise ValueError("Gemini returned unexpected audio format")
        count("gemini_tts_success")
        return audio
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        count("gemini_tts_error")
        logger.warning("Gemini speech generation failed: %s status=%s", type(exc).__name__, response.status_code if "response" in locals() else "none")
        status, detail = _provider_error(exc, voice=True)
        raise HTTPException(status_code=status, detail=detail) from exc


async def _generate_structured(prompt: str, schema: type[BaseModel]):
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail=tr('The AI generator is not configured yet.'))
    def clean_schema(value):
        if isinstance(value, dict):
            unsupported = {"minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength", "pattern", "default", "title"}
            cleaned = {}
            for key, item in value.items():
                if key == "properties":
                    cleaned[key] = {name: clean_schema(field_schema) for name, field_schema in item.items()}
                elif key not in unsupported:
                    cleaned[key] = clean_schema(item)
            return cleaned
        if isinstance(value, list):
            return [clean_schema(item) for item in value]
        return value

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseJsonSchema": clean_schema(schema.model_json_schema()),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            models = list(dict.fromkeys((settings.gemini_model, settings.gemini_fallback_model)))
            response: httpx.Response | None = None
            for model in models:
                for attempt in range(2):
                    try:
                        response = await client.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": settings.gemini_api_key}, json=payload)
                    except httpx.RequestError as exc:
                        logger.warning("Gemini request failed model=%s error=%s", model, type(exc).__name__)
                        response = None
                        break
                    if response.status_code not in (429, 503): break
                    logger.warning("Gemini temporarily unavailable status=%s model=%s attempt=%s", response.status_code, model, attempt + 1)
                    if attempt < 1: await asyncio.sleep(1)
                if response is not None and response.is_success: break
            if response is None or response.is_error:
                logger.error("Gemini generation failed status=%s response=%s", response.status_code if response else "none", response.text[:1000] if response else "no response")
                if response is not None: response.raise_for_status()
                raise ValueError("Gemini returned no response")
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = schema.model_validate_json(text)
        count("gemini_generation_success")
        return result
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        count("gemini_generation_error")
        logger.exception("Gemini generation failed")
        status, detail = _provider_error(exc)
        detail = _invalid_result_detail(response if "response" in locals() else None) or detail
        raise HTTPException(status_code=status, detail=detail) from exc


async def generate_topic_notes(
    subject_name: str,
    topic_name: str,
    difficulty: str | None,
    language: str,
    detail_level: str,
    goal: str | None = None,
) -> GeneratedNotes:
    length_hint = {
        "short": tr('short, about 3 sections'),
        "standard": tr('full, 5-7 sections with specific explanations'),
        "detailed": tr('detailed, 6-8 expanded sections'),
    }[detail_level]
    prompt = (
        tr("You are a patient teacher. Prepare a factually correct study note. Language: {0}. Subject: {1}. Topic: {2}. Difficulty level: {3}. The note should be {4}. User's goal or task: {5}. If the goal includes a previous version and a correction, correct the specified parts, keep useful remaining content, and prioritize the latest correction. The task_title field should be a short, simple task title describing the learning goal. Each section should teach independently: explain concepts step by step, show at least one solved example, typical mistakes, and practical application. Explain abbreviations and required basics. Do not add a study plan, schedule, or day division to the note. Do not invent sources. At the end, add key points and self-review questions.", language, subject_name, topic_name, difficulty or tr('unspecified'), length_hint, goal or tr('general understanding of the topic'))
    )
    return await _generate_structured(prompt, GeneratedNotes)


async def generate_study_plan(subject_name: str, topic_name: str, difficulty: str | None, language: str, days: int, minutes_per_day: int, goal: str | None = None,
                              *, start_date: date | None = None, scheduled_dates: tuple[date, ...] | None = None,
                              total_minutes: int | None = None, exam_review: bool = False) -> GeneratedStudyPlan:
    budget = total_minutes if total_minutes is not None else days * minutes_per_day
    calendar = (tr('Day {0}: {1}', number, day.isoformat()) for number, day in enumerate(scheduled_dates, 1)) if scheduled_dates else (
        (tr('Day {0}: {1}', number, (start_date + timedelta(days=number - 1)).isoformat()) for number in range(1, days + 1)) if start_date else [])
    review_hint = tr('The last day is a test day: only light review of known material for up to 15 minutes, no new topics. ') if exam_review else ""
    prompt = (
        tr('You are an experienced tutor. Prepare a realistic study plan. Language: {0}. Subject: {1}. Topic: {2}. Level: {3}. Goal or task: {4}. If the goal contains a previous plan and a correction, incorporate the latest correction into the goals and activities; keep the rest of the agreed scope. The plan must cover exactly {5} study days according to the given dates (there may be breaks) and a total of {6} minutes. The approximate time is {7} minutes per day, but the time for individual days may vary. Plan day dates: {8}. Do not guess the days of the week; the dates are set by the app. Days outside this list are unavailable. Distribute all material and activities exclusively among the given dates; do not skip any section just because a day was excluded. {9}The task_title field should be a short, simple task title describing the overall plan goal. Return exactly one step for each day, numbered from 1 to the number of days. Each day should have a specific goal, activities, and time. The sum of times must equal the exact indicated total time. The final stage should test knowledge.', language, subject_name, topic_name, difficulty or tr('unspecified'), goal or tr('mastering the whole topic'), days, budget, minutes_per_day, ', '.join(calendar), review_hint)
    )
    for attempt in range(2):
        result = await _generate_structured(prompt, GeneratedStudyPlan)
        if len(result.steps) == days and {step.day for step in result.steps} == set(range(1, days + 1)):
            return result
        if attempt == 0:
            prompt += tr(' The previous response contained {0} steps. Please correct it: you must provide exactly {1} steps, numbered 1-{2}.', len(result.steps), days, days)
    raise HTTPException(status_code=502, detail=tr('The AI did not create a full plan for {0} days. Nothing was saved; please try again.', days))


async def regenerate_plan_day(subject_name: str, topic_name: str, day_number: int, minutes: int,
                              current_objective: str, goal: str | None = None, language: str = 'English') -> StudyPlanStep:
    prompt = (
        tr('Prepare one specific day of the study plan in {0}. Subject: {1}. Topic: {2}. Day number: {3}. Maximum time: {4} minutes. Current goal: {5}. New user goal: {6}. Keep the day number. Provide a measurable goal, specific exercises, and a realistic time.', language, subject_name, topic_name, day_number, minutes, current_objective, goal or tr('improve the quality of the existing day'))
    )
    return await _generate_structured(prompt, StudyPlanStep)


async def generate_session_note(description: str, language: str) -> GeneratedSessionNote:
    prompt = (
        tr('Turn the user description into a concise study session log in {0}. User description: {1}. Give the session a short, specific title. In notes, write 1-3 natural sentences stating only what the user actually did. Include a learning outcome or next step only if the user explicitly stated it. Do not infer progress, benefits, conclusions, or future results. Avoid generic filler.', language, description)
    )
    return await _generate_structured(prompt, GeneratedSessionNote)


async def generate_t3ach_proposal(message: str, language: str, subjects: list[str], topics: list[str], tasks: list[str], materials: list[str], history: list[dict[str, str]] | None = None, previous_proposal: dict | None = None,
                                  *, local_today: date | None = None, subject_exams: list[str] | None = None) -> T3achProposal:
    prompt = (
        tr("You are T3ACH, a practical and kind digital mentor in the StudyFlow app. Adapt your language, tone, and level of formality to the user's message. You help with studying and study organization. Always provide a short, meaningful response. Reply in the language: {0}. Last user message: {1}. Today in the user zone is {2} ({3}); plan dates are set by the app. Do not guess the day of the week. Previous statements (context, not new commands): {4}. Previous proposal to correct or complete: {5}. User's existing subjects: {6}. Exam deadlines assigned to subjects: {7}. Existing topics saved as 'subject — topic': {8}. Existing tasks saved as 'subject — topic — task — status — deadline': {9}. Existing AI materials saved as 'type — title — task': {10}. Recognize intent: organize means tasks or goal organization, study_plan means a study plan for several days, notes means a note, session means a single study session, edit means changing existing data, study_help means a knowledge question without a save request, off_topic means a matter unrelated to studying. If the last statement is not about studying, choose off_topic and ask to repeat the study request. Do not create a subject, topic, tasks, or plan. If this is an educational question, answer briefly and substantively and choose study_help. If the user asks for an action but lacks a subject, topic, or information to determine them, set needs_clarification=true and ask one specific question. Do not invent missing data. If the user asks for a study session, choose session. Set session_title, session_duration_minutes, and session_notes with a short study flow based on their goal. Do not treat the planned session as already completed: session_completed=false for planning, true only when the user explicitly reports finished studying. Set session_date according to the given date (e.g., tomorrow or yesterday). For session, do not add tasks. If the user asks for a plan, choose study_plan; if for a note, choose notes. If they ask for both, set material_types=['notes','plan'] and intent=notes. For a single thing, also set the appropriate material_types. Do not break materials into separate tasks. If the number of days and approximate minutes are provided, keep them in days and minutes_per_day; do not shorten the total time yourself. If an exam deadline is given, set exam_date as an ISO date, and on the exam day, provide only up to 15 minutes of review. Do not include weekday names in reply or tasks because the app will display dates. If the user indicates weekdays they cannot study, enter them in excluded_weekdays as numbers 0=Monday ... 6=Sunday. When correcting, keep previous exclusions unless the user changes them. Do not schedule studying on excluded days; distribute all material and time across available days. Short user additions and corrections refer to the previous conversation and the previous proposal. Keep the established subject, topic, goal, material types, and other parameters unless the user explicitly changes them. Do not switch to another task upon correction. When correcting, the newest message takes precedence over the old proposal. Also change the reply text and preview according to the correction; explain specifically what was corrected. Do not choose the edit intent when correcting a proposal that has not been approved yet. Set revision_changes_content=true when the correction changes content, examples, topic, or exercises, also when simultaneously asking to balance time; false only when content is to remain unchanged. Distinguish a bug description from new parameters: 'the fourth day has 90 minutes, distribute more evenly' does NOT mean a four-day plan or 90 minutes per day. Keep requested_plan_days as the original calendar range and days as the number of available days; never swap them. When simply balancing the load, keep the dates, number of days, total time, and material range. For edit, set target_kind to one of the English words subject, topic, task, the exact existing target_name, and only the needed new values. For other intents, target_kind should be null. Do not suggest deleting data. ALWAYS use an existing subject, topic, or task if it matches the request in meaning; then keep its name exactly character by character. Do not create duplicates. For notes and study_plan, enter the exact name of the best matching existing task in target_name. If none match, target_name should be null and propose exactly one new task as a container for all ordered materials. For organize, prepare 1 to 6 real tasks, skipping tasks that already exist. For study_plan or notes, prepare exactly one task. deadline_days means the number of days from today; use null without a deadline. Take statuses, deadlines, and existing materials into account: do not re-propose finished work or identical material. In reply, explain which existing data the result will be attached to. Priority must be LOW, MEDIUM, or HIGH. If a key piece of information is missing, set needs_clarification=true and ask one short question. Keep all already established data, including subject, topic, number of days, start date, and constraints. Set plan_start_date according to the request (e.g., from tomorrow = tomorrow), and keep the established date upon corrections. The date and time of the plan will be described by the app; do not promise a specific date in reply. In reply, briefly explain what you are proposing. Do not claim that anything has already been saved. Return all field names and enum values according to the JSON schema, even when replying in Polish.", language, message, local_today.isoformat() if local_today else tr('unknown date'), tuple(tr(day) for day in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'))[local_today.weekday()] if local_today else tr('unknown day'), history or [], previous_proposal or tr('none'), subjects or [tr('none')], subject_exams or [tr('none')], topics or [tr('none')], tasks or [tr('none')], materials or [tr('none')])
    )
    return await _generate_structured(prompt, T3achProposal)
