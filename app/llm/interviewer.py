"""Synthetic interview: ask a persona several questions in ONE LLM call."""

import json
import re

from app.llm.client import LLMError, generate_text


def build_prompt(persona: dict, questions: list[str], memories: list[str]) -> str:
    """Build the interview prompt from the persona profile, backstory and past statements."""
    profile = {
        key: persona.get(key)
        for key in ("name", "demographics", "professional", "behavioral", "psychological")
    }
    memory_text = "\n".join(f"- {m}" for m in memories) or "- (nothing yet)"
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    return f"""You are role-playing a synthetic user for product research. Stay fully in character as this person.

PERSONA PROFILE (JSON):
{json.dumps(profile, indent=1)}

BACKSTORY:
{persona.get("backstory") or "(none)"}

THINGS THIS PERSON HAS ALREADY SAID (stay consistent, never contradict these):
{memory_text}

INTERVIEW QUESTIONS:
{numbered}

Rules:
- Answer every question in first person, 2 to 4 sentences, in this person's own voice (follow the communication style and decision style in the profile).
- Answers must fit the person's age, job, income, tech comfort, values and pain points.
- Do not mention being an AI or a persona. Do not name real brands.
- Return ONLY a JSON array with exactly {len(questions)} objects, in order: [{{"question": "...", "answer": "..."}}]"""


def parse_answers(text: str, questions: list[str]) -> list[dict]:
    """Turn the LLM reply into one answer per question, or raise LLMError."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise LLMError("Interview response is not a JSON list")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"Interview response is not valid JSON: {exc}")
    if not isinstance(data, list) or len(data) != len(questions):
        raise LLMError("Interview response does not contain one answer per question")
    results = []
    for question, item in zip(questions, data):
        answer = item.get("answer") if isinstance(item, dict) else None
        if not isinstance(answer, str) or not answer.strip():
            raise LLMError("Interview response has an empty answer")
        results.append({"question": question, "answer": answer.strip()})
    return results


def run_interview(persona: dict, questions: list[str], memories: list[str]) -> list[dict]:
    """Ask all questions with a single LLM call and return the parsed answers."""
    return parse_answers(generate_text(build_prompt(persona, questions, memories)), questions)
