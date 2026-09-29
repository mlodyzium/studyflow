import os
from datetime import timedelta
from uuid import UUID
import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db.database import Base, get_db
from app.core.config import Settings
from app.main import app
from app.schemas.ai import GeneratedNotes, GeneratedStudyPlan, T3achProposal
from app.core.config import settings
from app.services import auth as auth_service
from app.services import ai as ai_service


@pytest.fixture()
def client():
    test_database_url = os.getenv("TEST_DATABASE_URL")
    if test_database_url:
        engine = create_engine(test_database_url)
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
    assert duplicate.json()["detail"] == "Subject with this name already exists"

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


def test_generate_study_plan_with_selected_task(client, monkeypatch):
    headers, _ = auth_headers(client)
    subject = create_subject(client, headers)
    topic = client.post("/topics", headers=headers, json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    task = client.post("/tasks", headers=headers, json={"title": "Przygotuj się do kartkówki", "topic_uid": topic["topic_uid"]}).json()
    captured = {}

    async def fake_plan(*args):
        captured["args"] = args
        return GeneratedStudyPlan(**{"task_title": "Powtórka algebry", "title": "Plan", "overview": "Plan powtórki.", "steps": [{"day": 1, "title": "Podstawy", "objective": "Zrozumienie", "activities": ["Przeczytaj notatki"], "duration_minutes": 30}], "success_criteria": ["Rozwiązuję przykłady"]})

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

    async def fake_proposal(*args):
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

    async def fake_proposal(*args):
        return T3achProposal(reply="Ułożę plan.", intent="study_plan", subject_name=" matematyka ", topic_name="wielomiany", target_kind="zadanie", target_name="powtorka wielomianow", tasks=[])

    async def fake_plan(*args):
        return GeneratedStudyPlan(task_title="Powtórka wielomianów", title="Plan wielomianów", overview="Powtórka", steps=[{"day": 1, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45}], success_criteria=["Umiem rozwiązać zadania"])

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

    async def fake_proposal(*args):
        return T3achProposal(reply="Przygotuję notatkę i plan.", intent="notes", material_types=["notes", "plan"], subject_name="Matematyka", topic_name="Algebra", tasks=[{"title": "Nauka algebry"}])

    async def fake_notes(*args):
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka z algebry", summary="Podstawy", sections=[{"heading": "Definicje", "content": "Treść"}], key_points=["Punkt"], review_questions=[])

    async def fake_plan(*args):
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan algebry", overview="Powtórka", steps=[{"day": 1, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45}], success_criteria=["Umiem rozwiązać zadania"])

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

    async def fake_proposal(*args):
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

    async def fake_proposal(*args):
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

    async def fake_proposal(*args):
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

    async def fake_proposal(*args):
        previous_context.append(args[7])
        return T3achProposal(reply="Przygotuję poprawioną notatkę i plan.", intent="notes", material_types=["notes", "plan"], subject_name="Matematyka", topic_name="Algebra", days=5, tasks=[{"title": "Nauka algebry"}])

    async def fake_notes(*args):
        goals.append(args[-1])
        return GeneratedNotes(task_title="Nauka algebry", title="Notatka", summary="Podstawy", sections=[{"heading": "Definicje", "content": "Treść"}], key_points=["Punkt"], review_questions=[])

    async def fake_plan(*args):
        goals.append(args[-1])
        return GeneratedStudyPlan(task_title="Nauka algebry", title="Plan", overview="Powtórka", steps=[{"day": 1, "title": "Podstawy", "objective": "Zrozumieć", "activities": ["Ćwiczenia"], "duration_minutes": 45}], success_criteria=["Umiem"])

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


def test_t3ach_rejects_oversized_conversation_turn(client):
    headers, _ = auth_headers(client, "t3ach-limit")
    response = client.post("/ai/t3ach/propose", headers=headers, json={"message": "Ułóż plan algebry", "history": [{"role": "user", "text": "x" * 501}]})
    assert response.status_code == 422


def test_t3ach_off_topic_returns_reply_without_actions(client, monkeypatch):
    headers, _ = auth_headers(client, "t3ach-unrelated")

    async def fake_proposal(*args):
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


def test_user_can_set_distinct_shortcuts_for_task_and_ai(client):
    headers, _ = auth_headers(client, "two-shortcuts")
    updated = client.patch("/users/me", headers=headers, json={"task_shortcut": "Meta+Shift+J", "ai_shortcut": "Meta+Shift+A"})
    assert updated.status_code == 200
    assert updated.json()["ai_shortcut"] == "Meta+Shift+A"
    assert client.patch("/users/me", headers=headers, json={"ai_shortcut": "Meta+Shift+J"}).status_code == 422
    assert client.get("/users/me", headers=headers).json()["ai_shortcut"] == "Meta+Shift+A"
