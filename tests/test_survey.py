"""Tests for the survey engine (the LLM is always mocked)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.llm import interviewer
from app.llm.client import LLMError
from app.main import app
from app.routers.survey import extract_rating

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DELAY_SECONDS", 0)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def test_extract_rating_finds_first_standalone_digit():
    assert extract_rating("4. I would trust it") == 4
    assert extract_rating("I'd say it's a 2 out of 5") == 2
    assert extract_rating("In my 30s, no.") is None
    assert extract_rating("Maybe") is None


def test_survey_averages_ratings_and_saves_memories(client, monkeypatch):
    client.post("/personas/generate?count=3")
    client.post("/personas/psychology-pending")

    def fake_interview(persona, questions, memories):
        return [{"question": q, "answer": "4. Fine." if "scale of 1 to 5" in q else "My answer."} for q in questions]

    monkeypatch.setattr(interviewer, "run_interview", fake_interview)
    body = {
        "questions": ["How do you shop?"],
        "rating_statements": ["I trust new apps"],
        "limit": 2,
    }
    result = client.post("/surveys/run", json=body)
    assert result.status_code == 200
    data = result.json()
    assert data["personas_asked"] == 2 and data["failed"] == []
    assert data["rating_summary"]["I trust new apps"] == {"average": 4.0, "count": 2}
    persona_id = data["responses"][0]["persona_id"]
    assert len(client.get(f"/personas/{persona_id}/memories").json()) == 2


def test_survey_continues_after_failure_and_skips_personas_without_psychology(client, monkeypatch):
    client.post("/personas/generate?count=3")
    client.post("/personas/psychology-pending?limit=2")
    calls = {"count": 0}

    def flaky_interview(persona, questions, memories):
        calls["count"] += 1
        if calls["count"] == 2:
            raise LLMError("quota")
        return [{"question": q, "answer": "Fine."} for q in questions]

    monkeypatch.setattr(interviewer, "run_interview", flaky_interview)
    data = client.post("/surveys/run", json={"questions": ["Hi?"], "limit": 5}).json()
    assert data["personas_asked"] == 1
    assert len(data["failed"]) == 1
    assert len(data["skipped_without_psychology"]) == 1
    assert client.post("/surveys/run", json={}).status_code == 422
