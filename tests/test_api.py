import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.database import Base, get_db
from app.main import app

@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    def override_db():
        with TestingSession() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as api_client:
        yield api_client
    app.dependency_overrides.clear()

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

def test_full_study_flow(client):
    user = client.post("/users", json={"username": "student", "password": "secret123", "email": "student@example.com"}).json()
    subject = client.post("/subjects", json={"name": "Matematyka", "user_uid": user["user_uid"]}).json()
    topic = client.post("/topics", json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    response = client.post("/tasks", json={"title": "Powtórzyć równania", "topic_uid": topic["topic_uid"], "priority": "HIGH"})
    assert response.status_code == 201
    task = response.json()
    completed = client.patch(f"/tasks/{task['task_uid']}", json={"is_done": True})
    assert completed.status_code == 200
    assert completed.json()["is_done"] is True
    assert len(client.get("/tasks", params={"topic_uid": topic["topic_uid"]}).json()) == 1

def create_tree(client, suffix=""):
    user = client.post("/users", json={"username": f"student{suffix}", "password": "secret123"}).json()
    subject = client.post("/subjects", json={"name": "Math", "user_uid": user["user_uid"]}).json()
    topic = client.post("/topics", json={"name": "Algebra", "subject_uid": subject["subject_uid"]}).json()
    task = client.post("/tasks", json={"title": "Equations", "topic_uid": topic["topic_uid"]}).json()
    return user, subject, topic, task

@pytest.mark.parametrize(
    ("resource", "uid_field", "update_body", "updated_field", "updated_value"),
    [
        ("users", "user_uid", {"username": "updated-user"}, "username", "updated-user"),
        ("subjects", "subject_uid", {"name": "Physics"}, "name", "Physics"),
        ("topics", "topic_uid", {"name": "Geometry", "is_done": True}, "name", "Geometry"),
        ("tasks", "task_uid", {"title": "New title"}, "title", "New title"),
    ],
)
def test_get_and_update_every_resource(
    client, resource, uid_field, update_body, updated_field, updated_value
):
    records = create_tree(client, resource)
    record = dict(zip(("users", "subjects", "topics", "tasks"), records))[resource]
    uid = record[uid_field]

    assert client.get(f"/{resource}/{uid}").status_code == 200
    response = client.patch(f"/{resource}/{uid}", json=update_body)
    assert response.status_code == 200
    assert response.json()[updated_field] == updated_value

@pytest.mark.parametrize(
    ("resource", "uid_field"),
    [
        ("tasks", "task_uid"),
        ("topics", "topic_uid"),
        ("subjects", "subject_uid"),
        ("users", "user_uid"),
    ],
)
def test_delete_every_resource(client, resource, uid_field):
    records = create_tree(client, f"delete-{resource}")
    record = dict(zip(("users", "subjects", "topics", "tasks"), records))[resource]
    uid = record[uid_field]

    assert client.delete(f"/{resource}/{uid}").status_code == 204
    assert client.get(f"/{resource}/{uid}").status_code == 404

@pytest.mark.parametrize("resource", ["users", "subjects", "topics", "tasks"])
def test_unknown_resource_returns_404(client, resource):
    response = client.get(f"/{resource}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_duplicate_username_returns_409(client):
    payload = {"username": "duplicate", "password": "secret123"}
    assert client.post("/users", json=payload).status_code == 201
    assert client.post("/users", json=payload).status_code == 409

def test_password_can_be_changed_but_is_never_returned(client):
    response = client.post("/users", json={"username": "secure-user", "password": "first-password"})
    assert response.status_code == 201
    user = response.json()
    assert "password" not in user
    assert "password_hash" not in user

    updated = client.patch(
        f"/users/{user['user_uid']}", json={"password": "second-password"}
    )
    assert updated.status_code == 200
    assert "password_hash" not in updated.json()
