import os
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db.database import Base, get_db
from app.core.config import Settings
from app.main import app
from app.schemas.ai import GeneratedNotes, GeneratedStudyPlan, T3achProposal
from app.core.config import settings
from app.core.traffic import _events
from app.services import auth as auth_service
from app.services import ai as ai_service
from app.services import plans as plan_service
from app.routers.ai import _exam_date_from_message, _explicit_plan_preferences, _mentioned_weekdays, _weekday_availability, _plan_start_from_message


def future_wednesday():
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Warsaw")).date()
    return today + timedelta(days=7 + (2 - today.weekday()) % 7)


@pytest.fixture()
def client(monkeypatch):
    _events.clear()
    async def explain(message, history, previous, preview, language):
        plan = preview.get("plan", preview)
        return f"Zmiana: {message}. {len(plan['steps'])} dostępnych dni i łącznie {sum(step['duration_minutes'] for step in plan['steps'])} minut."
    monkeypatch.setattr(ai_service, "explain_t3ach_result", explain)
    test_database_url = os.getenv("TEST_DATABASE_URL")
    if test_database_url:
        engine = create_engine(test_database_url)
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    def override_db():
        with TestingSession() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as api_client:
        api_client.headers["Accept-Language"] = "pl"
        yield api_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def auth_headers(client, username="student"):
    payload = {"username": username, "password": "secret123"}
    registered = client.post("/auth/register", json=payload)
    assert registered.status_code == 201
    token = client.post("/auth/login", json=payload)
    assert token.status_code == 200
    return {"Authorization": f"Bearer {token.json()['access_token']}"}, registered.json()


def test_registration_rejects_mismatched_passwords(client):
    response = client.post("/auth/register", json={"username": "nowy", "password": "secret123", "confirm_password": "other123"})
    assert response.status_code == 422
    assert client.post("/auth/login", json={"username": "nowy", "password": "secret123"}).status_code == 401


def test_names_capitalize_first_word_and_known_acronyms(client):
    headers, _ = auth_headers(client, "name-student")
    subject = client.post("/subjects", headers=headers, json={"name": "informatyka"}).json()
    topic = client.post("/topics", headers=headers, json={"name": "sql i bazy danych", "subject_uid": subject["subject_uid"]}).json()
    assert subject["name"] == "Informatyka"
    assert topic["name"] == "SQL i bazy danych"
    renamed = client.patch(f"/topics/{topic['topic_uid']}", headers=headers, json={"name": "podstawy api"}).json()
    assert renamed["name"] == "Podstawy API"


def create_subject(client, headers, name="Matematyka"):
    response = client.post("/subjects", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_health_and_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "test-123"})
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-123"


def test_frontend_origin_is_allowed(client):
    response = client.options(
        "/subjects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_login_and_current_user(client):
    headers, user = auth_headers(client)
    current = client.get("/users/me", headers=headers)
    assert current.status_code == 200
    assert current.json()["user_uid"] == user["user_uid"]
    assert "password_hash" not in current.json()
    assert client.post("/auth/login", json={"username": "student", "password": "wrong-password"}).status_code == 401


def test_language_preference_and_localized_errors(client):
    english = {"Accept-Language": "en"}
    registered = client.post("/auth/register", headers=english,
                             json={"username": "language-user", "password": "secret123"})
    assert registered.status_code == 201
    assert registered.json()["language"] == "en"
    token = client.post("/auth/login", headers=english,
                        json={"username": "language-user", "password": "secret123"}).json()["access_token"]
    authorization = {"Authorization": f"Bearer {token}"}
    changed = client.patch("/users/me", headers={**authorization, **english}, json={"language": "pl"})
    assert changed.status_code == 200
    assert changed.json()["language"] == "pl"
    assert client.get("/users/me", headers=authorization).json()["language"] == "pl"
    invalid = client.patch("/users/me", headers={**authorization, **english}, json={"language": "de"})
    assert invalid.status_code == 422
    assert client.post("/auth/login", headers=english, json={"username": "language-user", "password": "wrong"}).json()["detail"] == "Invalid username or password."
    polish_error = client.post("/auth/login", json={"username": "language-user", "password": "wrong"})
    assert polish_error.json()["detail"] == "Nieprawidłowa nazwa użytkownika lub hasło."
    assert polish_error.headers["content-language"] == "pl"


def test_t3ach_voice_uses_saved_account_language(client, monkeypatch):
    headers, _ = auth_headers(client, "voice-language")
    spoken_languages = []

    async def fake_speech(text, language):
        spoken_languages.append(language)
        return b"RIFFtest"

    monkeypatch.setattr(ai_service, "generate_t3ach_speech", fake_speech)
    assert client.post("/ai/t3ach/speech", headers=headers, json={"text": "Hello"}).status_code == 200
    assert client.patch("/users/me", headers=headers, json={"language": "pl"}).status_code == 200
    assert client.post("/ai/t3ach/speech", headers=headers, json={"text": "Cześć"}).status_code == 200
    assert spoken_languages == ["English", "Polish"]


def test_english_plan_instructions_keep_dates_and_availability():
    today = date(2026, 9, 30)
    assert _plan_start_from_message("Start tomorrow", today) == date(2026, 10, 1)
    assert _plan_start_from_message("Begin day after tomorrow", today) == date(2026, 10, 2)
    assert _exam_date_from_message("The exam is in 6 days", today) == date(2026, 10, 6)
    assert _explicit_plan_preferences("Plan for 5 days, 40 minutes per day") == (5, 40)
    assert _weekday_availability("I cannot study on Saturday and Sunday")[0] == {5, 6}


def test_login_lockout_expires_and_success_clears_failures(client, monkeypatch):
    auth_headers(client, "lockout-student")
    wrong = {"username": "lockout-student", "password": "wrong-password"}
    correct = {"username": "lockout-student", "password": "secret123"}

    assert client.post("/auth/login", json=wrong).status_code == 401
    assert client.post("/auth/login", json=correct).status_code == 200

    for _ in range(settings.failed_login_limit - 1):
        assert client.post("/auth/login", json=wrong).status_code == 401
    locked = client.post("/auth/login", json=wrong)
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) == settings.login_lock_minutes * 60
    assert client.post("/auth/login", json=correct).status_code == 429

    now = auth_service._now()
    monkeypatch.setattr(auth_service, "_now", lambda: now + timedelta(minutes=settings.login_lock_minutes + 1))
    assert client.post("/auth/login", json=correct).status_code == 200
    assert client.post("/auth/login", json=wrong).status_code == 401


def test_login_failure_window_resets_without_lockout(client, monkeypatch):
    auth_headers(client, "window-student")
    wrong = {"username": "window-student", "password": "wrong-password"}
    for _ in range(settings.failed_login_limit - 1):
        assert client.post("/auth/login", json=wrong).status_code == 401
    now = auth_service._now()
    monkeypatch.setattr(auth_service, "_now", lambda: now + timedelta(minutes=16))
    assert client.post("/auth/login", json=wrong).status_code == 401


@pytest.mark.parametrize("path", ["/users/me", "/subjects", "/topics", "/tasks", "/study-sessions", "/exam-results"])
def test_protected_endpoints_require_token(client, path):
    assert client.get(path).status_code == 401


def test_users_cannot_access_each_others_data(client):
    first_headers, _ = auth_headers(client, "first-user")
    second_headers, _ = auth_headers(client, "second-user")
    subject = create_subject(client, first_headers)
    assert client.get(f"/subjects/{subject['subject_uid']}", headers=second_headers).status_code == 404
    assert client.get("/subjects", headers=second_headers).json()["total"] == 0


