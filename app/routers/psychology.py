"""Psychological profile generation and persona memory endpoints."""

import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.generation.psychology import generate_psychology, persona_seed
from app.models.memory import PersonaMemory
from app.models.persona import Persona
from app.schemas.memory import MemoryCreate, MemoryRead

router = APIRouter(prefix="/personas", tags=["psychology and memory"])


def _get_persona(db: Session, persona_id: str) -> Persona:
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    return persona


def _fill_psychology(persona: Persona, seed: Optional[int] = None) -> dict:
    profile = {
        "demographics": persona.demographics,
        "professional": persona.professional,
        "behavioral": persona.behavioral,
    }
    rng = random.Random(persona_seed(persona.id, seed))
    persona.psychological = generate_psychology(profile, rng)
    return persona.psychological


@router.post("/psychology-pending")
def psychology_pending(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Generate psychological profiles for personas that do not have one yet (no LLM used)."""
    personas = db.query(Persona).order_by(Persona.created_at.desc()).all()
    pending = [p for p in personas if not p.psychological][:limit]
    for persona in pending:
        _fill_psychology(persona)
    db.commit()
    return {"generated": len(pending), "persona_ids": [p.id for p in pending]}


@router.post("/{id}/psychology")
def generate_persona_psychology(
    id: str,
    regenerate: bool = False,
    seed: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Generate the psychological profile for one persona. Does not change version or status."""
    persona = _get_persona(db, id)
    if persona.psychological and not regenerate:
        return persona.psychological
    result = _fill_psychology(persona, seed)
    db.commit()
    return result


@router.get("/{id}/psychology")
def get_persona_psychology(id: str, db: Session = Depends(get_db)):
    """Return the stored psychological profile (404 if not generated yet)."""
    persona = _get_persona(db, id)
    if not persona.psychological:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Psychological profile not generated yet"
        )
    return persona.psychological


@router.post("/{id}/memories", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def add_memory(id: str, data: MemoryCreate, db: Session = Depends(get_db)):
    """Store something the persona said, decided or experienced."""
    _get_persona(db, id)
    memory = PersonaMemory(
        persona_id=id,
        kind=data.kind,
        topic=data.topic,
        content=data.content,
        source=data.source,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.get("/{id}/memories", response_model=list[MemoryRead])
def list_memories(
    id: str,
    kind: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List a persona's memories, newest first."""
    _get_persona(db, id)
    query = db.query(PersonaMemory).filter(PersonaMemory.persona_id == id)
    if kind:
        query = query.filter(PersonaMemory.kind == kind)
    return query.order_by(PersonaMemory.created_at.desc()).limit(limit).all()
