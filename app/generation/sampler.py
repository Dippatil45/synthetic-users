"""Persona profile sampling with realistic correlations."""

import random
from typing import Any
from app.generation import distributions as dist


def _weighted_choice(rng: random.Random, items: list[tuple[Any, float]]) -> Any:
    """Select an item based on weights."""
    values, weights = zip(*items)
    return rng.choices(values, weights=weights, k=1)[0]


def _parse_age_bracket(bracket: str) -> tuple[int, int]:
    """Parse age bracket string to min/max ages."""
    if bracket == "65+":
        return (65, 85)
    parts = bracket.split("-")
    return (int(parts[0]), int(parts[1]))


def _sample_age_from_bracket(rng: random.Random, bracket: str) -> int:
    """Sample a specific age from an age bracket."""
    min_age, max_age = _parse_age_bracket(bracket)
    return rng.randint(min_age, max_age)


def _get_start_age(education: str) -> int:
    """Get typical start age for a given education level."""
    start_ages = {
        "high_school": 18,
        "some_college": 20,
        "bachelors": 22,
        "masters": 24,
        "doctorate": 27,
    }
    return start_ages.get(education, 18)


def _sample_education_for_age(rng: random.Random, age: int) -> str:
    """Sample education level based on age."""
    if age < 20:
        # Under 20: only high school
        return "high_school"
    elif age < 22:
        # 20-21: high school or some college
        return _weighted_choice(rng, [
            ("high_school", 0.6),
            ("some_college", 0.4),
        ])
    elif age < 24:
        # 22-23: can have up to bachelor's
        return _weighted_choice(rng, [
            ("high_school", 0.2),
            ("some_college", 0.3),
            ("bachelors", 0.5),
        ])
    elif age < 27:
        # 24-26: can have up to master's
        return _weighted_choice(rng, [
            ("high_school", 0.15),
            ("some_college", 0.15),
            ("bachelors", 0.50),
            ("masters", 0.20),
        ])
    else:
        # 27+: any education level
        return _weighted_choice(rng, dist.EDUCATION)


def _meets_education_requirement(education: str, min_education: str | None) -> bool:
    """Check if education meets minimum requirement for occupation."""
    if min_education is None:
        return True
    
    edu_level = dist.EDUCATION_LEVELS.get(education, 0)
    min_level = dist.EDUCATION_LEVELS.get(min_education, 0)
    return edu_level >= min_level


def _select_occupation_for_age_and_education(
    rng: random.Random, age: int, education: str
) -> tuple[str, str, int, str | None]:
    """
    Select occupation based on age and education.
    Returns (occupation, industry, base_income, min_education).
    """
    if age < 25:
        # Young people are mostly students or entry-level
        candidates = [
            ("student", "education", 0, None),
            ("retail_worker", "retail", 1, None),
            ("restaurant_server", "hospitality", 1, None),
            ("customer_service_rep", "service", 1, None),
            ("it_support", "technology", 2, "some_college"),
        ]
        # Filter by education
        valid = [c for c in candidates if _meets_education_requirement(education, c[3])]
        return rng.choice(valid)
    elif age >= 65:
        # 65+ are mostly retired, but some still work
        if rng.random() < 0.7:
            return ("retired", "none", 1, None)
        else:
            # Working seniors - experienced professionals
            candidates = [
                ("professor", "education", 3, "doctorate"),
                ("doctor", "healthcare", 4, "doctorate"),
                ("business_consultant", "business", 3, "bachelors"),
                ("small_business_owner", "business", 2, None),
            ]
            valid = [c for c in candidates if _meets_education_requirement(education, c[3])]
            if valid:
                return rng.choice(valid)
            else:
                # Fallback to business owner if education doesn't match
                return ("small_business_owner", "business", 2, None)
    else:
        # 25-64: filter occupations by education requirement
        non_student = [occ for occ in dist.OCCUPATIONS if occ[0] not in ["student", "retired"]]
        valid = [occ for occ in non_student if _meets_education_requirement(education, occ[3])]
        if valid:
            return rng.choice(valid)
        else:
            # Fallback to any-education jobs
            any_edu = [occ for occ in non_student if occ[3] is None]
            return rng.choice(any_edu)


def _calculate_experience_years(
    rng: random.Random, age: int, education: str, occupation: str
) -> int:
    """Calculate realistic experience years based on age, education, and occupation."""
    if occupation == "student":
        # Students: 0 to 2 years of experience
        return rng.randint(0, 2)
    
    start_age = _get_start_age(education)
    
    if occupation == "retired":
        # Retired people: former working years (age - start_age - random 5 to 10)
        years_since_start = age - start_age
        retirement_offset = rng.randint(5, 10)
        return max(0, years_since_start - retirement_offset)
    
    # Regular workers: age - start_age - random 0 to 3
    years_since_start = age - start_age
    random_offset = rng.randint(0, 3)
    return max(0, years_since_start - random_offset)