def test_subject_names_are_unique_per_user(client):
    headers, _ = auth_headers(client)
    first = create_subject(client, headers, "Matematyka")

    duplicate = client.post("/subjects", headers=headers, json={"name": "  matematyka  "})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Przedmiot o tej nazwie już istnieje."

    second = create_subject(client, headers, "Fizyka")
    renamed = client.patch(
        f"/subjects/{second['subject_uid']}",
        headers=headers,
        json={"name": "MATEMATYKA"},
    )
    assert renamed.status_code == 409

    other_headers, _ = auth_headers(client, "other-student")
    assert client.post("/subjects", headers=other_headers, json={"name": "Matematyka"}).status_code == 201
    assert client.patch(f"/subjects/{first['subject_uid']}", headers=headers, json={"name": " Matematyka "}).status_code == 200


def test_blank_topic_and_task_names_are_rejected(client):
    headers, _ = auth_headers(client, "blank-names")
    subject = create_subject(client, headers)
    blank_topic = client.post("/topics", headers=headers, json={"name": "   ", "subject_uid": subject["subject_uid"]})
    assert blank_topic.status_code == 422
    topic = client.post("/topics", headers=headers, json={"name": " Algebra ", "subject_uid": subject["subject_uid"]}).json()
    assert topic["name"] == "Algebra"
    blank_task = client.post("/tasks", headers=headers, json={"title": "   ", "topic_uid": topic["topic_uid"]})
    assert blank_task.status_code == 422
    task = client.post("/tasks", headers=headers, json={"title": " Powtórka ", "topic_uid": topic["topic_uid"]}).json()
    assert task["title"] == "Powtórka"
    assert client.patch(f"/topics/{topic['topic_uid']}", headers=headers, json={"name": "   "}).status_code == 422
    assert client.patch(f"/tasks/{task['task_uid']}", headers=headers, json={"title": "   "}).status_code == 422


def test_bulk_complete_is_atomic_and_checks_ownership(client):
    first_headers, _ = auth_headers(client, "bulk-owner")
    other_headers, _ = auth_headers(client, "bulk-other")
    subject = create_subject(client, first_headers)
    topic = client.post("/topics", headers=first_headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    first = client.post("/tasks", headers=first_headers, json={"title": "Pierwsze", "topic_uid": topic["topic_uid"]}).json()
    second = client.post("/tasks", headers=first_headers, json={"title": "Drugie", "topic_uid": topic["topic_uid"]}).json()
    foreign_subject = create_subject(client, other_headers, "Fizyka")
    foreign_topic = client.post("/topics", headers=other_headers, json={"name": "Ruch", "subject_uid": foreign_subject["subject_uid"]}).json()
    foreign = client.post("/tasks", headers=other_headers, json={"title": "Obce", "topic_uid": foreign_topic["topic_uid"]}).json()
    rejected = client.post("/tasks/bulk-complete", headers=first_headers, json={"task_uids": [first["task_uid"], foreign["task_uid"]]})
    assert rejected.status_code == 404
    assert client.get(f"/tasks/{first['task_uid']}", headers=first_headers).json()["is_done"] is False
    accepted = client.post("/tasks/bulk-complete", headers=first_headers, json={"task_uids": [first["task_uid"], second["task_uid"]]})
    assert accepted.status_code == 200
    assert accepted.json() == {"updated": 2}
    assert client.get(f"/tasks/{first['task_uid']}", headers=first_headers).json()["is_done"] is True
    assert client.get(f"/tasks/{second['task_uid']}", headers=first_headers).json()["is_done"] is True


def test_topic_move_reports_name_conflict(client):
    headers, _ = auth_headers(client, "move-topic")
    first_subject = create_subject(client, headers, "Fizyka")
    second_subject = create_subject(client, headers, "Matematyka")
    first = client.post("/topics", headers=headers, json={"name": "Wzory", "subject_uid": first_subject["subject_uid"]}).json()
    client.post("/topics", headers=headers, json={"name": "Wzory", "subject_uid": second_subject["subject_uid"]})
    response = client.patch(f"/topics/{first['topic_uid']}", headers=headers, json={"subject_uid": second_subject["subject_uid"]})
    assert response.status_code == 409
    assert response.json()["detail"] == "Temat o tej nazwie już istnieje w tym przedmiocie."
    assert client.get(f"/topics/{first['topic_uid']}", headers=headers).json()["subject_uid"] == first_subject["subject_uid"]


def test_session_summary_matches_local_day(client):
    headers, _ = auth_headers(client, "session-summary")
    subject = create_subject(client, headers)
    result = client.post("/study-sessions", headers=headers, json={"subject_uid": subject["subject_uid"], "duration_minutes": 35})
    assert result.status_code == 201
    summary = client.get("/study-sessions/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json() == {"today_minutes": 35, "week_minutes": 35, "streak": 1}


def test_jwt_secret_must_be_unique_and_long():
    with pytest.raises(ValueError):
        Settings(jwt_secret_key="short")
    with pytest.raises(ValueError):
        Settings(jwt_secret_key="development-only-secret-change-this-123456789")


def test_full_crud_for_study_resources(client):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    subject_uid = subject["subject_uid"]
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject_uid}).json()
    task = client.post("/tasks", headers=headers, json={"title": "Równania", "topic_uid": topic["topic_uid"], "priority": "HIGH", "notes": "Rozdział 4"}).json()
    session = client.post("/study-sessions", headers=headers, json={"subject_uid": subject_uid, "topic_uid": topic["topic_uid"], "task_uid": task["task_uid"], "duration_minutes": 45, "notes": "Powtórka"}).json()
    assert task["notes"] == "Rozdział 4"
    assert session["topic_uid"] == topic["topic_uid"]
    assert session["task_uid"] == task["task_uid"]
    other_subject = create_subject(client, headers, "Chemia")
    invalid_session = client.post("/study-sessions", headers=headers, json={"subject_uid": other_subject["subject_uid"], "topic_uid": topic["topic_uid"], "duration_minutes": 10})
    assert invalid_session.status_code == 422
    result = client.post("/exam-results", headers=headers, json={"subject_uid": subject_uid, "score_percent": 88.5}).json()

    resources = [
        ("subjects", subject_uid, {"name": "Fizyka"}, "name", "Fizyka"),
        ("topics", topic["topic_uid"], {"is_done": True}, "is_done", True),
        ("tasks", task["task_uid"], {"is_done": True}, "is_done", True),
        ("study-sessions", session["study_uid"], {"duration_minutes": 60}, "duration_minutes", 60),
        ("exam-results", result["exam_uid"], {"score_percent": 90}, "score_percent", "90.00"),
    ]
    for resource, uid, update, field, expected in resources:
        assert client.get(f"/{resource}/{uid}", headers=headers).status_code == 200
        changed = client.patch(f"/{resource}/{uid}", headers=headers, json=update)
        assert changed.status_code == 200
        assert changed.json()[field] == expected

    for resource, uid, *_ in reversed(resources):
        assert client.delete(f"/{resource}/{uid}", headers=headers).status_code == 204
        assert client.get(f"/{resource}/{uid}", headers=headers).status_code == 404


