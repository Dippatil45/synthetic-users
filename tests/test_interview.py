"""Tests for the synthetic interview engine (the LLM is always mocked)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.llm import interviewer
from app.llm.client import LLMError
from app.main import app

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
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def _persona_with_psychology(client):
    persona_id = client.post("/personas/generate?count=1").json()[0]["id"]
    client.post("/personas/psychology-pending")
    return persona_id


def test_parse_answers_handles_fences_wrappers_and_bad_output():
    questions = ["Do you shop online?", "What annoys you?"]
    fenced = '```json\n[{"question": "a", "answer": " Yes. "}, {"question": "b", "answer": "Pop-ups."}]\n```'
    assert interviewer.parse_answers(fenced, questions) == [
        {"question": questions[0], "answer": "Yes."},
        {"question": questions[1], "answer": "Pop-ups."},
    ]
    wrapped = json.dumps({"answers": [{"answer": "A1"}, {"answer": "A2"}]})
    assert [a["answer"] for a in interviewer.parse_answers(wrapped, questions)] == ["A1", "A2"]
    for bad in ["no json here", '[{"answer": "only one"}]', '[{"answer": ""}, {"answer": "x"}]']:
        with pytest.raises(LLMError):
            interviewer.parse_answers(bad, questions)


def test_build_prompt_contains_profile_questions_and_memories():
    persona = {"name": "Ana", "demographics": {"age": 50}, "backstory": "Lives in Pune."}
    prompt = interviewer.build_prompt(persona, ["Do you shop online?", "What annoys you?"], ["Q: x A: y"])
    assert "1. Do you shop online?" in prompt and "2. What annoys you?" in prompt
    assert "- Q: x A: y" in prompt
    assert "Lives in Pune." in prompt
    assert "exactly 2 objects" in prompt


def test_interview_saves_answers_and_feeds_memory_back(client, monkeypatch):
    persona_id = _persona_with_psychology(client)
    calls = []

    def fake_interview(persona, questions, memories):
        calls.append(list(memories))
        return [{"question": q, "answer": f"Answer to {q}"} for q in questions]

    monkeypatch.setattr(interviewer, "run_interview", fake_interview)
    first = client.post(
        f"/personas/{persona_id}/interview",
        json={"questions": ["Do you shop online?", "What annoys you?"]},
    )
    assert first.status_code == 200
    assert len(first.json()["answers"]) == 2
    memories = client.get(f"/personas/{persona_id}/memories").json()
    assert len(memories) == 2 and all(m["kind"] == "answer" for m in memories)
    client.post(f"/personas/{persona_id}/interview", json={"questions": ["Anything else?"]})
    assert calls[0] == []
    assert any("Do you shop online?" in memory for memory in calls[1])


def test_interview_errors_and_nothing_saved_on_failure(client, monkeypatch):
    assert client.post("/personas/nope/interview", json={"questions": ["Hi?"]}).status_code == 404
    persona_id = client.post("/personas/generate?count=1").json()[0]["id"]
    assert client.post(f"/personas/{persona_id}/interview", json={"questions": ["Hi?"]}).status_code == 409
    client.post("/personas/psychology-pending")

    def boom(*args, **kwargs):
        raise LLMError("quota")

    monkeypatch.setattr(interviewer, "run_interview", boom)
    assert client.post(f"/personas/{persona_id}/interview", json={"questions": ["Hi?"]}).status_code == 502
    assert client.get(f"/personas/{persona_id}/memories").json() == []
    assert client.post(f"/personas/{persona_id}/interview", json={"questions": []}).status_code == 422
    assert client.post(f"/personas/{persona_id}/interview", json={"questions": ["  "]}).status_code == 422
