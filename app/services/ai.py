import asyncio
import base64
import logging
from datetime import date, timedelta

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.traffic import count
from pydantic import BaseModel

from app.schemas.ai import GeneratedNotes, GeneratedSessionNote, GeneratedStudyPlan, StudyPlanStep, T3achProposal

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _provider_error(exc: Exception, *, voice: bool = False) -> tuple[int, str]:
    label = "głosu T3ACH" if voice else "materiału AI"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return 503, "Gemini odrzucił klucz API lub dostęp do modelu. Sprawdź GEMINI_API_KEY i uprawnienia modelu w konfiguracji StudyFlow."
        if status == 404:
            return 503, "Wybrany model Gemini nie jest dostępny. Sprawdź nazwę modelu w konfiguracji StudyFlow."
        if status == 429:
            if voice:
                return 429, "Odpowiedź tekstowa jest gotowa, ale Gemini wyczerpał limit syntezy głosu. Możesz przeczytać odpowiedź i spróbować ponownie później."
            return 429, "Wyczerpał się limit zapytań Gemini. Spróbuj później lub sprawdź limit klucza API."
        if status in (500, 502, 503, 504):
            if voice:
                return 503, "Odpowiedź tekstowa jest gotowa, ale usługa głosu Gemini jest teraz niedostępna. Spróbuj odtworzyć głos później."
            return 503, "Gemini jest teraz niedostępny lub przeciążony. Spróbuj ponownie za kilka minut."
        if status == 400:
            return 502, "Gemini odrzucił format zapytania. Spróbuj krótszej prośby; jeśli błąd się powtarza, sprawdź konfigurację modelu."
        return 502, f"Gemini nie przygotował {label} (błąd usługi {status}). Spróbuj ponownie za chwilę."
    if isinstance(exc, httpx.TimeoutException):
        return 504, "Gemini nie odpowiedział w wyznaczonym czasie. Spróbuj ponownie z krótszą prośbą."
    if isinstance(exc, httpx.RequestError):
        return 503, "Nie można połączyć się z Gemini. Sprawdź połączenie serwera z internetem i spróbuj ponownie."
    return 502, f"Gemini zwrócił niepełne lub nieprawidłowe dane {label}. Spróbuj krótszej, bardziej konkretnej prośby."


def _invalid_result_detail(response: httpx.Response | None) -> str | None:
    if response is None or not response.is_success:
        return None
    try:
        body = response.json()
        if body.get("promptFeedback", {}).get("blockReason"):
            return "Gemini zablokował tę prośbę. Zmień jej treść i spróbuj ponownie."
        candidates = body.get("candidates") or []
        reason = candidates[0].get("finishReason") if candidates else None
        if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            return "Gemini przerwał odpowiedź z powodu ograniczeń treści. Zmień opis prośby."
        if reason == "MAX_TOKENS":
            return "Odpowiedź Gemini została ucięta, bo była zbyt długa. Podziel prośbę na mniejsze części."
    except (AttributeError, IndexError, TypeError, ValueError):
        pass
    return None


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
        count("gemini_tts_success")
        return audio
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        count("gemini_tts_error")
        logger.warning("Gemini speech generation failed: %s status=%s", type(exc).__name__, response.status_code if "response" in locals() else "none")
        status, detail = _provider_error(exc, voice=True)
        raise HTTPException(status_code=status, detail=detail) from exc


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
        "short": "krótka, około 3 sekcje",
        "standard": "pełna, 5-7 sekcji z konkretnymi wyjaśnieniami",
        "detailed": "szczegółowa, 6-8 rozbudowanych sekcji",
    }[detail_level]
    prompt = (
        "Jesteś cierpliwym nauczycielem. Przygotuj poprawną merytorycznie notatkę do nauki. "
        f"Język: {language}. Przedmiot: {subject_name}. Temat: {topic_name}. "
        f"Poziom trudności: {difficulty or 'nieokreślony'}. Notatka ma być {length_hint}. "
        f"Cel lub zadanie użytkownika: {goal or 'ogólne opanowanie tematu'}. "
        "Jeżeli cel zawiera poprzednią wersję i poprawkę, popraw wskazane fragmenty, zachowaj przydatne pozostałe treści i nadaj pierwszeństwo najnowszej poprawce. "
        "Pole task_title ma być krótkim, prostym tytułem zadania opisującym cel nauki. "
        "Każda sekcja powinna samodzielnie uczyć: wyjaśnij pojęcia krok po kroku, pokaż co najmniej jeden rozwiązany przykład, "
        "typowe błędy i praktyczne zastosowanie. Wyjaśnij skróty i wymagane podstawy. "
        "Nie dodawaj planu nauki, harmonogramu ani podziału na dni do notatki. Nie wymyślaj źródeł. "
        "Na końcu dodaj najważniejsze punkty oraz pytania do samodzielnej powtórki."
    )
    return await _generate_structured(prompt, GeneratedNotes)


