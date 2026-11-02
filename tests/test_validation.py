"""Tests for validation rules and the diversity report."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.validation import diversity_report, validate_persona

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


def make_persona(**changes):
    persona = {
        "demographics": {"age": 45, "education": "bachelors", "income_band": "middle"},
        "professional": {"occupation": "accountant", "experience_years": 20},
        "behavioral": {"tech_savviness": 5, "shopping_habits": "balanced"},
        "psychological": {"trait_levels": {"conscientiousness": "medium"}},
        "backstory": "Lives in Pune.",
    }
    for key, value in changes.items():
        persona[key] = {**persona[key], **value} if isinstance(value, dict) else value
    return persona


def rules(persona):
    return {issue["rule"] for issue in validate_persona(persona)}


def test_clean_persona_has_no_issues():
    assert validate_persona(make_persona()) == []


def test_contradictions_are_flagged():
    assert "experience_years is more than age minus 18" in rules(
        make_persona(demographics={"age": 30}, professional={"experience_years": 20})
    )
    assert "occupation normally needs a degree but education is school level" in rules(
        make_persona(demographics={"education": "high_school"})
    )
    assert "student with a high income band" in rules(
        make_persona(demographics={"income_band": "high"}, professional={"occupation": "student"})
    )
    assert "retired before age 50" in rules(
        make_persona(demographics={"age": 45}, professional={"occupation": "retired"})
    )
    missing = rules(make_persona(psychological=None, backstory=None))
    assert {"psychological profile missing", "backstory missing"} <= missing


def test_diversity_report_evenness_and_empty_input():
    mixed = diversity_report([{"demographics": {"gender": "female"}}, {"demographics": {"gender": "male"}}])
    assert mixed["attributes"]["gender"]["distinct"] == 2
    assert mixed["attributes"]["gender"]["evenness"] == 1.0
    same = diversity_report([{"demographics": {"gender": "male"}}] * 3)
    assert same["attributes"]["gender"]["evenness"] == 0.0
    empty = diversity_report([])
    assert empty["personas"] == 0 and empty["overall_evenness"] == 0.0


def test_validation_report_endpoint(client):
    client.post("/personas/generate?count=4")
    client.post("/personas/psychology-pending")
    data = client.get("/validation/report").json()
    assert data["personas_checked"] == 4
    assert data["diversity"]["personas"] == 4
    assert {"personas_with_errors", "personas_with_warnings", "issues"} <= set(data)