def test_pagination_filters_search_and_sort(client):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"], "difficulty": "HARD"}).json()
    for number, priority in enumerate(["LOW", "HIGH", "HIGH"]):
        client.post("/tasks", headers=headers, json={"title": f"Task {number}", "topic_uid": topic["topic_uid"], "priority": priority})

    page = client.get("/tasks", headers=headers, params={"priority": "HIGH", "search": "Task", "sort": "title", "order": "desc", "page": 1, "page_size": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["pages"] == 2
    assert len(page.json()["items"]) == 1
    assert client.get("/tasks", headers=headers, params={"sort": "invalid"}).status_code == 422


def test_input_validation(client):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    assert client.post("/study-sessions", headers=headers, json={"subject_uid": subject["subject_uid"], "duration_minutes": -1}).status_code == 422
    assert client.post("/exam-results", headers=headers, json={"subject_uid": subject["subject_uid"], "score_percent": 101}).status_code == 422
    assert client.get("/subjects", headers=headers, params={"page": 0}).status_code == 422


def test_ai_notes_require_authentication(client):
    assert client.post(
        "/ai/topics/00000000-0000-0000-0000-000000000001/notes",
        json={},
    ).status_code == 401


def test_generate_notes_for_owned_topic(client, monkeypatch):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    topic = client.post(
        "/topics",
        headers=headers,
        json={"name": "Równania kwadratowe", "subject_uid": subject["subject_uid"], "difficulty": "Średni"},
    ).json()
    captured = {}

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return GeneratedNotes(**{
            "task_title": "Nauka równań kwadratowych",
            "title": "Równania kwadratowe — notatka",
            "summary": "Najważniejsze informacje.",
            "sections": [{"heading": "Definicja", "content": "Opis zagadnienia."}],
            "key_points": ["Zapamiętaj deltę."],
            "review_questions": ["Czym jest delta?"],
        })

    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", fake_generate)
    response = client.post(
        f"/ai/topics/{topic['topic_uid']}/notes",
        headers=headers,
        json={"language": "polski", "detail_level": "detailed"},
    )

    assert response.status_code == 200
    assert response.json()["sections"][0]["heading"] == "Definicja"
    history = client.get("/ai/materials", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["material_type"] == "notes"
    assert history.json()[0]["title"] == "Równania kwadratowe — notatka"
    created_tasks = client.get("/tasks", headers=headers).json()["items"]
    assert len(created_tasks) == 1
    assert created_tasks[0]["title"] == "Nauka równań kwadratowych"
    assert created_tasks[0]["notes"] is None
    assert history.json()[0]["task_uid"] == created_tasks[0]["task_uid"]
    assert captured == {
        "subject_name": "Matematyka",
        "topic_name": "Równania kwadratowe",
        "difficulty": "Średni",
        "language": "polski",
        "detail_level": "detailed",
        "goal": None,
    }


def test_onboarding_materials_are_saved_only_after_review(client, monkeypatch):
    headers, _ = auth_headers(client, "review-first-plan")
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()

    async def fake_notes(**kwargs):
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka", summary="Podstawy",
                              sections=[{"heading": "Definicja", "content": "Treść"}], key_points=["Punkt"])

    async def fake_plan(*args, **kwargs):
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan", overview="Powtórka",
                                  steps=[{"day": day, "title": "Podstawy", "objective": "Zrozumieć",
                                          "activities": ["Ćwiczenia"], "duration_minutes": 30}
                                         for day in range(1, args[4] + 1)], success_criteria=["Umiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", fake_notes)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    note = client.post(f"/ai/topics/{topic['topic_uid']}/notes", headers=headers,
                       json={"preview_only": True}).json()
    plan = client.post(f"/ai/topics/{topic['topic_uid']}/plan", headers=headers,
                       json={"preview_only": True, "days": 2, "minutes_per_day": 30}).json()
    assert plan["plan_uid"] is None
    assert client.get("/ai/materials", headers=headers).json() == []
    assert client.get("/plans", headers=headers).json() == []
    assert client.get("/tasks", headers=headers).json()["items"] == []

    note["sections"][0]["content"] = "Poprawiona treść"
    plan["steps"][0]["duration_minutes"] = 45
    saved = client.post(f"/ai/topics/{topic['topic_uid']}/materials/accept", headers=headers,
                        json={"notes": note, "plan": plan, "minutes_per_day": 30})
    assert saved.status_code == 200
    assert saved.json()["note_uid"] and saved.json()["plan_uid"]
    materials = client.get("/ai/materials", headers=headers).json()
    assert next(item for item in materials if item["material_type"] == "notes")["content"]["sections"][0]["content"] == "Poprawiona treść"
    assert client.get("/plans", headers=headers).json()[0]["days"][0]["duration_minutes"] == 45
    assert len(client.get("/tasks", headers=headers).json()["items"]) == 1


def test_onboarding_material_review_rejects_invalid_plan_without_saving_note(client):
    headers, _ = auth_headers(client, "invalid-reviewed-plan")
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    note = {"task_title": "Nauka", "title": "Notatka", "summary": "Opis",
            "sections": [{"heading": "A", "content": "Treść"}], "key_points": ["Punkt"]}
    plan = {"task_title": "Nauka", "title": "Plan", "overview": "Opis", "start_date": "2026-10-01",
            "steps": [{"day": 1, "title": "A", "objective": "Cel", "activities": ["Ćwicz"], "duration_minutes": 30},
                      {"day": 1, "title": "B", "objective": "Cel", "activities": ["Ćwicz"], "duration_minutes": 30}],
            "success_criteria": ["Umiem"]}
    response = client.post(f"/ai/topics/{topic['topic_uid']}/materials/accept", headers=headers,
                           json={"notes": note, "plan": plan, "minutes_per_day": 30})
    assert response.status_code == 422
    assert client.get("/ai/materials", headers=headers).json() == []
    assert client.get("/tasks", headers=headers).json()["items"] == []


def test_generate_study_plan_with_selected_task(client, monkeypatch):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    task = client.post("/tasks", headers=headers, json={"title": "Przygotuj się do kartkówki", "topic_uid": topic["topic_uid"]}).json()
    captured = {}

    async def fake_plan(*args, **kwargs):
        captured["args"] = args
        return GeneratedStudyPlan(**{"task_title": "Powtórka algebry", "title": "Plan", "overview": "Plan powtórki.", "steps": [{"day": day, "title": "Podstawy", "objective": "Zrozumienie", "activities": ["Przeczytaj notatki"], "duration_minutes": 30} for day in range(1, args[4] + 1)], "success_criteria": ["Rozwiązuję przykłady"]})

    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post(f"/ai/topics/{topic['topic_uid']}/plan", headers=headers, json={"task_uid": task["task_uid"], "days": 5, "minutes_per_day": 30, "local_date": "2026-09-29", "local_hour": 19})
    assert response.status_code == 200
    assert response.json()["steps"][0]["day"] == 1
    assert captured["args"][-1] == "Przygotuj się do kartkówki"
    plans = client.get("/ai/materials", headers=headers, params={"task_uid": task["task_uid"]})
    assert plans.status_code == 200
    assert plans.json()[0]["task_uid"] == task["task_uid"]
    study_plans = client.get("/plans", headers=headers).json()
    assert len(study_plans) == 1
    assert study_plans[0]["days"][0]["title"] == "Podstawy"
    assert study_plans[0]["days"][0]["calendar_task_uid"] is None


def test_ai_notes_cannot_access_another_users_topic(client, monkeypatch):
    first_headers, _ = auth_headers(client, "ai-owner")
    second_headers, _ = auth_headers(client, "ai-stranger")
    subject = create_subject(client, first_headers)
    topic = client.post(
        "/topics",
        headers=first_headers,
        json={"name": "Algebra", "subject_uid": subject["subject_uid"]},
    ).json()

    async def should_not_run(**kwargs):
        raise AssertionError("Gemini should not be called")

    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", should_not_run)
    response = client.post(f"/ai/topics/{topic['topic_uid']}/notes", headers=second_headers, json={})
    assert response.status_code == 404


def test_t3ach_proposes_then_executes_actions(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-user")

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(
            reply="Ułożę podstawy nauki algebry.",
            subject_name="Matematyka",
            topic_name="Algebra",
            difficulty="Średni",
            tasks=[
                {"title": "Powtórz działania", "priority": "HIGH", "deadline_days": 2, "notes": "Zacznij od podstaw."},
                {"title": "Rozwiąż zadania", "priority": "MEDIUM", "deadline_days": None, "notes": None},
            ],
        )

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    proposal = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Chcę nauczyć się algebry"})
    assert proposal.status_code == 200
    assert proposal.json()["topic_name"] == "Algebra"

    other_headers, _ = auth_headers(client, "t3ach-other")
    assert client.post("/ai/t3ach/execute", headers=other_headers, json={"proposal_uid": proposal.json()["proposal_uid"]}).status_code == 404
    tampered = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal.json()["proposal_uid"], "tasks": [{"title": "Nieautoryzowana zmiana"}]})
    assert tampered.status_code == 422
    executed = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal.json()["proposal_uid"]})
    assert executed.status_code == 200
    assert executed.json()["created_subject"] is True
    assert executed.json()["created_topic"] is True
    assert len(executed.json()["task_uids"]) == 2
    assert len(client.get("/tasks", headers=headers).json()["items"]) == 2
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal.json()["proposal_uid"]}).status_code == 409


