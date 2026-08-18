"""Testy aktualnej warstwy SQLAlchemy."""
import os
from datetime import date
import pytest
import functions
from functions import Auth, ask_choice, ask_date, ask_float, ask_int
from data.auth import hash_password, verify_password

def fake_input(monkeypatch, values):
    values = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(values))

class TestInputHelpers:
    def test_ask_date(self, monkeypatch):
        fake_input(monkeypatch, ["2026-08-18"])
        assert ask_date("data") == date(2026, 8, 18)
    def test_ask_int_retries(self, monkeypatch):
        fake_input(monkeypatch, ["abc", "0", "4"])
        assert ask_int("liczba", allow_empty=False, min_value=1) == 4
    def test_ask_float_retries(self, monkeypatch):
        fake_input(monkeypatch, ["101", "42.5"])
        assert ask_float("wynik", allow_empty=False, min_value=0, max_value=100) == 42.5
    def test_ask_choice_normalizes_input(self, monkeypatch):
        fake_input(monkeypatch, ["medium"])
        assert ask_choice("priorytet", ["LOW", "MEDIUM"]) == "MEDIUM"

class TestAuth:
    def test_password_hash_is_not_plaintext(self):
        hashed = hash_password("tajne-haslo")
        assert hashed != "tajne-haslo"
        assert verify_password("tajne-haslo", hashed)
        assert not verify_password("bledne", hashed)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

@pytest.fixture
def database_session():
    if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith("postgresql"):
        pytest.skip("Ustaw TEST_DATABASE_URL na testową bazę PostgreSQL")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from data.database import Base
    from data.models import User, Subject
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="pytest_user", password_hash="hash")
        session.add(user); session.flush()
        subject = Subject(nazwa="matematyka", user_uid=user.user_uid)
        session.add(subject); session.commit()
        yield session, user, subject
    finally:
        session.rollback(); session.close(); Base.metadata.drop_all(engine); engine.dispose()

def test_sqlalchemy_postgres_persists_relationship(database_session):
    session, user, _ = database_session
    from data.models import Subject
    loaded = session.query(Subject).filter_by(user_uid=user.user_uid).one()
    assert loaded.nazwa == "matematyka"
    assert loaded.user_uid == user.user_uid

@pytest.fixture
def app_session(database_session, monkeypatch):
    session, user, subject = database_session
    monkeypatch.setattr(functions, "SessionLocal", lambda: session)
    return session, user, subject

def test_subject_service_add(app_session, monkeypatch):
    session, user, _ = app_session
    fake_input(monkeypatch, ["fizyka", ""])
    functions.SubjectService(user.user_uid).add()
    names = {s.nazwa for s in functions.SubjectService(user.user_uid)._get_all(session)}
    assert names == {"fizyka", "matematyka"}

def test_topic_and_task_persist(app_session, monkeypatch):
    session, user, _ = app_session
    fake_input(monkeypatch, ["algebra", "HARD"])
    functions.TopicService(user.user_uid).add()
    topic = session.query(functions.TopicModel).one()
    fake_input(monkeypatch, ["matematyka", "algebra", "zadanie", "", "HIGH"])
    functions.TaskService(user.user_uid).add()
    session.refresh(topic)
    assert topic.tasks[0].title == "zadanie"
    assert topic.tasks[0].priority.value == "HIGH"

def test_auth_register_and_login(app_session, monkeypatch):
    _, _, _ = app_session
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "jan")
    monkeypatch.setattr("getpass.getpass", lambda *_a, **_k: "haslo")
    uid = Auth().register()
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "jan")
    assert Auth().login() == uid

def test_invalid_exam_score_rejected(app_session):
    session, _, subject = app_session
    from data.models import ExamResult
    from sqlalchemy.exc import IntegrityError
    session.add(ExamResult(subject_uid=subject.subject_uid, exam_date=date.today(), score_percent=101))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
