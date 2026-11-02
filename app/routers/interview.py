"""Synthetic interview endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import interviewer
from app.llm.client import LLMError
from app.models.memory import PersonaMemory
from app.models.persona import Persona

router = APIRouter(prefix="/personas", tags=["interviews"])

MEMORY_CONTEXT_LIMIT = 15


class InterviewRequest(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=10)
    topic: Optional[str] = None
    save_to_memory: bool = True


@router.post("/{id}/interview")
def interview_persona(id: str, request: InterviewRequest, db: Session = Depends(get_db)):
    """Interview a persona. All questions are answered with ONE LLM call."""
    persona = db.query(Persona).filter(Persona.id == id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    if not persona.psychological:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate the psychological profile first (POST /personas/psychology-pending).",
        )
    questions = [q.strip() for q in request.questions if q.strip()]
    if not questions:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No questions given")

    recent = (
        db.query(PersonaMemory)
        .filter(PersonaMemory.persona_id == id)
        .order_by(PersonaMemory.created_at.desc())
        .limit(MEMORY_CONTEXT_LIMIT)
        .all()
    )
    memories = [m.content for m in reversed(recent)]
    persona_data = {
        "name": persona.name,
        "demographics": persona.demographics,
        "professional": persona.professional,
        "behavioral": persona.behavioral,
        "psychological": persona.psychological,
        "backstory": persona.backstory,
    }

    try:
        answers = interviewer.run_interview(persona_data, questions, memories)
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Interview failed: {exc}")

    if request.save_to_memory:
        for item in answers:
            db.add(
                PersonaMemory(
                    persona_id=id,
                    kind="answer",
                    topic=request.topic or item["question"][:80],
                    content=f"Q: {item['question']} A: {item['answer']}",
                    source="interview",
                )
            )
        db.commit()

    return {
        "persona_id": id,
        "persona_name": persona.name,
        "answers": answers,
        "saved_to_memory": request.save_to_memory,
    }