def test_t3ach_normalizes_unused_gemini_fields():
    proposal = T3achProposal(reply="Co dokładnie chcesz przygotować?", intent="chat", days=0, minutes_per_day=0)
    assert proposal.days == 7
    assert proposal.minutes_per_day == 45
    assert proposal.intent == "organize"
    assert proposal.needs_clarification is True
    assert proposal.question == proposal.reply


def test_t3ach_normalizes_polish_enum_values_and_rejects_off_topic():
    proposal = T3achProposal.model_validate({"reply": "Dodam zadanie.", "intent": "edit", "target_kind": "zadanie", "new_priority": "wysoki", "tasks": [{"title": "Powtórka", "priority": "średni"}]})
    assert proposal.target_kind == "task"
    assert proposal.new_priority == "HIGH"
    assert proposal.tasks[0].priority == "MEDIUM"
    plan = T3achProposal.model_validate({"reply": "Przygotuję plan.", "intent": "study_plan", "target_kind": "zadanie domowe"})
    assert plan.target_kind is None
    unrelated = T3achProposal(reply="Opowiem o pogodzie.", intent="off_topic", subject_name="Matematyka", tasks=[{"title": "Pogoda"}])
    assert unrelated.needs_clarification is True
    assert unrelated.tasks == []
    assert "nauce" in unrelated.reply


def test_t3ach_reuses_existing_structure_for_plan(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-reuse")
    subject = create_subject(client, headers, "Matematyka")
    topic = client.post("/topics", headers=headers, json={"name": "Wielomiany", "subject_uid": subject["subject_uid"]}).json()
    task = client.post("/tasks", headers=headers, json={"title": "Powtórka wielomianów", "topic_uid": topic["topic_uid"], "priority": "MEDIUM"}).json()

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Ułożę plan.", intent="study_plan", subject_name=" matematyka ", topic_name="wielomiany", target_kind="zadanie", target_name="powtorka wielomianow", tasks=[])

    async def fake_plan(*args, **kwargs):
        return GeneratedStudyPlan(task_title="Powtórka wielomianów", title="Plan wielomianów", overview="Powtórka", steps=[{"day": day, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45} for day in range(1, args[4] + 1)], success_criteria=["Umiem rozwiązać zadania"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan nauki wielomianów"})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["subject_name"] == "Matematyka"
    assert proposal["topic_name"] == "Wielomiany"
    assert proposal["target_name"] == "Powtórka wielomianów"
    executed = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]})
    assert executed.status_code == 200
    assert executed.json()["created_subject"] is False
    assert executed.json()["created_topic"] is False
    assert executed.json()["task_uids"] == []
    assert len(executed.json()["plan_uids"]) == 1
    assert client.get("/tasks", headers=headers).json()["total"] == 1


def test_t3ach_creates_note_and_plan_from_one_request(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-both")

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Przygotuję notatkę i plan.", intent="notes", material_types=["notes", "plan"], subject_name="Matematyka", topic_name="Algebra", tasks=[{"title": "Nauka algebry"}])

    async def fake_notes(*args):
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka z algebry", summary="Podstawy", sections=[{"heading": "Definicje", "content": "Treść"}], key_points=["Punkt"], review_questions=[])

    async def fake_plan(*args, **kwargs):
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan algebry", overview="Powtórka", steps=[{"day": day, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45} for day in range(1, args[4] + 1)], success_criteria=["Umiem rozwiązać zadania"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", fake_notes)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Przygotuj notatkę i plan nauki algebry", "local_date": "2026-09-29"})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["material_types"] == ["notes", "plan"]
    assert set(proposal["preview"]) == {"notes", "plan"}
    assert "Definicje" not in proposal["reply"]
    executed = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]})
    assert executed.status_code == 200
    assert len(executed.json()["task_uids"]) == 1
    assert len(executed.json()["plan_uids"]) == 1
    assert client.get("/plans", headers=headers).json()[0]["days"][0]["calendar_task_uid"] is None
    materials = client.get("/ai/materials", headers=headers).json()
    assert {item["material_type"] for item in materials} == {"notes", "plan"}
    assert {item["task_uid"] for item in materials} == {executed.json()["task_uids"][0]}


def test_plan_days_calendar_export_and_optional_tasks(client):
    headers, _ = auth_headers(client, "plan-lifecycle")
    subject = create_subject(client, headers, "Fizyka")
    topic = client.post("/topics", headers=headers, json={"name": "Mechanika", "subject_uid": subject["subject_uid"]}).json()
    created = client.post(f"/ai/topics/{topic['topic_uid']}/fallback-plan", headers=headers,
                          json={"goal": "Powtórka", "days": 3, "minutes_per_day": 45})
    assert created.status_code == 200
    plan = client.get("/plans", headers=headers).json()[0]
    assert len(plan["days"]) == 3
    day = plan["days"][0]
    assert day["scheduled_time"] is None
    scheduled = client.patch(f"/plans/{plan['plan_uid']}/days/{day['day_uid']}", headers=headers,
                             json={"scheduled_time": "09:30", "duration_minutes": 75})
    assert scheduled.status_code == 200
    assert scheduled.json()["scheduled_time"] == "09:30"
    assert scheduled.json()["duration_minutes"] == 75
    assert client.patch(f"/plans/{plan['plan_uid']}/days/{day['day_uid']}", headers=headers,
                        json={"duration_minutes": 0}).status_code == 422
    timed_calendar = client.get("/calendar/export.ics", headers=headers).text
    assert "DTSTART:" in timed_calendar
    assert "DTSTART;VALUE=DATE:" in timed_calendar
    assert client.patch(f"/plans/{plan['plan_uid']}/days/{day['day_uid']}", headers=headers,
                        json={"is_done": True}).json()["is_done"] is True
    assert client.get("/tasks", headers=headers).json()["total"] == 0
    calendar = client.get("/calendar/export.ics", headers=headers)
    assert calendar.status_code == 200
    assert calendar.text.count("BEGIN:VEVENT") == 2
    with_tasks = client.post(f"/plans/{plan['plan_uid']}/calendar-tasks", headers=headers,
                             json={"create_tasks": True})
    assert with_tasks.status_code == 200
    assert all(item["calendar_task_uid"] for item in with_tasks.json()["days"])
    assert client.get("/tasks", headers=headers).json()["total"] == 3
    assert all(task["deadline"] is None for task in client.get("/tasks", headers=headers).json()["items"] if task["task_uid"] != with_tasks.json()["days"][0]["calendar_task_uid"])
    exported = client.get("/calendar/export.ics", headers=headers).text
    assert exported.count("BEGIN:VEVENT") == 2
    assert exported.count("DTSTART;VALUE=DATE:") == 2
    second_day = with_tasks.json()["days"][1]
    changed = client.patch(f"/plans/{plan['plan_uid']}/days/{second_day['day_uid']}", headers=headers,
                           json={"scheduled_time": "14:00", "duration_minutes": 60})
    assert changed.status_code == 200
    linked_task = next(task for task in client.get("/tasks", headers=headers).json()["items"] if task["task_uid"] == second_day["calendar_task_uid"])
    assert linked_task["deadline"] is not None
    exported = client.get("/calendar/export.ics", headers=headers).text
    assert exported.count("BEGIN:VEVENT") == 2
    assert exported.count("DTSTART;VALUE=DATE:") == 1


