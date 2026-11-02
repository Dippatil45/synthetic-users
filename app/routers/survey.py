"""Survey endpoint: ask the same questions to many personas (one LLM call per persona)."""

import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.llm import interviewer
from app.llm.client import LLMError
from app.models.memory import PersonaMemory
from app.models.persona import Persona

router = APIRouter(prefix="/surveys", tags=["surveys"])

MEMORY_CONTEXT_LIMIT = 15
RATING_PREFIX = (
    "On a scale of 1 to 5 (1 = strongly disagree, 5 = strongly agree), how much do you agree "
    "with this statement? Start your answer with the number, then explain in one sentence: "
)


class SurveyRequest(BaseModel):
    questions: list[str] = Field(default_factory=list, max_length=8)
    rating_statements: list[str] = Field(default_factory=list, max_length=8)
    persona_ids: Optional[list[str]] = None
    limit: int = Field(default=5, ge=1, le=20)
    save_to_memory: bool = True


def extract_rating(answer: str) -> Optional[int]:
    """First standalone digit 1-5 in the answer, or None."""
    match = re.search(r"\b([1-5])\b", answer)
    return int(match.group(1)) if match else None


@router.post("/run")
def run_survey(request: SurveyRequest, db: Session = Depends(get_db)):
    """Run a survey: one LLM call per persona. Rating statements are scored 1-5 and averaged."""
    questions = [q.strip() for q in request.questions if q.strip()]
    statements = [s.strip() for s in request.rating_statements if s.strip()]
    all_questions = questions + [RATING_PREFIX + s for s in statements]
    if not all_questions or len(all_questions) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Give between 1 and 10 questions and rating statements in total",
        )

    query = db.query(Persona).order_by(Persona.created_at.desc())
    if request.persona_ids:
        query = query.filter(Persona.id.in_(request.persona_ids))
    candidates = query.all()
    selected = [p for p in candidates if p.psychological]
    if not request.persona_ids:
        selected = selected[: request.limit]
    skipped = [p.id for p in candidates if not p.psychological]
    if request.persona_ids:
        skipped += [i for i in request.persona_ids if i not in {p.id for p in candidates}]

    responses, failed = [], []
    for index, persona in enumerate(selected):
        recent = (
            db.query(PersonaMemory)
            .filter(PersonaMemory.persona_id == persona.id)
            .order_by(PersonaMemory.created_at.desc())
            .limit(MEMORY_CONTEXT_LIMIT)
            .all()
        )
        persona_data = {
            "name": persona.name,
            "demographics": persona.demographics,
            "professional": persona.professional,
            "behavioral": persona.behavioral,
            "psychological": persona.psychological,
            "backstory": persona.backstory,
        }
        try:
            answers = interviewer.run_interview(
                persona_data, all_questions, [m.content for m in reversed(recent)]
            )
        except LLMError:
            failed.append(persona.id)
            continue
        if request.save_to_memory:
            for item in answers:
                db.add(
                    PersonaMemory(
                        persona_id=persona.id,
                        kind="answer",
                        topic="survey",
                        content=f"Q: {item['question']} A: {item['answer']}",
                        source="survey",
                    )
                )
            db.commit()
        ratings = [extract_rating(a["answer"]) for a in answers[len(questions):]]
        responses.append(
            {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "answers": [
                    {"question": q, "answer": a["answer"]} for q, a in zip(questions, answers)
                ],
                "ratings": dict(zip(statements, ratings)),
            }
        )
        if index < len(selected) - 1:
            time.sleep(settings.LLM_DELAY_SECONDS)

    summary = {}
    for statement in statements:
        values = [r["ratings"][statement] for r in responses if r["ratings"].get(statement)]
        summary[statement] = {
            "average": round(sum(values) / len(values), 2) if values else None,
            "count": len(values),
        }
    return {
        "personas_asked": len(responses),
        "failed": failed,
        "skipped_without_psychology": skipped,
        "rating_summary": summary,
        "responses": responses,
    }
