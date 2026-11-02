"""Tests for persona profile sampler."""

import pytest
from app.generation.sampler import sample_profiles
from app.schemas.persona import Demographics, Professional, Behavioral


def test_samples_validate_against_pydantic_models():
    """Test that 200 samples all validate against Pydantic models."""
    profiles = sample_profiles(200, seed=42)
    
    assert len(profiles) == 200
    
    for profile in profiles:
        # These will raise ValidationError if invalid
        Demographics(**profile["demographics"])
        Professional(**profile["professional"])
        Behavioral(**profile["behavioral"])


def test_same_seed_gives_same_output():
    """Test that same seed produces identical output."""
    profiles1 = sample_profiles(50, seed=123)
    profiles2 = sample_profiles(50, seed=123)
    
    assert profiles1 == profiles2


def test_diversity_across_samples():
    """Test diversity: 200 samples have diverse occupations, locations, and ages."""
    profiles = sample_profiles(200, seed=999)
    
    occupations = set()
    locations = set()
    age_brackets = set()
    
    for profile in profiles:
        occupations.add(profile["professional"]["occupation"])
        locations.add(profile["demographics"]["location"])
        
        age = profile["demographics"]["age"]
        if age < 25:
            bracket = "18-24"
        elif age < 35:
            bracket = "25-34"
        elif age < 45:
            bracket = "35-44"
        elif age < 55:
            bracket = "45-54"
        elif age < 65:
            bracket = "55-64"
        else:
            bracket = "65+"
        age_brackets.add(bracket)
    
    assert len(occupations) >= 10, f"Only {len(occupations)} distinct occupations"
    assert len(locations) >= 5, f"Only {len(locations)} distinct locations"
    assert len(age_brackets) >= 5, f"Only {len(age_brackets)} age brackets"


def test_experience_years_realistic_for_age():
    """Test that people aged 40+ who work have realistic experience years."""
    profiles = sample_profiles(200, seed=777)
    
    for profile in profiles:
        age = profile["demographics"]["age"]
        occupation = profile["professional"]["occupation"]
        experience = profile["professional"]["experience_years"]
        
        if age >= 40 and occupation not in ["student", "retired"]:
            assert experience >= 8, (
                f"Person aged {age} with occupation {occupation} has only "
                f"{experience} years of experience (expected >= 8)"
            )


def test_education_requirements_respected():
    """Test that professional occupations have appropriate education levels."""
    profiles = sample_profiles(200, seed=555)
    
    # Occupations requiring at least bachelor's degree
    degree_required = ["software_engineer", "accountant", "teacher"]
    
    for profile in profiles:
        occupation = profile["professional"]["occupation"]
        education = profile["demographics"]["education"]
        
        if occupation in degree_required:
            assert education not in ["high_school"], (
                f"{occupation} has education level {education} "
                f"(expected at least some_college or higher)"
            )
        
        # Nurse can have some_college or higher
        if occupation == "nurse":
            assert education in ["some_college", "bachelors", "masters", "doctorate"], (
                f"Nurse has education level {education} "
                f"(expected at least some_college)"
            )
