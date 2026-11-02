"""Tests for persona lifecycle API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db

# In-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """Create a test client with a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def test_create_then_get_returns_same_persona(client):
    """Test that creating then getting a persona returns the same data."""
    create_data = {
        "name": "Test User",
        "tags": ["test", "sample"],
        "demographics": {
            "age": 30,
            "gender": "female",
            "location": "New York, USA",
            "education": "bachelors",
            "income_band": "middle",
            "marital_status": "single"
        },
        "professional": {
            "occupation": "software_engineer",
            "industry": "technology",
            "experience_years": 5
        },
        "behavioral": {
            "tech_savviness": 8,
            "shopping_habits": "online_primary",
            "brand_loyalty": "medium",
            "preferred_devices": ["smartphone", "laptop"],
            "spending_style": "moderate"
        }
    }
    
    # Create persona
    response = client.post("/personas", json=create_data)
    assert response.status_code == 201
    created = response.json()
    
    assert created["name"] == "Test User"
    assert created["status"] == "draft"
    assert created["version"] == 1
    assert created["tags"] == ["test", "sample"]
    
    # Get persona
    persona_id = created["id"]
    response = client.get(f"/personas/{persona_id}")
    assert response.status_code == 200
    retrieved = response.json()
    
    # Compare key fields
    assert retrieved["id"] == created["id"]
    assert retrieved["name"] == created["name"]
    assert retrieved["demographics"] == created["demographics"]
    assert retrieved["professional"] == created["professional"]
    assert retrieved["behavioral"] == created["behavioral"]


def test_generate_returns_personas_and_list_returns_them(client):
    """Test that generate creates personas with draft status and list returns them."""
    # Generate 5 personas
    response = client.post("/personas/generate?count=5&seed=123")
    assert response.status_code == 200
    generated = response.json()
    
    assert len(generated) == 5
    for persona in generated:
        assert persona["status"] == "draft"
        assert persona["name"].startswith("Synthetic User ")
        assert persona["version"] == 1
    
    # List all personas
    response = client.get("/personas")
    assert response.status_code == 200
    listed = response.json()
    
    assert len(listed) == 5


def test_list_filters_by_status_and_respects_limit_offset(client):
    """Test that list endpoint filters by status and respects limit/offset."""
    # Generate some personas
    client.post("/personas/generate?count=10&seed=456")
    
    # Get all personas and change some to active
    response = client.get("/personas?limit=100")
    all_personas = response.json()
    
    # Change first 4 to active status
    for i in range(4):
        persona_id = all_personas[i]["id"]
        client.patch(f"/personas/{persona_id}", json={"status": "active"})
    
    # Filter by draft status
    response = client.get("/personas?status=draft")
    assert response.status_code == 200
    draft_personas = response.json()
    assert len(draft_personas) == 6
    for p in draft_personas:
        assert p["status"] == "draft"
    
    # Filter by active status
    response = client.get("/personas?status=active")
    assert response.status_code == 200
    active_personas = response.json()
    assert len(active_personas) == 4
    for p in active_personas:
        assert p["status"] == "active"
    
    # Test limit
    response = client.get("/personas?limit=3")
    assert response.status_code == 200
    limited = response.json()
    assert len(limited) == 3
    
    # Test offset
    response = client.get("/personas?limit=3&offset=3")
    assert response.status_code == 200
    offset_result = response.json()
    assert len(offset_result) == 3
    # Should be different personas (no overlap)
    limited_ids = {p["id"] for p in limited}
    offset_ids = {p["id"] for p in offset_result}
    assert limited_ids.isdisjoint(offset_ids)


def test_patch_demographics_bumps_version_tags_does_not(client):
    """Test that patching demographics increments version, but patching tags doesn't."""
    # Create a persona
    create_data = {
        "name": "Version Test",
        "tags": ["original"],
        "demographics": {
            "age": 25,
            "gender": "male",
            "location": "London, UK",
            "education": "masters",
            "income_band": "upper-middle",
            "marital_status": "single"
        },
        "professional": {
            "occupation": "data_scientist",
            "industry": "technology",
            "experience_years": 3
        },
        "behavioral": {
            "tech_savviness": 9,
            "shopping_habits": "online_primary",
            "brand_loyalty": "low",
            "preferred_devices": ["smartphone", "laptop", "tablet"],
            "spending_style": "moderate"
        }
    }
    
    response = client.post("/personas", json=create_data)
    persona = response.json()
    persona_id = persona["id"]
    assert persona["version"] == 1
    
    # Patch only tags - version should stay 1
    response = client.patch(f"/personas/{persona_id}", json={"tags": ["updated", "new"]})
    assert response.status_code == 200
    updated = response.json()
    assert updated["version"] == 1
    assert updated["tags"] == ["updated", "new"]
    
    # Patch demographics - version should increment to 2
    new_demographics = {
        "age": 26,
        "gender": "male",
        "location": "London, UK",
        "education": "masters",
        "income_band": "upper-middle",
        "marital_status": "married"
    }
    response = client.patch(f"/personas/{persona_id}", json={"demographics": new_demographics})
    assert response.status_code == 200
    updated = response.json()
    assert updated["version"] == 2
    assert updated["demographics"]["marital_status"] == "married"


def test_invalid_transition_returns_409_and_delete_returns_404(client):
    """Test that invalid status transition returns 409 and delete then get returns 404."""
    # Create a persona
    create_data = {
        "name": "Transition Test",
        "tags": [],
        "demographics": {
            "age": 40,
            "gender": "female",
            "location": "Tokyo, Japan",
            "education": "bachelors",
            "income_band": "middle",
            "marital_status": "married"
        },
        "professional": {
            "occupation": "teacher",
            "industry": "education",
            "experience_years": 15
        },
        "behavioral": {
            "tech_savviness": 5,
            "shopping_habits": "balanced",
            "brand_loyalty": "high",
            "preferred_devices": ["smartphone"],
            "spending_style": "frugal"
        }
    }
    
    response = client.post("/personas", json=create_data)
    persona = response.json()
    persona_id = persona["id"]
    
    # Valid transition: draft -> active
    response = client.patch(f"/personas/{persona_id}", json={"status": "active"})
    assert response.status_code == 200
    
    # Valid transition: active -> archived
    response = client.patch(f"/personas/{persona_id}", json={"status": "archived"})
    assert response.status_code == 200
    
    # Invalid transition: archived -> draft (not allowed)
    response = client.patch(f"/personas/{persona_id}", json={"status": "draft"})
    assert response.status_code == 409
    assert "Invalid status transition" in response.json()["detail"]
    
    # Delete the persona
    response = client.delete(f"/personas/{persona_id}")
    assert response.status_code == 204
    
    # Try to get deleted persona - should return 404
    response = client.get(f"/personas/{persona_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