def test_notes_export_reviews_and_subject_archive_are_user_scoped(client):
    first, _ = auth_headers(client, "notes-owner")
    second, _ = auth_headers(client, "notes-other")
    subject = client.post("/subjects", headers=first,
                          json={"name": "informatyka", "color": "#aa44cc", "tags": ["semestr 1"]}).json()
    assert subject["color"] == "#aa44cc"
    assert subject["tags"] == ["semestr 1"]
    topic = client.post("/topics", headers=first,
                        json={"name": "sql", "subject_uid": subject["subject_uid"]}).json()
    note = client.post(f"/ai/topics/{topic['topic_uid']}/manual-note", headers=first,
                       json={"title": "SQL", "content": "SELECT <script>alert(1)</script>"})
    assert note.status_code == 200
    material = client.get("/ai/materials", headers=first).json()[0]
    markdown = client.get(f"/ai/materials/{material['material_uid']}/export.md", headers=first)
    assert markdown.status_code == 200 and "SELECT" in markdown.text
    printed = client.get(f"/ai/materials/{material['material_uid']}/print", headers=first)
    assert "&lt;script&gt;" in printed.text
    assert client.get(f"/ai/materials/{material['material_uid']}/export.md", headers=second).status_code == 404
    review = client.get("/reviews", headers=first).json()[0]
    answered = client.post(f"/reviews/{review['review_uid']}/answer", headers=first, json={"rating": "easy"})
    assert answered.status_code == 200 and answered.json()["streak"] == 1
    assert client.post(f"/reviews/{review['review_uid']}/answer", headers=second, json={"rating": "easy"}).status_code == 404
    archived = client.patch(f"/subjects/{subject['subject_uid']}", headers=first,
                            json={"archived": True}).json()
    assert archived["archived_at"] is not None
    assert client.get("/subjects", headers=first).json()["total"] == 0
    assert client.get("/subjects?archived=true", headers=first).json()["total"] == 1


def test_t3ach_study_question_answers_without_acceptance_card(client, monkeypatch):
    headers, _ = auth_headers(client, "study-help")

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(intent="study_help", reply="SELECT pobiera wiersze z tabeli.",
                             subject_name="Informatyka", topic_name="SQL")

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    response = client.post("/ai/t3ach/propose", headers=headers,
                           json={"message": "Co robi SELECT w SQL?"})
    assert response.status_code == 200
    assert response.json()["needs_clarification"] is True
    assert response.json()["question"] == "SELECT pobiera wiersze z tabeli."
    assert client.get("/subjects", headers=headers).json()["total"] == 0


def test_t3ach_rejects_invalid_saved_preview_without_writing_data(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-bad-preview")

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Przygotuję notatkę.", intent="notes", subject_name="Matematyka", topic_name="Algebra", tasks=[{"title": "Nauka algebry"}])

    async def fake_notes(*args):
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka", summary="Podstawy", sections=[{"heading": "Definicje", "content": "Treść"}], key_points=["Punkt"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", fake_notes)
    proposal = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Notatka z algebry"}).json()
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    conversation = db.get(models.AiConversation, UUID(proposal["proposal_uid"]))
    conversation.proposal = {**conversation.proposal, "preview": {"sections": "invalid"}}
    db.commit()
    db_generator.close()

    response = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]})
    assert response.status_code == 422
    assert client.get("/ai/materials", headers=headers).json() == []
    assert client.get("/tasks", headers=headers).json()["total"] == 0


def test_t3ach_passes_previous_turn_to_model(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-context")
    captured = {}

    async def fake_proposal(*args, **kwargs):
        captured["history"] = args[6]
        captured["previous"] = args[7]
        return T3achProposal(reply="Jaki temat?", needs_clarification=True, question="Jaki temat?", subject_name="Matematyka", topic_name="Algebra")

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    previous_response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan algebry"})
    assert previous_response.status_code == 200
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Jednak na pięć dni", "history": [{"role": "user", "text": "Ułóż plan algebry"}, {"role": "assistant", "text": "Przygotuję plan."}], "previous_proposal_uid": previous_response.json()["proposal_uid"]})
    assert response.status_code == 200
    assert captured["history"][0]["text"] == "Ułóż plan algebry"
    assert captured["previous"]["topic_name"] == "Algebra"
    assert captured["previous"]["original_request"] == "Ułóż plan algebry"
    assert "preview" not in captured["previous"]
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": previous_response.json()["proposal_uid"]}).status_code == 409
    assert client.post("/ai/t3ach/propose", headers=headers, json={"message": "Jednak na sześć dni", "previous_proposal_uid": previous_response.json()["proposal_uid"]}).status_code == 409


def test_t3ach_revision_uses_original_request_for_materials(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-revision")
    goals = []
    previous_context = []

    async def fake_proposal(*args, **kwargs):
        previous_context.append(args[7])
        return T3achProposal(reply="Przygotuję poprawioną notatkę i plan.", intent="notes", material_types=["notes", "plan"], subject_name="Matematyka", topic_name="Algebra", days=5, tasks=[{"title": "Nauka algebry"}])

    async def fake_notes(*args):
        goals.append(args[-1])
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka", summary="Podstawy", sections=[{"heading": "Definicje", "content": "Treść"}], key_points=["Punkt"], review_questions=[])

    async def fake_plan(*args, **kwargs):
        goals.append(args[-1])
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan", overview="Powtórka", steps=[{"day": day, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45} for day in range(1, args[4] + 1)], success_criteria=["Umiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_topic_notes", fake_notes)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    first = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Notatka i plan z algebry"})
    second = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Rozłóż to na pięć dni", "previous_proposal_uid": first.json()["proposal_uid"]})
    assert second.status_code == 200
    assert previous_context[1]["original_request"] == "Notatka i plan z algebry"
    assert all("Notatka i plan z algebry" in goal and "Rozłóż to na pięć dni" in goal for goal in goals[-2:])
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": first.json()["proposal_uid"]}).status_code == 409
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": second.json()["proposal_uid"]}).status_code == 200


def test_t3ach_prompt_revision_changes_answer_preview_and_saved_plan(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-revised-answer")
    goals = []
    previous_context = []

    async def fake_proposal(*args, **kwargs):
        previous_context.append(args[7])
        if args[7]:
            return T3achProposal(reply="Poprawiłem plan zgodnie z prośbą: pięć dni i zadania praktyczne.",
                                 intent="study_plan", subject_name="Matematyka", topic_name="Algebra",
                                 days=5, minutes_per_day=40)
        return T3achProposal(reply="Wstępny plan na sześć dni.", intent="study_plan",
                             subject_name="Matematyka", topic_name="Algebra", days=6, minutes_per_day=40)

    async def fake_plan(*args, **kwargs):
        goals.append(args[-1])
        revised = "Najnowsza poprawka użytkownika" in args[-1]
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan algebry",
                                  overview="Plan z zadaniami praktycznymi" if revised else "Plan wstępny",
                                  steps=[{"day": day, "title": "Ćwiczenia praktyczne" if revised else "Teoria",
                                          "objective": "Przećwicz przykłady", "activities": ["Rozwiąż zadania"],
                                          "duration_minutes": 40} for day in range(1, args[4] + 1)],
                                  success_criteria=["Umiem rozwiązać zadania"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    first = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan algebry na 6 dni po 40 minut"})
    assert first.status_code == 200
    revised = client.post("/ai/t3ach/propose", headers=headers,
                          json={"message": "Poprawka: zrób plan na pięć dni i dodaj zadania praktyczne",
                                "previous_proposal_uid": first.json()["proposal_uid"]})
    assert revised.status_code == 200
    proposal = revised.json()
    assert proposal["days"] == 5
    assert len(proposal["preview"]["steps"]) == 5
    assert proposal["preview"]["steps"][0]["title"] == "Ćwiczenia praktyczne"
    assert "5 dostępnych dni i łącznie 200 minut" in proposal["reply"]
    assert "Plan wstępny" in previous_context[1]["previous_material"]
    assert "pięć dni" in goals[-1]
    assert client.post("/ai/t3ach/execute", headers=headers,
                       json={"proposal_uid": first.json()["proposal_uid"]}).status_code == 409
    saved = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]})
    assert saved.status_code == 200
    assert len(client.get("/plans", headers=headers).json()[0]["days"]) == 5


