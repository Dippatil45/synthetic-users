"""Psychological profile generator (code only, no LLM calls).

Big Five traits, values, goals, pain points and decision style are derived from
the persona's existing profile plus seeded randomness, so results are diverse,
consistent with the profile, and reproducible.
"""

import hashlib
import random

TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]

INCOME_INDEX = {"low": 0, "lower-middle": 25, "middle": 50, "upper-middle": 75, "high": 100}

# value -> list of (trait, coefficient); weight = 1 + sum(coef * (score - 50) / 50)
VALUE_RULES = {
    "security": [("neuroticism", 0.8), ("openness", -0.6)],
    "family": [("agreeableness", 0.6)],
    "achievement": [("conscientiousness", 0.8)],
    "independence": [("openness", 0.5), ("agreeableness", -0.5)],
    "community": [("extraversion", 0.6), ("agreeableness", 0.5)],
    "creativity": [("openness", 1.0)],
    "tradition": [("openness", -0.8), ("conscientiousness", 0.3)],
    "health": [("conscientiousness", 0.4)],
    "status": [("extraversion", 0.4), ("agreeableness", -0.4)],
    "learning": [("openness", 0.8)],
    "fairness": [("agreeableness", 0.7)],
    "adventure": [("openness", 0.6), ("neuroticism", -0.5), ("extraversion", 0.4)],
}

GOALS = {
    "early": [
        "finish education and start a stable career",
        "become financially independent",
        "build professional skills and a network",
        "save for a first home or a major purchase",
    ],
    "building": [
        "grow income and move up in their career",
        "save for a home or their family's future",
        "find a better work-life balance",
        "build a financial safety net",
    ],
    "established": [
        "secure financial stability for the family",
        "keep making steady career progress",
        "stay healthy and active",
        "prepare for a comfortable retirement",
    ],
    "late": [
        "stay healthy and independent",
        "spend more time with family",
        "keep expenses manageable",
        "stay connected with friends and the community",
    ],
}

GENERIC_PAIN_POINTS = ["hidden fees", "poor customer service", "unreliable products"]


def persona_seed(persona_id: str, seed: int | None = None) -> int:
    """Stable integer seed derived from the persona id (and an optional extra seed)."""
    digest = hashlib.sha256(f"{persona_id}:{seed}".encode()).hexdigest()
    return int(digest[:12], 16)


def _clamp(value: float, low: int = 5, high: int = 95) -> int:
    return int(max(low, min(high, round(value))))


def _level(score: float) -> str:
    if score < 40:
        return "low"
    if score > 60:
        return "high"
    return "medium"


def _weighted_sample(rng: random.Random, items: list, weights: list, k: int) -> list:
    items, weights = list(items), list(weights)
    chosen = []
    for _ in range(min(k, len(items))):
        index = rng.choices(range(len(items)), weights=weights)[0]
        chosen.append(items.pop(index))
        weights.pop(index)
    return chosen


def _life_stage(age: int, occupation: str) -> str:
    if occupation == "student" or age < 25:
        return "early"
    if occupation == "retired" or age >= 65:
        return "late"
    if age < 45:
        return "building"
    return "established"