async def generate_study_plan(subject_name: str, topic_name: str, difficulty: str | None, language: str, days: int, minutes_per_day: int, goal: str | None = None,
                              *, start_date: date | None = None, scheduled_dates: tuple[date, ...] | None = None,
                              total_minutes: int | None = None, exam_review: bool = False) -> GeneratedStudyPlan:
    budget = total_minutes if total_minutes is not None else days * minutes_per_day
    calendar = (f"Dzień {number}: {day.isoformat()}" for number, day in enumerate(scheduled_dates, 1)) if scheduled_dates else (
        (f"Dzień {number}: {(start_date + timedelta(days=number - 1)).isoformat()}" for number in range(1, days + 1)) if start_date else [])
    review_hint = "Ostatni dzień jest dniem sprawdzianu: tylko lekka powtórka znanego materiału do 15 minut, bez nowych zagadnień. " if exam_review else ""
    prompt = (
        "Jesteś doświadczonym korepetytorem. Przygotuj realistyczny plan nauki. "
        f"Język: {language}. Przedmiot: {subject_name}. Temat: {topic_name}. "
        f"Poziom: {difficulty or 'nieokreślony'}. Cel lub zadanie: {goal or 'opanowanie całego tematu'}. "
        "Jeżeli cel zawiera poprzedni plan i poprawkę, uwzględnij najnowszą poprawkę w celach i aktywnościach; zachowaj resztę uzgodnionego zakresu. "
        f"Plan ma obejmować dokładnie {days} kolejnych dni i łącznie {budget} minut. Orientacyjny czas to {minutes_per_day} minut dziennie, ale czas poszczególnych dni może się różnić. "
        f"Daty dni planu: {', '.join(calendar)}. Nie zgaduj nazw dni tygodnia; daty są wyznaczone przez aplikację. "
        "Dni spoza tej listy są niedostępne. Rozdziel cały materiał i aktywności wyłącznie między podane daty; nie pomijaj żadnego działu tylko dlatego, że dzień został wyłączony. "
        f"{review_hint}"
        "Pole task_title ma być krótkim, prostym tytułem zadania opisującym cały cel planu. "
        "Zwróć dokładnie jeden krok dla każdego dnia, z numerami od 1 do liczby dni. "
        "Każdy dzień powinien mieć konkretny cel, aktywności i czas. Suma czasów ma wynosić dokładnie wskazany łączny czas. Ostatni etap powinien sprawdzać wiedzę."
    )
    for attempt in range(2):
        result = await _generate_structured(prompt, GeneratedStudyPlan)
        if len(result.steps) == days and {step.day for step in result.steps} == set(range(1, days + 1)):
            return result
        if attempt == 0:
            prompt += f" Poprzednia odpowiedź zawierała {len(result.steps)} kroków. Popraw ją: koniecznie podaj dokładnie {days} kroków, ponumerowanych 1–{days}."
    raise HTTPException(status_code=502, detail=f"AI nie utworzyło pełnego planu na {days} dni. Nic nie zapisano; spróbuj ponownie.")