def test_t3ach_revision_excludes_weekend_and_carries_activities_into_calendar(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-no-weekend")
    start = future_wednesday()
    expected_dates = [(start + timedelta(days=offset)).isoformat() for offset in (0, 1, 2, 5)]
    monkeypatch.setattr(plan_service, "start_date_for", lambda *args: start)

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Plan z zachowaniem pełnego materiału.", intent="study_plan",
                             subject_name="Matematyka", topic_name="Algebra", days=6, minutes_per_day=30)

    async def fake_plan(*args, **kwargs):
        revised = "Najnowsza poprawka użytkownika" in args[-1]
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan", overview="Ćwiczenia", steps=[
            {"day": day, "title": f"Etap {day}", "objective": f"Cel {day}",
             "activities": [f"{'Nowe' if revised else 'Stare'} ćwiczenie {day}"], "duration_minutes": 30}
            for day in range(1, args[4] + 1)
        ], success_criteria=["Umiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    first = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Plan algebry na 6 dni po 30 minut"})
    assert first.status_code == 200
    revised = client.post("/ai/t3ach/propose", headers=headers,
                          json={"message": "Nie mogę w sobotę i niedzielę, przenieś te aktywności na inne dni",
                                "previous_proposal_uid": first.json()["proposal_uid"]})
    assert revised.status_code == 200
    proposal = revised.json()
    assert proposal["excluded_weekdays"] == [5, 6]
    assert proposal["requested_plan_days"] == 6
    steps = proposal["preview"]["steps"]
    assert [step["scheduled_date"] for step in steps] == expected_dates
    assert sum(step["duration_minutes"] for step in steps) == 180
    assert any("Stare ćwiczenie 4" in step["activities"] for step in steps)
    assert any("Stare ćwiczenie 5" in step["activities"] for step in steps)
    saved = client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]})
    assert saved.status_code == 200
    plan = client.get("/plans", headers=headers).json()[0]
    assert [day["scheduled_date"] for day in plan["days"]] == expected_dates
    assert sum(day["duration_minutes"] for day in plan["days"]) == 180
    duplicate = client.post(f"/plans/{plan['plan_uid']}/duplicate", headers=headers, json={"start_date": (start + timedelta(days=7)).isoformat()})
    assert duplicate.status_code == 200
    assert [day["scheduled_date"] for day in duplicate.json()["days"]] == [(start + timedelta(days=7 + offset)).isoformat() for offset in (0, 1, 2, 5)]


def test_direct_plan_generator_respects_unavailable_weekdays_in_goal(client, monkeypatch):
    headers, _ = auth_headers(client, "direct-no-weekend")
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers,
                        json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    start = future_wednesday()
    expected_dates = tuple(start + timedelta(days=offset) for offset in (0, 1, 2, 5))
    monkeypatch.setattr(plan_service, "start_date_for", lambda *args: start)

    async def fake_plan(*args, **kwargs):
        assert kwargs["scheduled_dates"] == expected_dates
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan", overview="Ćwiczenia", steps=[
            {"day": day, "title": f"Etap {day}", "objective": "Ćwicz", "activities": ["Rozwiąż zadania"], "duration_minutes": 30}
            for day in range(1, args[4] + 1)
        ], success_criteria=["Umiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post(f"/ai/topics/{topic['topic_uid']}/plan", headers=headers,
                           json={"days": 6, "minutes_per_day": 30, "custom_goal": "nie moge sobota i niedziela"})
    assert response.status_code == 200
    assert [step["scheduled_date"] for step in response.json()["steps"]] == [day.isoformat() for day in expected_dates]
    assert [step["duration_minutes"] for step in response.json()["steps"]] == [45, 45, 45, 45]


def test_t3ach_tomorrow_survives_clarification_revision_and_save(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-tomorrow")
    contexts = []
    tomorrow = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Warsaw")).date() + timedelta(days=1)

    async def fake_proposal(*args, **kwargs):
        contexts.append(args[6])
        if len(contexts) == 1:
            return T3achProposal(reply="Jaki temat?", question="Jaki temat?", needs_clarification=True,
                                 intent="study_plan", subject_name="Matematyka", days=3, minutes_per_day=30)
        return T3achProposal(reply="Zacznę dziś.", intent="study_plan", subject_name="Matematyka",
                             topic_name="Algebra", days=3, minutes_per_day=30)

    async def fake_plan(*args, **kwargs):
        assert kwargs["start_date"] == tomorrow
        return GeneratedStudyPlan(task_title="Algebra", title="Plan", overview="Nauka",
                                  steps=[{"day": day, "title": "Ćwiczenia", "objective": "Nauka", "activities": ["Zadania"], "duration_minutes": 30}
                                         for day in range(1, args[4] + 1)], success_criteria=["Rozumiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    first = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Plan matematyki od jutra na 3 dni po 30 minut"})
    assert first.status_code == 200
    second = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Algebra, skup się na równaniach", "previous_proposal_uid": first.json()["proposal_uid"]})
    assert second.status_code == 200, second.text
    third = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Dodaj przykłady praktyczne", "previous_proposal_uid": second.json()["proposal_uid"]})
    assert third.status_code == 200, third.text
    proposal = third.json()
    assert len(contexts[-1]) == 4
    assert contexts[-1][2]["text"] == "Algebra, skup się na równaniach"
    assert proposal["plan_start_date"] == tomorrow.isoformat()
    assert "Zacznę dziś" not in proposal["reply"]
    steps = proposal["preview"]["steps"]
    assert [step["day"] for step in steps] == [1, 2, 3]
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]}).status_code == 200
    saved = client.get("/plans", headers=headers).json()[0]
    assert [day["scheduled_date"] for day in saved["days"]] == [step["scheduled_date"] for step in steps]


def test_explicit_plan_dates_and_next_week_exam():
    from app.routers.ai import _plan_start_from_message
    today = date(2026, 9, 30)
    assert _plan_start_from_message("Plan od jutra", today) == date(2026, 10, 1)
    assert _plan_start_from_message("Zacznij pojutrze", today) == date(2026, 10, 2)
    assert _plan_start_from_message("Plan od poniedziałku", today) == date(2026, 10, 5)
    assert _plan_start_from_message("Sprawdzian jutro", today) is None
    assert _exam_date_from_message("Sprawdzian za tydzień w środę", today) == date(2026, 10, 7)
    with pytest.raises(HTTPException):
        plan_service.build_schedule(today, 3, 30, date(2026, 9, 20))


def test_t3ach_rejects_oversized_conversation_turn(client):
    headers, _ = auth_headers(client, "t3ach-limit")
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan algebry", "history": [{"role": "user", "text": "x" * 4001}]})
    assert response.status_code == 422


def test_t3ach_off_topic_returns_reply_without_actions(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-unrelated")

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Pogoda będzie słoneczna.", intent="off_topic", subject_name="Pogoda", tasks=[{"title": "Sprawdź prognozę"}])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Jaka będzie pogoda?"})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["needs_clarification"] is True
    assert proposal["tasks"] == []
    assert proposal["subject_name"] is None
    assert client.post("/ai/t3ach/execute", headers=headers, json={"proposal_uid": proposal["proposal_uid"]}).status_code == 422


