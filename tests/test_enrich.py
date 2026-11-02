"""Tests for LLM-based persona enrichment."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.llm.client import LLMError
from app.llm.persona_writer import write_identity

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


def test_write_identity_parses_markdown_and_raises_on_invalid():
    """Test that write_identity parses JSON in markdown code fences and raises on invalid output."""
    profile = {
        "demographics": {"age": 30, "gender": "female", "location": "Paris, France"},
        "professional": {"occupation": "teacher", "industry": "education"},
        "behavioral": {"tech_savviness": 6, "preferred_devices": ["smartphone"]},
    }
    
    # Test 1: Valid JSON wrapped in markdown code fences
    with patch("app.llm.persona_writer.generate_text") as mock_generate:
        mock_generate.return_value = '''```json
{
  "name": "Marie Dubois",
  "backstory": "Marie is a dedicated teacher who lives in Paris. She enjoys her work with students and uses technology moderately in her classroom. In her free time, she shops online for books and educational materials, preferring convenience over brand loyalty. She dreams of writing her own textbook someday."
}
```'''
        result = write_identity(profile)
        assert result["name"] == "Marie Dubois"
        assert "Marie" in result["backstory"]
        assert len(result["backstory"]) > 50
    
    # Test 2: Valid JSON without code fences
    with patch("app.llm.persona_writer.generate_text") as mock_generate:
        mock_generate.return_value = '{"name": "Sophie Martin", "backstory": "Sophie teaches mathematics at a secondary school in Paris. She balances traditional teaching methods with digital tools, using her smartphone to organize lesson plans and communicate with parents. She shops locally for everyday items but orders specialized teaching materials online."}'
        result = write_identity(profile)
        assert result["name"] == "Sophie Martin"
        assert "Sophie" in result["backstory"]
    
    # Test 3: Missing name field - should raise LLMError
    with patch("app.llm.persona_writer.generate_text") as mock_generate:
        mock_generate.return_value = '{"backstory": "Some backstory text here"}'
        with pytest.raises(LLMError, match="missing 'name' field"):
            write_identity(profile)
    
    # Test 4: Missing backstory field - should raise LLMError
    with patch("app.llm.persona_writer.generate_text") as mock_generate:
        mock_generate.return_value = '{"name": "Test Name"}'
        with pytest.raises(LLMError, match="missing 'backstory' field"):
            write_identity(profile)
    
    # Test 5: Invalid JSON - should raise LLMError
    with patch("app.llm.persona_writer.generate_text") as mock_generate:
        mock_generate.return_value = "This is not JSON at all"
        with pytest.raises(LLMError, match="Failed to parse"):
            write_identity(profile)


def test_enrich_endpoint_updates_name_and_backstory_keeps_version_status(client):
    """Test that POST /personas/{id}/enrich updates name and backstory without changing version or status."""
    # Create a persona
    create_data = {
        "name": "Temp Name",
        "tags": ["test"],
        "demographics": {
            "age": 35,
            "gender": "male",
            "location": "Tokyo, Japan",
            "education": "bachelors",
            "income_band": "middle",
            "marital_status": "married"
        },
        "professional": {
            "occupation": "software_engineer",
            "industry": "technology",
            "experience_years": 10
        },
        "behavioral": {
            "tech_savviness": 9,
            "shopping_habits": "online_primary",
            "brand_loyalty": "low",
            "preferred_devices": ["smartphone", "laptop"],
            "spending_style": "moderate"
        }
    }
    
    response = client.post("/personas", json=create_data)
    assert response.status_code == 201
    persona = response.json()
    persona_id = persona["id"]
    original_version = persona["version"]
    original_status = persona["status"]
    
    # Mock the LLM response
    mock_identity = {
        "name": "Takeshi Yamamoto",
        "backstory": "Takeshi is a skilled software engineer working for a tech startup in Tokyo. He spends his days coding and collaborating with his team using the latest development tools. After work, he unwinds by shopping online for gadgets and tech accessories, always seeking the best deals rather than sticking to particular brands. His goal is to lead his own development team within the next two years."
    }
    
    with patch("app.llm.persona_writer.write_identity") as mock_write:
        mock_write.return_value = mock_identity
        
        # Enrich the persona
        response = client.post(f"/personas/{persona_id}/enrich")
        assert response.status_code == 200
        enriched = response.json()
        
        # Verify name and backstory updated
        assert enriched["name"] == "Takeshi Yamamoto"
        assert enriched["backstory"] == mock_identity["backstory"]
        
        # Verify version and status unchanged
        assert enriched["version"] == original_version
        assert enriched["status"] == original_status


def test_enrich_with_llm_error_returns_502_and_persona_unchanged(client):
    """Test that when write_identity raises LLMError, enrich returns 502 and persona is unchanged."""
    # Create a persona
    create_data = {
        "name": "Original Name",
        "tags": [],
        "demographics": {
            "age": 28,
            "gender": "female",
            "location": "Berlin, Germany",
            "education": "masters",
            "income_band": "upper-middle",
            "marital_status": "single"
        },
        "professional": {
            "occupation": "data_scientist",
            "industry": "technology",
            "experience_years": 5
        },
        "behavioral": {
            "tech_savviness": 8,
            "shopping_habits": "online_primary",
            "brand_loyalty": "medium",
            "preferred_devices": ["laptop", "smartphone"],
            "spending_style": "moderate"
        }
    }
    
    response = client.post("/personas", json=create_data)
    assert response.status_code == 201
    persona = response.json()
    persona_id = persona["id"]
    original_name = persona["name"]
    
    # Mock write_identity to raise LLMError
    with patch("app.llm.persona_writer.write_identity") as mock_write:
        mock_write.side_effect = LLMError("LLM API request failed")
        
        # Try to enrich - should return 502
        response = client.post(f"/personas/{persona_id}/enrich")
        assert response.status_code == 502
        assert "Failed to generate persona identity" in response.json()["detail"]
    
    # Verify persona is unchanged
    response = client.get(f"/personas/{persona_id}")
    assert response.status_code == 200
    unchanged = response.json()
    assert unchanged["name"] == original_name
    assert unchanged["backstory"] is None
