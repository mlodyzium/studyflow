import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.schemas.ai import GeneratedNotes, GeneratedStudyPlan


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
    other_subject = create_subject(client, headers, "Fizyka")
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
        return GeneratedStudyPlan(**{"title": "Plan", "overview": "Plan powtórki.", "steps": [{"day": 1, "title": "Podstawy", "objective": "Zrozumienie", "activities": ["Przeczytaj notatki"], "duration_minutes": 30}], "success_criteria": ["Rozwiązuję przykłady"]})

    monkeypatch.setattr("app.routers.ai.ai_service.generate_study_plan", fake_plan)
    response = client.post(f"/ai/topics/{topic['topic_uid']}/plan", headers=headers, json={"task_uid": task["task_uid"], "days": 5, "minutes_per_day": 30})
    assert response.status_code == 200
    assert response.json()["steps"][0]["day"] == 1
    assert captured["args"][-1] == "Przygotuj się do kartkówki"


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