def test_t3ach_explains_model_error_instead_of_blame_on_prompt(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-invalid")

    async def invalid_response(*args):
        raise HTTPException(status_code=502, detail="Invalid Gemini response")

    monkeypatch.setattr("app.services.ai._generate_structured", invalid_response)
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan nauki"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Invalid Gemini response"


@pytest.mark.parametrize("status,expected", [
    (403, "klucz API"), (404, "model Gemini"), (429, "limit zapytań"),
    (503, "niedostępny"), (400, "format zapytania"),
])
def test_gemini_errors_explain_cause(status, expected):
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.invalid"))
    exception = httpx.HTTPStatusError("Gemini error", request=response.request, response=response)
    assert expected in ai_service._provider_error(exception)[1]


def test_gemini_incomplete_response_explains_truncation():
    response = httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS"}]}, request=httpx.Request("POST", "https://example.invalid"))
    assert "ucięta" in ai_service._invalid_result_detail(response)


def test_gemini_voice_failure_does_not_blame_generated_answer():
    response = httpx.Response(503, request=httpx.Request("POST", "https://example.invalid"))
    exception = httpx.HTTPStatusError("Gemini voice error", request=response.request, response=response)
    status, detail = ai_service._provider_error(exception, voice=True)
    assert status == 503
    assert "Odpowiedź tekstowa jest gotowa" in detail
    assert "głosu" in detail


def test_plan_preserves_total_time_and_limits_exam_day_to_review():
    schedule = plan_service.build_schedule(date(2026, 9, 30), 6, 30, date(2026, 10, 2))
    assert schedule.days == 3
    assert schedule.total_minutes == 180
    result = GeneratedStudyPlan(task_title="Nauka", title="Plan", overview="Ćwiczenia", steps=[
        {"day": day, "title": "Temat", "objective": "Ćwiczenia", "activities": ["Rozwiąż zadania"], "duration_minutes": 30}
        for day in range(1, 4)
    ], success_criteria=["Umiem"])
    plan_service.apply_schedule(result, schedule)
    assert sum(step.duration_minutes for step in result.steps) == 180
    assert [step.duration_minutes for step in result.steps] == [83, 82, 15]
    assert "powtórka" in result.steps[-1].title.casefold()
    assert "nowych zagadnień" in result.steps[-1].activities[-1]


def test_plan_rejects_ai_response_with_missing_days():
    schedule = plan_service.build_schedule(date(2026, 9, 30), 6, 30)
    result = GeneratedStudyPlan(task_title="Nauka", title="Plan", overview="Ćwiczenia", steps=[
        {"day": day, "title": "Temat", "objective": "Ćwiczenia", "activities": ["Rozwiąż zadania"], "duration_minutes": 30}
        for day in range(1, 4)
    ], success_criteria=["Umiem"])
    with pytest.raises(HTTPException, match="zamiast wymaganych 6"):
        plan_service.apply_schedule(result, schedule)


def test_plan_skips_weekend_and_moves_full_time_to_available_days():
    schedule = plan_service.build_schedule(date(2026, 9, 30), 6, 30, excluded_weekdays={5, 6})
    assert schedule.dates == (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5))
    result = GeneratedStudyPlan(task_title="Nauka", title="Plan", overview="Ćwiczenia", steps=[
        {"day": day, "title": f"Etap {day}", "objective": "Ćwiczenia", "activities": ["Zadania"], "duration_minutes": 30}
        for day in range(1, 5)
    ], success_criteria=["Umiem"])
    plan_service.apply_schedule(result, schedule)
    assert [step.scheduled_date for step in result.steps] == list(schedule.dates)
    assert [step.duration_minutes for step in result.steps] == [45, 45, 45, 45]
    assert sum(step.duration_minutes for step in result.steps) == 180
    assert _weekday_availability("Nie mogę w sobotę i niedzielę") == ({5, 6}, set())
    assert _weekday_availability("nie moge sobota i niedziela") == ({5, 6}, set())
    assert _weekday_availability("W sobotę i niedzielę nie mogę, ale w poniedziałek mogę") == ({5, 6}, {0})
    exam_and_match = "Plan z języka polskiego za tydzień w środę, nie umiem nic i w sobotę nie mogę się uczyć, bo mam mecz"
    blocked, available = _weekday_availability(exam_and_match)
    assert (blocked, available) == ({5}, set())
    assert _mentioned_weekdays(exam_and_match) == {2, 5}
    assert _weekday_availability("w sobotę i w niedzielę nie mogę") == ({5, 6}, set())
    before_weekend_exam = plan_service.build_schedule(date(2026, 9, 30), 6, 30, date(2026, 10, 4), {5, 6})
    assert before_weekend_exam.dates == (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2))
    assert before_weekend_exam.exam_review is False
    assert before_weekend_exam.total_minutes == 180


def test_plan_reads_explicit_budget_and_relative_exam_from_user_message():
    message = "Ułóż plan na 6 dni po 30 minut, sprawdzian za 2 dni"
    assert _explicit_plan_preferences(message) == (6, 30)
    assert _exam_date_from_message(message, date(2026, 9, 30)) == date(2026, 10, 2)


def test_plan_generation_retries_when_ai_omits_days(monkeypatch):
    calls = []

    async def fake_structured(prompt, schema):
        calls.append(prompt)
        days = 3 if len(calls) == 1 else 6
        return GeneratedStudyPlan(task_title="Nauka", title="Plan", overview="Ćwiczenia", steps=[
            {"day": day, "title": "Temat", "objective": "Ćwiczenia", "activities": ["Rozwiąż zadania"], "duration_minutes": 30}
            for day in range(1, days + 1)
        ], success_criteria=["Umiem"])

    monkeypatch.setattr(ai_service, "_generate_structured", fake_structured)
    result = asyncio.run(ai_service.generate_study_plan("Matematyka", "Algebra", None, "polski", 6, 30, start_date=date(2026, 9, 30)))
    assert len(calls) == 2
    assert len(result.steps) == 6