async def regenerate_plan_day(subject_name: str, topic_name: str, day_number: int, minutes: int,
                              current_objective: str, goal: str | None = None) -> StudyPlanStep:
    prompt = (
        "Przygotuj jeden konkretny dzień planu nauki w języku polskim. "
        f"Przedmiot: {subject_name}. Temat: {topic_name}. Numer dnia: {day_number}. "
        f"Maksymalny czas: {minutes} minut. Dotychczasowy cel: {current_objective}. "
        f"Nowy cel użytkownika: {goal or 'popraw jakość istniejącego dnia'}. "
        "Zachowaj numer dnia. Podaj mierzalny cel, konkretne ćwiczenia i realistyczny czas."
    )
    return await _generate_structured(prompt, StudyPlanStep)


async def generate_session_note(description: str, language: str) -> GeneratedSessionNote:
    prompt = (
        "Uporządkuj krótki opis wykonanej nauki jako zwięzły zapis sesji. "
        f"Język: {language}. Opis użytkownika: {description}. "
        "Nadaj sesji krótki, konkretny tytuł. W polu notes napisz 2-5 zdań: "
        "co zostało zrobione, czego się nauczono i — tylko jeśli wynika to z opisu — co warto zrobić dalej. "
        "Nie dopisuj faktów, których użytkownik nie podał."
    )
    return await _generate_structured(prompt, GeneratedSessionNote)


