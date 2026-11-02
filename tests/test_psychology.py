"""Tests for psychological profiles and persona memory."""

import random
import statistics

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.generation.psychology import VALUE_RULES, generate_psychology, persona_seed
from app.main import app
from app.models.memory import PersonaMemory

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


def make_profile(age=40, tech=5):
    return {
        "demographics": {"age": age, "marital_status": "married", "income_band": "middle"},
        "professional": {"occupation": "accountant"},
        "behavioral": {
            "tech_savviness": tech,
            "shopping_habits": "balanced",
            "brand_loyalty": "medium",
            "spending_style": "moderate",
        },
    }


def _average(trait, **kwargs):
    return statistics.mean(
        generate_psychology(make_profile(**kwargs), random.Random(persona_seed(f"p{i}")))["big_five"][trait]
        for i in range(200)
    )


def test_psychology_profile_is_complete_and_valid():
    result = generate_psychology(make_profile(), random.Random(1))
    assert set(result) == {
        "big_five", "trait_levels", "values", "goals", "pain_points",
        "decision_style", "communication_style", "preferences",
    }
    assert all(1 <= score <= 100 for score in result["big_five"].values())
    assert len(result["values"]) == 3 and len(set(result["values"])) == 3
    assert set(result["values"]) <= set(VALUE_RULES)
    assert len(result["goals"]) == 2
    assert len(result["pain_points"]) == 3 and len(set(result["pain_points"])) == 3
    assert set(result["trait_levels"].values()) <= {"low", "medium", "high"}


def test_psychology_is_reproducible_and_seedable():
    profile = make_profile()
    first = generate_psychology(profile, random.Random(persona_seed("abc")))
    second = generate_psychology(profile, random.Random(persona_seed("abc")))
    other = generate_psychology(profile, random.Random(persona_seed("abc", 7)))
    assert first == second
    assert first != other


def test_psychology_reflects_profile():
    assert _average("conscientiousness", age=60) > _average("conscientiousness", age=25) + 4
    assert _average("openness", tech=9) > _average("openness", tech=2) + 8


def test_psychology_pending_fills_only_missing_profiles(client):
    assert client.post("/personas/generate?count=3").status_code == 200
    first = client.post("/personas/psychology-pending").json()
    assert first["generated"] == 3
    second = client.post("/personas/psychology-pending").json()
    assert second["generated"] == 0
    persona_id = first["persona_ids"][0]
    assert "big_five" in client.get(f"/personas/{persona_id}/psychology").json()
    assert client.get(f"/personas/{persona_id}").json()["version"] == 1


def test_single_psychology_endpoint_and_regenerate(client):
    persona_id = client.post("/personas/generate?count=1").json()[0]["id"]
    assert client.get(f"/personas/{persona_id}/psychology").status_code == 404
    first = client.post(f"/personas/{persona_id}/psychology").json()
    again = client.post(f"/personas/{persona_id}/psychology").json()
    assert first == again
    changed = client.post(f"/personas/{persona_id}/psychology?regenerate=true&seed=5").json()
    assert changed != first
    assert client.get(f"/personas/{persona_id}").json()["version"] == 1
    assert client.post("/personas/does-not-exist/psychology").status_code == 404


def test_memories_add_list_and_delete_with_persona(client):
    persona_id = client.post("/personas/generate?count=1").json()[0]["id"]
    first = client.post(f"/personas/{persona_id}/memories", json={"content": "Likes quick checkout", "kind": "opinion"})
    assert first.status_code == 201
    client.post(f"/personas/{persona_id}/memories", json={"content": "Dislikes pop-up ads"})
    memories = client.get(f"/personas/{persona_id}/memories").json()
    assert [m["content"] for m in memories] == ["Dislikes pop-up ads", "Likes quick checkout"]
    assert client.post(f"/personas/{persona_id}/memories", json={"content": "x", "kind": "bad"}).status_code == 422
    assert client.delete(f"/personas/{persona_id}").status_code == 204
    assert client.get(f"/personas/{persona_id}/memories").status_code == 404
    db = TestingSessionLocal()
    try:
        assert db.query(PersonaMemory).filter(PersonaMemory.persona_id == persona_id).count() == 0
    finally:
        db.close()