def test_t3ach_keeps_requested_minutes_when_exam_shortens_plan(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-exam-budget")
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Warsaw")).date()
    monkeypatch.setattr(plan_service, "start_date_for", lambda *args: today)

    async def fake_proposal(*args, **kwargs):
        return T3achProposal(reply="Przygotuję plan.", intent="study_plan", subject_name="Matematyka", topic_name="Algebra", days=3, minutes_per_day=30)

    async def fake_plan(*args, **kwargs):
        return GeneratedStudyPlan(task_title="Nauka", title="Plan", overview="Ćwiczenia", steps=[
            {"day": day, "title": "Temat", "objective": "Ćwiczenia", "activities": ["Rozwiąż zadania"], "duration_minutes": 30}
            for day in range(1, args[4] + 1)
        ], success_criteria=["Umiem"])

    monkeypatch.setattr("app.routers.ai.ai_service.generate_t3ach_proposal", fake_proposal)
    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Plan na 6 dni po 30 minut, sprawdzian za 2 dni"})
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["days"] == 3
    assert proposal["requested_plan_days"] == 6
    assert proposal["plan_total_minutes"] == 180
    assert proposal["plan_start_date"] == today.isoformat()
    assert sum(step["duration_minutes"] for step in proposal["preview"]["steps"]) == 180
    assert proposal["preview"]["steps"][-1]["duration_minutes"] == 15


def test_user_can_set_distinct_shortcuts_for_task_and_ai(client):
    headers, _ = auth_headers(client, "two-shortcuts")
    updated = client.patch("/users/me", headers=headers, json={"task_shortcut": "Meta+Shift+J", "ai_shortcut": "Meta+Shift+A"})
    assert updated.status_code == 200
    assert updated.json()["ai_shortcut"] == "Meta+Shift+A"
    assert client.patch("/users/me", headers=headers, json={"ai_shortcut": "Meta+Shift+J"}).status_code == 422
    assert client.patch("/users/me", headers=headers, json={"ai_shortcut": "shift+meta+j"}).status_code == 422
    canonical = client.patch("/users/me", headers=headers, json={"ai_shortcut": "shift+ctrl+a"})
    assert canonical.status_code == 200
    assert canonical.json()["ai_shortcut"] == "Ctrl+Shift+A"
    assert client.patch("/users/me", headers=headers, json={"task_shortcut": "shift+ctrl+a"}).status_code == 422
    assert client.patch("/users/me", headers=headers, json={"ai_shortcut": "Ctrl++"}).status_code == 422
    assert client.get("/users/me", headers=headers).json()["ai_shortcut"] == "Ctrl+Shift+A"


def test_t3ach_even_distribution_preserves_days_budget_notes_and_calendar(client, monkeypatch):
    headers, _ = auth_headers(client, 'even-distribution')
    calls = []
    async def propose(*args, **kwargs):
        # Reproduce the model's erroneous interpretation of the reported 90 minutes.
        return T3achProposal(reply='Stara odpowiedź', intent='notes', material_types=['notes', 'plan'],
                             subject_name='Matematyka', topic_name='Funkcja liniowa', days=5 if args[7] else 7,
                             minutes_per_day=90 if args[7] else 45, excluded_weekdays=[5,6])
    async def notes(*args, **kwargs):
        calls.append('notes')
        return GeneratedNotes(task_title='Funkcja', title='Notatka', summary='Podstawy', sections=[{'heading':'Wzór','content':'y=ax+b'}], key_points=['Współczynniki'])
    async def plan(*args, **kwargs):
        calls.append('plan')
        return GeneratedStudyPlan(task_title='Funkcja', title='Plan', overview='Ćwiczenia',
            steps=[{'day':i+1,'title':f'Etap {i+1}','objective':'Nauka','activities':[f'Ćwiczenie {i+1}'], 'duration_minutes':v}
                   for i,v in enumerate([45,60,60,90,60])],success_criteria=['Rozumiem'])
    monkeypatch.setattr(plan_service, 'start_date_for', lambda *args: future_wednesday())
    monkeypatch.setattr(ai_service,'generate_t3ach_proposal',propose)
    monkeypatch.setattr(ai_service,'generate_topic_notes',notes)
    monkeypatch.setattr(ai_service,'generate_study_plan',plan)
    first=client.post('/ai/t3ach/propose',headers=headers,json={'message':'Plan i notatki na 7 dni po 45 minut, bez weekendu'})
    assert first.status_code == 200, first.text
    before=first.json()
    latest=before
    for message in [
        'Dobra zmienisz mi bo obecnie w planie jest najwięcej czasu poświęcony na Czwarty dzień jest 90 min czy zrobiłbyś mi to bardziej żeby było równomiernie między innymi dniami',
        'Nie miałeś usuwać czwartego dnia, chciałbym bardziej równomiernie żeby czwarty dzień dalej istnieje',
    ]:
        response=client.post('/ai/t3ach/propose',headers=headers,json={'message':message,'previous_proposal_uid':latest['proposal_uid']})
        assert response.status_code == 200, response.text
        latest=response.json()
        assert latest['preview']['notes'] == before['preview']['notes']
        assert latest['requested_plan_days'] == 7
        assert [s['duration_minutes'] for s in latest['preview']['plan']['steps']] == [63]*5
        assert [s['scheduled_date'] for s in latest['preview']['plan']['steps']] == [s['scheduled_date'] for s in before['preview']['plan']['steps']]
        assert [s['activities'] for s in latest['preview']['plan']['steps']] == [s['activities'] for s in before['preview']['plan']['steps']]
        if message.startswith('Dobra'):
            # Simulate a draft saved by the broken version: 3 days, 450 minutes.
            generator = app.dependency_overrides[get_db]()
            db = next(generator)
            row = db.get(models.AiConversation, UUID(latest['proposal_uid']))
            broken = row.proposal.copy()
            broken.pop('_schedule_revision_version', None)
            broken['days'] = 3
            broken['requested_plan_days'] = 5
            broken['minutes_per_day'] = 90
            broken['plan_total_minutes'] = 450
            broken['preview'] = {**broken['preview'], 'plan': {**broken['preview']['plan'], 'steps': [
                {**step, 'duration_minutes': 150} for step in broken['preview']['plan']['steps'][:3]]}}
            row.proposal = broken
            db.commit()
            generator.close()
    assert calls == ['notes','plan']
    assert client.post('/ai/t3ach/execute', headers=headers,json={'proposal_uid':latest['proposal_uid']}).status_code == 200
    saved=client.get('/plans',headers=headers).json()[0]
    assert [d['duration_minutes'] for d in saved['days']] == [63]*5


def test_schedule_mentions_are_not_change_requests():
    from app.routers.ai import _revision_changes_schedule
    message='Czwarty dzień jest 90 min, rozłóż czas równomiernie między dniami'
    assert _explicit_plan_preferences(message) == (None,None)
    assert _revision_changes_schedule(message) == (False,False)
    assert _mentioned_weekdays('Czwarty dzień') == set()
    assert _mentioned_weekdays('W czwartek') == {3}


@pytest.mark.parametrize('kind', ['materials', 'chats'])
def test_ai_history_bulk_delete_is_owned_and_atomic(client, kind):
    headers, user = auth_headers(client, 'bulk-ai')
    other_headers, other = auth_headers(client, 'bulk-ai-other')
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    ids = []
    for owner in [user, user, user, other]:
        if kind == 'chats':
            item = models.AiConversation(user_uid=UUID(owner['user_uid']), title='Rozmowa', user_message='Plan', assistant_message='Podgląd', proposal={})
            db.add(item)
            db.flush()
            ids.append(str(item.conversation_uid))
        else:
            subject = models.Subject(user_uid=UUID(owner['user_uid']), name=f'Przedmiot {len(ids)}')
            db.add(subject)
            db.flush()
            topic = models.Topic(subject_uid=subject.subject_uid, name='Temat')
            db.add(topic)
            db.flush()
            item = models.AiMaterial(user_uid=UUID(owner['user_uid']), topic_uid=topic.topic_uid, material_type='notes', title='Notatka', content={})
            db.add(item)
            db.flush()
            ids.append(str(item.material_uid))
    db.commit()
    generator.close()
    endpoint = '/ai/materials' if kind == 'materials' else '/ai/t3ach/history'
    assert client.post('/ai/history/bulk-delete', headers=headers, json={'kind':kind,'ids':[ids[0],ids[3]]}).status_code == 404
    assert len(client.get(endpoint, headers=headers).json()) == 3
    assert client.post('/ai/history/bulk-delete', headers=headers, json={'kind':kind,'ids':ids[:2]+ids[:1]}).status_code == 204
    assert len(client.get(endpoint, headers=headers).json()) == 1
    assert len(client.get(endpoint, headers=other_headers).json()) == 1
    assert client.post('/ai/history/bulk-delete', headers=headers, json={'kind':kind,'ids':[]}).status_code == 422


def test_result_explanation_uses_finished_preview_and_handles_provider_failure(monkeypatch):
    before = {'steps': [{'day': 4, 'duration_minutes': 90}]}
    after = {'steps': [{'day': 4, 'duration_minutes': 63}]}
    async def generated(prompt, schema):
        assert '90' in prompt and '63' in prompt and 'skróć czwarty dzień' in prompt
        return schema(reply='Skróciłem czwarty dzień z 90 do 63 minut.')
    monkeypatch.setattr(ai_service, '_generate_structured', generated)
    assert asyncio.run(ai_service.explain_t3ach_result('skróć czwarty dzień', [], before, after, 'polski')) == 'Skróciłem czwarty dzień z 90 do 63 minut.'
    async def unavailable(*args):
        raise HTTPException(status_code=503, detail='unavailable')
    monkeypatch.setattr(ai_service, '_generate_structured', unavailable)
    fallback = asyncio.run(ai_service.explain_t3ach_result('skróć czwarty dzień', [], before, after, 'polski'))
    assert '90 → 63' in fallback