def _adjust_income_for_occupation_and_experience(
    rng: random.Random, 
    base_income: int, 
    experience_years: int,
    occupation: str
) -> str:
    """Adjust income band based on occupation base and experience."""
    if occupation == "student":
        return "low"
    if occupation == "retired":
        # Retired people have varied income from pensions/savings
        return _weighted_choice(rng, [
            ("low", 0.3),
            ("lower-middle", 0.4),
            ("middle", 0.3),
        ])
    
    # Adjust base income by experience
    if experience_years > 15:
        base_income = min(4, base_income + 1)
    elif experience_years > 8:
        base_income = min(4, base_income)
    elif experience_years < 3:
        base_income = max(0, base_income - 1)
    
    # Add some randomness
    base_income = max(0, min(4, base_income + rng.choice([-1, 0, 0, 1])))
    
    income_levels = ["low", "lower-middle", "middle", "upper-middle", "high"]
    return income_levels[base_income]


def _sample_tech_savviness(rng: random.Random, age: int) -> int:
    """Sample tech savviness with age correlation."""
    if age < 25:
        base = 8
    elif age < 35:
        base = 7
    elif age < 45:
        base = 6
    elif age < 55:
        base = 5
    elif age < 65:
        base = 4
    else:
        base = 3
    
    # Add noise
    value = base + rng.randint(-2, 2)
    return max(1, min(10, value))


def _sample_devices(rng: random.Random, tech_savviness: int) -> list[str]:
    """Sample preferred devices based on tech savviness."""
    # Everyone has at least smartphone
    devices = ["smartphone"]
    
    # Higher tech savviness = more devices
    num_additional = min(tech_savviness // 3, len(dist.PREFERRED_DEVICES) - 1)
    if num_additional > 0:
        available = [d for d in dist.PREFERRED_DEVICES if d != "smartphone"]
        num_to_add = rng.randint(1, num_additional + 1)
        devices.extend(rng.sample(available, min(num_to_add, len(available))))
    
    return devices


def sample_profile(rng: random.Random) -> dict:
    """
    Sample a single persona profile with realistic correlations.
    
    Sampling order: age -> education -> occupation -> experience_years -> income_band.
    
    Returns a dict with keys: demographics, professional, behavioral.
    The dict validates against Demographics, Professional, Behavioral Pydantic models.
    """
    # 1. Sample age first
    age_bracket = _weighted_choice(rng, dist.AGE_BRACKETS)
    age = _sample_age_from_bracket(rng, age_bracket)
    
    # 2. Sample education based on age
    education = _sample_education_for_age(rng, age)
    
    # 3. Sample occupation based on age and education
    occupation, industry, base_income, min_education = _select_occupation_for_age_and_education(
        rng, age, education
    )
    
    # 4. Calculate experience years based on age, education, and occupation
    experience_years = _calculate_experience_years(rng, age, education, occupation)
    
    # 5. Calculate income band based on occupation and experience
    income_band = _adjust_income_for_occupation_and_experience(
        rng, base_income, experience_years, occupation
    )
    
    # Other demographics
    gender = _weighted_choice(rng, dist.GENDER)
    location = _weighted_choice(rng, dist.LOCATION)
    marital_status = _weighted_choice(rng, dist.MARITAL_STATUS)
    
    # Behavioral - tech savviness correlated with age
    tech_savviness = _sample_tech_savviness(rng, age)
    shopping_habits = _weighted_choice(rng, dist.SHOPPING_HABITS)
    brand_loyalty = _weighted_choice(rng, dist.BRAND_LOYALTY)
    spending_style = _weighted_choice(rng, dist.SPENDING_STYLE)
    preferred_devices = _sample_devices(rng, tech_savviness)
    
    return {
        "demographics": {
            "age": age,
            "gender": gender,
            "location": location,
            "education": education,
            "income_band": income_band,
            "marital_status": marital_status,
        },
        "professional": {
            "occupation": occupation,
            "industry": industry,
            "experience_years": experience_years,
        },
        "behavioral": {
            "tech_savviness": tech_savviness,
            "shopping_habits": shopping_habits,
            "brand_loyalty": brand_loyalty,
            "preferred_devices": preferred_devices,
            "spending_style": spending_style,
        },
    }


def sample_profiles(n: int, seed: int | None = None) -> list[dict]:
    """
    Sample n persona profiles.
    
    Args:
        n: Number of profiles to generate
        seed: Random seed for reproducibility
        
    Returns:
        List of profile dicts
    """
    rng = random.Random(seed)
    return [sample_profile(rng) for _ in range(n)]