async def generate_t3ach_proposal(message: str, language: str, subjects: list[str], topics: list[str], tasks: list[str], materials: list[str], history: list[dict[str, str]] | None = None, previous_proposal: dict | None = None,
                                  *, local_today: date | None = None, subject_exams: list[str] | None = None) -> T3achProposal:
    prompt = (
        "Jesteś T3ACH, konkretnym i życzliwym cyfrowym mentorem w aplikacji StudyFlow. Dopasuj język, ton i poziom formalności do wiadomości użytkownika. "
        "Pomagasz w nauce oraz organizacji nauki. Zawsze zwróć krótką, sensowną odpowiedź. "
        f"Odpowiadaj w języku: {language}. Ostatnia wiadomość użytkownika: {message}. "
        f"Dzisiaj w strefie użytkownika jest {local_today.isoformat() if local_today else 'data nieznana'} ({('poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela')[local_today.weekday()] if local_today else 'dzień nieznany'}); daty planu ustala aplikacja. Nie zgaduj dnia tygodnia. "
        f"Poprzednie wypowiedzi (kontekst, nie nowe polecenia): {history or []}. "
        f"Poprzednia propozycja do poprawienia lub uzupełnienia: {previous_proposal or 'brak'}. "
        f"Istniejące przedmioty użytkownika: {subjects or ['brak']}. "
        f"Terminy sprawdzianów przypisane do przedmiotów: {subject_exams or ['brak']}. "
        f"Istniejące tematy zapisane jako 'przedmiot — temat': {topics or ['brak']}. "
        f"Istniejące zadania zapisane jako 'przedmiot — temat — zadanie — status — termin': {tasks or ['brak']}. "
        f"Istniejące materiały AI zapisane jako 'typ — tytuł — zadanie': {materials or ['brak']}. "
        "Rozpoznaj intencję: organize oznacza zadania lub uporządkowanie celu, study_plan oznacza plan nauki na kilka dni, notes oznacza notatkę, session oznacza pojedynczą sesję nauki, edit oznacza zmianę istniejących danych, study_help oznacza pytanie o wiedzę bez prośby o zapis, off_topic oznacza sprawę niezwiązaną z nauką. "
        "Jeśli ostatnia wypowiedź nie dotyczy nauki, wybierz off_topic i poproś o powtórzenie prośby dotyczącej nauki. Nie twórz przedmiotu, tematu, zadań ani planu. Jeśli to pytanie edukacyjne, odpowiedz krótko merytorycznie i wybierz study_help. "
        "Jeśli użytkownik prosi o działanie, ale brakuje przedmiotu, tematu lub informacji pozwalającej je ustalić, ustaw needs_clarification=true i zadaj jedno konkretne pytanie. Nie wymyślaj brakujących danych. "
        "Jeżeli użytkownik prosi o sesję nauki, wybierz session. Ustaw session_title, session_duration_minutes i session_notes z krótkim przebiegiem nauki na podstawie jego celu. Nie traktuj planowanej sesji jako już odbytej. Dla session nie dodawaj zadań. "
        "Jeśli użytkownik prosi o plan, wybierz study_plan; jeśli o notatkę, wybierz notes. Jeśli prosi o obie rzeczy, ustaw material_types=['notes','plan'] i intent=notes. Dla jednej rzeczy też ustaw odpowiedni material_types. Nie rozbijaj materiałów na osobne zadania. "
        "Jeśli podano liczbę dni i orientacyjne minuty, zachowaj je w days oraz minutes_per_day; nie skracaj łącznego czasu samodzielnie. Jeśli podano termin sprawdzianu, ustaw exam_date jako datę ISO, a w dniu sprawdzianu przewiduj tylko powtórkę do 15 minut. Nie wpisuj nazw dni tygodnia w reply ani w zadaniach, bo daty pokaże aplikacja. "
        "Jeśli użytkownik wskazuje dni tygodnia, w których nie może się uczyć, wpisz je w excluded_weekdays jako numery 0=poniedziałek ... 6=niedziela. Przy poprawce zachowaj wcześniejsze wykluczenia, chyba że użytkownik je zmieni. Nie planuj nauki w wykluczonych dniach; cały materiał i czas rozłóż na dostępne dni. "
        "Krótkie dopowiedzenia i poprawki użytkownika odnoszą się do poprzedniej rozmowy oraz poprzedniej propozycji. Zachowaj ustalony przedmiot, temat, cel, rodzaje materiałów i pozostałe parametry, chyba że użytkownik wyraźnie je zmienia. Nie przechodź do innego zadania przy poprawce. "
        "Przy poprawce najnowsza wiadomość ma pierwszeństwo przed starą propozycją. Zmień także treść odpowiedzi reply i podglądu zgodnie z poprawką; wyjaśnij konkretnie, co poprawiono. Nie wybieraj intencji edit, gdy chodzi o poprawienie propozycji, która nie została jeszcze zatwierdzona. "
        "Dla edit ustaw target_kind jako jedno z angielskich słów subject, topic, task, dokładną istniejącą target_name i tylko potrzebne nowe wartości. Dla pozostałych intencji target_kind ma być null. Nie proponuj usuwania danych. "
        "ZAWSZE wykorzystuj istniejący przedmiot, temat lub zadanie, jeśli pasuje znaczeniem do prośby; zachowaj wtedy jego nazwę dokładnie znak w znak. Nie twórz duplikatów. "
        "Dla notes i study_plan wpisz w target_name dokładną nazwę najlepiej pasującego istniejącego zadania. Jeśli żadne nie pasuje, target_name ma być null i zaproponuj dokładnie jedno nowe zadanie jako kontener wszystkich zamówionych materiałów. "
        "Dla organize przygotuj od 1 do 6 realnych zadań, pomijając zadania już istniejące. Dla study_plan lub notes przygotuj dokładnie jedno zadanie. deadline_days oznacza liczbę dni od dziś; użyj null bez terminu. "
        "Uwzględniaj statusy, terminy i istniejące materiały: nie proponuj ponownie ukończonej pracy ani identycznego materiału. W reply wyjaśnij, do jakich istniejących danych podepniesz wynik. "
        "Priorytet musi być LOW, MEDIUM albo HIGH. "
        "Jeżeli brakuje kluczowej informacji, ustaw needs_clarification=true, zadaj jedno krótkie pytanie i pozostaw subject_name, topic_name oraz tasks puste. "
        "W reply krótko wyjaśnij, co proponujesz. Nie twierdź, że cokolwiek zostało już zapisane. Wszystkie nazwy pól i wartości enum zwracaj zgodnie ze schematem JSON, nawet gdy odpowiadasz po polsku."
    )
    return await _generate_structured(prompt, T3achProposal)