def generate_psychology(profile: dict, rng: random.Random) -> dict:
    """Build a psychological profile from demographics, professional and behavioral data."""
    demo = profile.get("demographics", {})
    prof = profile.get("professional", {})
    beh = profile.get("behavioral", {})

    age = int(demo.get("age", 35))
    marital = demo.get("marital_status", "")
    income_band = demo.get("income_band", "middle")
    occupation = prof.get("occupation", "")
    tech = int(beh.get("tech_savviness", 5))
    shopping = beh.get("shopping_habits", "")
    loyalty = beh.get("brand_loyalty", "medium")
    spending = beh.get("spending_style", "moderate")

    age_shift = max(-20, min(40, age - 35))

    raw = {trait: rng.gauss(50, 15) for trait in TRAITS}
    raw["openness"] += (tech - 5.5) * 2.5 - age_shift * 0.2
    raw["conscientiousness"] += age_shift * 0.25
    raw["neuroticism"] -= age_shift * 0.2
    raw["agreeableness"] += age_shift * 0.1
    if occupation == "student":
        raw["openness"] += 5
    if shopping == "impulse_buyer":
        raw["extraversion"] += 5
        raw["conscientiousness"] -= 8
    if spending == "frugal":
        raw["conscientiousness"] += 5
    elif spending == "generous":
        raw["conscientiousness"] -= 3

    if shopping == "impulse_buyer":
        raw["conscientiousness"] = min(raw["conscientiousness"], 60)

    if shopping == "impulse_buyer":
        raw["conscientiousness"] = min(raw["conscientiousness"], 60)

    scores = {trait: _clamp(value) for trait, value in raw.items()}
    o, c, e, a, n = (scores[t] for t in TRAITS)

    # Values
    names, weights = [], []
    for value, rules in VALUE_RULES.items():
        weight = 1 + sum(coef * (scores[trait] - 50) / 50 for trait, coef in rules)
        if value == "family" and marital == "married":
            weight += 0.5
        if value == "health" and age >= 50:
            weight += 0.6
        names.append(value)
        weights.append(max(0.1, weight))
    values = _weighted_sample(rng, names, weights, 3)

    # Goals
    goals = rng.sample(GOALS[_life_stage(age, occupation)], 2)

    # Pain points: up to 2 specific to the persona, the rest generic
    specific = []
    if income_band in ("low", "lower-middle"):
        specific += ["rising cost of living", "unexpected expenses"]
    if tech <= 4:
        specific += ["complicated apps and digital payments", "having to learn new technology"]
    if tech >= 8:
        specific += ["slow or buggy software", "products that lack advanced features"]
    if n > 60:
        specific += ["uncertainty about the future", "fear of making the wrong choice"]
    if c > 60:
        specific += ["wasted time", "disorganised processes"]
    if e < 40:
        specific += ["pushy sales or support calls"]
    if age >= 55:
        specific += ["small text and cluttered screens"]
    specific = list(dict.fromkeys(specific))
    pain_points = rng.sample(specific, min(2, len(specific)))
    pain_points += rng.sample(
        [p for p in GENERIC_PAIN_POINTS if p not in pain_points], 3 - len(pain_points)
    )

    # Decision style
    if shopping == "impulse_buyer" or c < 40:
        decision_style = "impulsive, decides quickly based on feeling"
    elif c > 60 and o >= 40:
        decision_style = "analytical, compares options and reads reviews before buying"
    elif loyalty == "high" and o < 50:
        decision_style = "habit-driven, sticks with brands they already trust"
    elif e > 60 or a > 60:
        decision_style = "socially influenced, relies on friends and family"
    else:
        decision_style = "balanced, weighs price against quality"

    #Communication style
    tone = "talkative and expressive" if e > 60 else "reserved and to the point" if e < 40 else "friendly and moderate"
    manner = "diplomatic" if a > 60 else "blunt and willing to disagree" if a < 40 else "straightforward"
    communication_style = f"{tone}, {manner}"

    # Preferences
    income_idx = INCOME_INDEX.get(income_band, 50)
    risk_score = 0.35 * o + 0.35 * (100 - n) + 0.3 * income_idx
    price_score = (100 - income_idx) + (20 if spending == "frugal" else -20 if spending == "generous" else 0)

    return {
        "big_five": scores,
        "trait_levels": {trait: _level(score) for trait, score in scores.items()},
        "values": values,
        "goals": goals,
        "pain_points": pain_points,
        "decision_style": decision_style,
        "communication_style": communication_style,
        "preferences": {
            "risk_tolerance": _level(risk_score),
            "price_sensitivity": _level(price_score * 0.9 + 5),
            "novelty_seeking": _level(o),
        },
    }


