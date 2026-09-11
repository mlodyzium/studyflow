import asyncio
import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings
from pydantic import BaseModel

from app.schemas.ai import GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def _generate_structured(prompt: str, schema: type[BaseModel]):
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Generator AI nie jest jeszcze skonfigurowany.")
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
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseJsonSchema": clean_schema(schema.model_json_schema()),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        return schema.model_validate_json(text)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.exception("Gemini generation failed")
        raise HTTPException(status_code=502, detail="Nie udało się wygenerować materiału. Spróbuj ponownie za chwilę.") from exc


async def generate_topic_notes(
    subject_name: str,
    topic_name: str,
    difficulty: str | None,
    language: str,
    detail_level: str,
    goal: str | None = None,
) -> GeneratedNotes:
    length_hint = {
        "short": "krótka, około 3 sekcje",
        "standard": "konkretna, około 4-5 sekcji",
        "detailed": "szczegółowa, około 6-8 sekcji",
    }[detail_level]
    prompt = (
        "Jesteś cierpliwym nauczycielem. Przygotuj poprawną merytorycznie notatkę do nauki. "
        f"Język: {language}. Przedmiot: {subject_name}. Temat: {topic_name}. "
        f"Poziom trudności: {difficulty or 'nieokreślony'}. Notatka ma być {length_hint}. "
        f"Cel lub zadanie użytkownika: {goal or 'ogólne opanowanie tematu'}. "
        "Pole task_title ma być krótkim, prostym tytułem zadania opisującym cel nauki. "
        "Wyjaśniaj jasno, używaj przykładów tam, gdzie pomagają, i nie wymyślaj źródeł. "
        "Na końcu dodaj najważniejsze punkty oraz pytania do samodzielnej powtórki."
    )
    return await _generate_structured(prompt, GeneratedNotes)


async def generate_study_plan(subject_name: str, topic_name: str, difficulty: str | None, language: str, days: int, minutes_per_day: int, goal: str | None = None) -> GeneratedStudyPlan:
    prompt = (
        "Jesteś doświadczonym korepetytorem. Przygotuj realistyczny plan nauki. "
        f"Język: {language}. Przedmiot: {subject_name}. Temat: {topic_name}. "
        f"Poziom: {difficulty or 'nieokreślony'}. Cel lub zadanie: {goal or 'opanowanie całego tematu'}. "
        f"Plan ma obejmować {days} dni, maksymalnie {minutes_per_day} minut dziennie. "
        "Pole task_title ma być krótkim, prostym tytułem zadania opisującym cały cel planu. "
        "Każdy dzień powinien mieć konkretny cel, aktywności i czas. Ostatni etap powinien sprawdzać wiedzę."
    )
    return await _generate_structured(prompt, GeneratedStudyPlan)


async def generate_session_note(description: str, language: str) -> GeneratedSessionNote:
    prompt = (
        "Uporządkuj krótki opis wykonanej nauki jako zwięzły zapis sesji. "
        f"Język: {language}. Opis użytkownika: {description}. "
        "Nadaj sesji krótki, konkretny tytuł. W polu notes napisz 2-5 zdań: "
        "co zostało zrobione, czego się nauczono i — tylko jeśli wynika to z opisu — co warto zrobić dalej. "
        "Nie dopisuj faktów, których użytkownik nie podał."
    )
    return await _generate_structured(prompt, GeneratedSessionNote)
