import asyncio
import base64
import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings
from pydantic import BaseModel

from app.schemas.ai import GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, T3achProposal

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def generate_t3ach_speech(text: str) -> bytes:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Głos T3ACH nie jest skonfigurowany.")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text, "speech_metadata": {"style": "Speak in Polish naturally, warmly and conversationally, like a patient tutor."}}]}],
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
        return audio
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Gemini speech generation failed: %s status=%s", type(exc).__name__, response.status_code if "response" in locals() else "none")
        detail = "Nie udało się wygenerować głosu T3ACH. Sprawdź dostęp do modelu Gemini TTS i spróbuj ponownie."
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (400, 404):
            detail = f"Model głosu {settings.gemini_tts_model} nie jest dostępny dla tego klucza Gemini."
        raise HTTPException(status_code=502, detail=detail) from exc


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
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
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


async def generate_t3ach_proposal(message: str, language: str, subjects: list[str], topics: list[str], tasks: list[str], materials: list[str]) -> T3achProposal:
    prompt = (
        "Jesteś T3ACH, konkretnym i życzliwym cyfrowym mentorem w aplikacji StudyFlow. Dopasuj język, ton i poziom formalności do wiadomości użytkownika. "
        "Pomagasz w nauce oraz organizacji nauki. Zawsze zwróć krótką, sensowną odpowiedź. "
        f"Odpowiadaj w języku: {language}. Wiadomość lub kontekst rozmowy: {message}. "
        f"Istniejące przedmioty użytkownika: {subjects or ['brak']}. "
        f"Istniejące tematy zapisane jako 'przedmiot — temat': {topics or ['brak']}. "
        f"Istniejące zadania zapisane jako 'przedmiot — temat — zadanie — status — termin': {tasks or ['brak']}. "
        f"Istniejące materiały AI zapisane jako 'typ — tytuł — zadanie': {materials or ['brak']}. "
        "Rozpoznaj intencję: organize oznacza zadania lub uporządkowanie celu, study_plan oznacza plan nauki na kilka dni, notes oznacza notatkę, session oznacza pojedynczą sesję nauki, edit oznacza zmianę istniejących danych, study_help oznacza pytanie o wiedzę bez prośby o zapis, off_topic oznacza sprawę niezwiązaną z nauką. "
        "Jeśli ostatnia wypowiedź nie dotyczy nauki, wybierz off_topic i poproś o powtórzenie prośby dotyczącej nauki. Nie twórz przedmiotu, tematu, zadań ani planu. Jeśli to pytanie edukacyjne, odpowiedz krótko merytorycznie i wybierz study_help. "
        "Jeśli użytkownik prosi o działanie, ale brakuje przedmiotu, tematu lub informacji pozwalającej je ustalić, ustaw needs_clarification=true i zadaj jedno konkretne pytanie. Nie wymyślaj brakujących danych. "
        "Jeżeli użytkownik prosi o sesję nauki, wybierz session. Ustaw session_title, session_duration_minutes i session_notes z krótkim przebiegiem nauki na podstawie jego celu. Nie traktuj planowanej sesji jako już odbytej. Dla session nie dodawaj zadań. "
        "Jeśli użytkownik prosi o plan, ZAWSZE wybierz study_plan i nie rozbijaj go na osobne zadania. Jeśli prosi o notatkę, wybierz notes. "
        "Dla edit ustaw target_kind jako jedno z angielskich słów subject, topic, task, dokładną istniejącą target_name i tylko potrzebne nowe wartości. Dla pozostałych intencji target_kind ma być null. Nie proponuj usuwania danych. "
        "ZAWSZE wykorzystuj istniejący przedmiot, temat lub zadanie, jeśli pasuje znaczeniem do prośby; zachowaj wtedy jego nazwę dokładnie znak w znak. Nie twórz duplikatów. "
        "Dla notes i study_plan wpisz w target_name dokładną nazwę najlepiej pasującego istniejącego zadania. Jeśli żadne nie pasuje, target_name ma być null i zaproponuj dokładnie jedno nowe zadanie jako kontener materiału. "
        "Dla organize przygotuj od 1 do 6 realnych zadań, pomijając zadania już istniejące. Dla study_plan lub notes przygotuj dokładnie jedno zadanie. deadline_days oznacza liczbę dni od dziś; użyj null bez terminu. "
        "Uwzględniaj statusy, terminy i istniejące materiały: nie proponuj ponownie ukończonej pracy ani identycznego materiału. W reply wyjaśnij, do jakich istniejących danych podepniesz wynik. "
        "Priorytet musi być LOW, MEDIUM albo HIGH. "
        "Jeżeli brakuje kluczowej informacji, ustaw needs_clarification=true, zadaj jedno krótkie pytanie i pozostaw subject_name, topic_name oraz tasks puste. "
        "W reply krótko wyjaśnij, co proponujesz. Nie twierdź, że cokolwiek zostało już zapisane. Wszystkie nazwy pól i wartości enum zwracaj zgodnie ze schematem JSON, nawet gdy odpowiadasz po polsku."
    )
    try:
        return await _generate_structured(prompt, T3achProposal)
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        logger.warning("T3ACH proposal failed; returning clarification")
        return T3achProposal(reply="Nie udało mi się zrozumieć tej prośby. Powiedz proszę jeszcze raz, czego chcesz się nauczyć lub co mam zaplanować.", needs_clarification=True, question="Nie udało mi się zrozumieć tej prośby. Powiedz proszę jeszcze raz, czego chcesz się nauczyć lub co mam zaplanować.")
