"""Realism/consistency validation and diversity report (code only, no LLM)."""

import math
import statistics
from collections import Counter

DEGREE_JOBS = {"software_engineer", "accountant", "nurse", "teacher"}
LOW_EDUCATION = {"high_school", "none", "primary", "less_than_high_school"}
AGE_GROUPS = [(18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 200)]


def validate_persona(persona: dict) -> list[dict]:
    """Return realism/consistency issues for one persona (empty list = clean)."""
    demo = persona.get("demographics") or {}
    prof = persona.get("professional") or {}
    beh = persona.get("behavioral") or {}
    psych = persona.get("psychological") or {}
    age, experience = demo.get("age"), prof.get("experience_years")
    occupation, education = prof.get("occupation"), demo.get("education")
    issues = []

    def add(level: str, rule: str) -> None:
        issues.append({"level": level, "rule": rule})

    if isinstance(age, int) and isinstance(experience, int) and experience > age - 18:
        add("error", "experience_years is more than age minus 18")
    if occupation in DEGREE_JOBS and education in LOW_EDUCATION:
        add("error", "occupation normally needs a degree but education is school level")
    if occupation == "student" and demo.get("income_band") == "high":
        add("error", "student with a high income band")
    if occupation == "retired" and isinstance(age, int) and age < 50:
        add("error", "retired before age 50")
    if isinstance(age, int) and age >= 70 and (beh.get("tech_savviness") or 0) >= 9:
        add("warning", "age 70+ with very high tech savviness")
    if not psych:
        add("warning", "psychological profile missing")
    elif (
        beh.get("shopping_habits") == "impulse_buyer"
        and (psych.get("trait_levels") or {}).get("conscientiousness") == "high"
    ):
        add("warning", "impulse buyer with high conscientiousness")
    if not persona.get("backstory"):
        add("warning", "backstory missing")
    return issues


def _age_group(age) -> str:
    for low, high in AGE_GROUPS:
        if isinstance(age, int) and low <= age <= high:
            return f"{low}-{high}" if high < 200 else f"{low}+"
    return "unknown"


def _evenness(counter: Counter) -> float:
    """1.0 = values spread evenly, 0.0 = everyone has the same value."""
    total, kinds = sum(counter.values()), len(counter)
    if kinds <= 1:
        return 0.0
    entropy = -sum((c / total) * math.log(c / total) for c in counter.values())
    return round(entropy / math.log(kinds), 2)


def diversity_report(personas: list[dict]) -> dict:
    """How varied the population is across key attributes and personality traits."""
    getters = {
        "gender": lambda p: (p.get("demographics") or {}).get("gender"),
        "age_group": lambda p: _age_group((p.get("demographics") or {}).get("age")),
        "education": lambda p: (p.get("demographics") or {}).get("education"),
        "income_band": lambda p: (p.get("demographics") or {}).get("income_band"),
        "marital_status": lambda p: (p.get("demographics") or {}).get("marital_status"),
        "location": lambda p: (p.get("demographics") or {}).get("location"),
        "occupation": lambda p: (p.get("professional") or {}).get("occupation"),
        "shopping_habits": lambda p: (p.get("behavioral") or {}).get("shopping_habits"),
        "decision_style": lambda p: (p.get("psychological") or {}).get("decision_style"),
    }
    attributes = {}
    for name, getter in getters.items():
        counter = Counter(v for v in (getter(p) for p in personas) if v)
        attributes[name] = {
            "distinct": len(counter),
            "evenness": _evenness(counter),
            "top": counter.most_common(3),
        }
    big_five = {}
    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        scores = [
            (p.get("psychological") or {}).get("big_five", {}).get(trait)
            for p in personas
        ]
        scores = [s for s in scores if isinstance(s, (int, float))]
        if scores:
            big_five[trait] = {
                "average": round(statistics.mean(scores), 1),
                "spread": round(statistics.pstdev(scores), 1),
            }
    evenness_values = [a["evenness"] for a in attributes.values() if a["distinct"]]
    return {
        "personas": len(personas),
        "attributes": attributes,
        "big_five": big_five,
        "overall_evenness": round(sum(evenness_values) / len(evenness_values), 2) if evenness_values else 0.0,
    }
