"""Persona lifecycle API endpoints."""

import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.persona import Persona, PersonaStatus
from app.schemas.persona import PersonaCreate, PersonaRead, PersonaUpdate
from app.generation.sampler import sample_profiles
from app.llm import persona_writer
from app.llm.client import LLMError
from app.config import settings

router = APIRouter(prefix="/personas", tags=["personas"])

# Valid status transitions
VALID_TRANSITIONS = {
    PersonaStatus.draft: [PersonaStatus.active, PersonaStatus.archived],
    PersonaStatus.active: [PersonaStatus.archived],
    PersonaStatus.archived: [PersonaStatus.active],
}


@router.post("", response_model=PersonaRead, status_code=status.HTTP_201_CREATED)
def create_persona(persona_data: PersonaCreate, db: Session = Depends(get_db)):
    """Create a new persona with draft status and version 1."""
    persona = Persona(
        id=str(uuid.uuid4()),
        name=persona_data.name,
        version=1,
        status=PersonaStatus.draft,
        tags=persona_data.tags,
        demographics=persona_data.demographics.model_dump(),
        professional=persona_data.professional.model_dump(),
        behavioral=persona_data.behavioral.model_dump(),
        psychological=persona_data.psychological,
        backstory=persona_data.backstory,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


@router.get("", response_model=list[PersonaRead])
def list_personas(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List personas with optional filtering. Newest first."""
    query = db.query(Persona)
    
    if status:
        query = query.filter(Persona.status == status)
    
    if tag:
        # Filter by tag in JSON array
        query = query.filter(Persona.tags.contains([tag]))
    
    query = query.order_by(Persona.created_at.desc())
    query = query.offset(offset).limit(limit)
    
    return query.all()


@router.get("/{id}", response_model=PersonaRead)
def get_persona(id: str, db: Session = Depends(get_db)):
    """Get a persona by ID."""
    persona = db.query(Persona).filter(Persona.id == id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    return persona


@router.patch("/{id}", response_model=PersonaRead)
def update_persona(id: str, updates: PersonaUpdate, db: Session = Depends(get_db)):
    """
    Partially update a persona.
    
    Version increments if demographics, professional, behavioral, psychological, or backstory change.
    Status changes follow allowed transitions only.
    """
    persona = db.query(Persona).filter(Persona.id == id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    
    # Track if content fields change (trigger version increment)
    content_changed = False
    
    # Handle status change with validation
    if updates.status is not None:
        try:
            new_status_enum = PersonaStatus(updates.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {updates.status}"
            )
        
        # Check if transition is valid
        if new_status_enum != persona.status:
            if new_status_enum not in VALID_TRANSITIONS.get(persona.status, []):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Invalid status transition from {persona.status.value} to {updates.status}"
                )
            persona.status = new_status_enum
    
    # Update other fields
    if updates.name is not None:
        persona.name = updates.name
    
    if updates.tags is not None:
        # Reassign as new list so SQLAlchemy detects change
        persona.tags = list(updates.tags)
    
    if updates.demographics is not None:
        persona.demographics = dict(updates.demographics.model_dump())
        content_changed = True
    
    if updates.professional is not None:
        persona.professional = dict(updates.professional.model_dump())
        content_changed = True
    
    if updates.behavioral is not None:
        persona.behavioral = dict(updates.behavioral.model_dump())
        content_changed = True
    
    if updates.psychological is not None:
        persona.psychological = dict(updates.psychological) if updates.psychological else None
        content_changed = True
    
    if updates.backstory is not None:
        persona.backstory = updates.backstory
        content_changed = True
    
    # Increment version if content changed
    if content_changed:
        persona.version += 1
    
    db.commit()
    db.refresh(persona)
    return persona


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(id: str, db: Session = Depends(get_db)):
    """Hard delete a persona."""
    persona = db.query(Persona).filter(Persona.id == id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    
    db.delete(persona)
    db.commit()
    return None


@router.post("/generate", response_model=list[PersonaRead])
def generate_personas(
    count: int = Query(default=10, ge=1, le=100),
    seed: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Generate and store synthetic personas.
    
    Uses sample_profiles to create personas with draft status.
    Names are temporary "Synthetic User " + first 6 chars of ID.
    """
    if not (1 <= count <= 100):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Count must be between 1 and 100"
        )
    
    profiles = sample_profiles(count, seed=seed)
    
    personas = []
    for profile in profiles:
        persona_id = str(uuid.uuid4())
        persona_name = f"Synthetic User {persona_id[:6]}"
        
        persona = Persona(
            id=persona_id,
            name=persona_name,
            version=1,
            status=PersonaStatus.draft,
            tags=[],
            demographics=profile["demographics"],
            professional=profile["professional"],
            behavioral=profile["behavioral"],
            psychological=None,
            backstory=None,
        )
        db.add(persona)
        personas.append(persona)
    
    db.commit()
    for persona in personas:
        db.refresh(persona)
    
    return personas


@router.post("/enrich-pending")
def enrich_pending_personas(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Enrich personas that have no backstory.
    
    Takes up to limit personas (newest first), generates name and backstory.
    Returns count of enriched and failed personas.
    """
    # Query personas with no backstory
    query = db.query(Persona).filter(
        (Persona.backstory == None) | (Persona.backstory == "")
    )
    query = query.order_by(Persona.created_at.desc())
    query = query.limit(limit)
    
    personas_to_enrich = query.all()
    
    enriched_count = 0
    failed_count = 0
    enriched_personas = []
    
    for persona in personas_to_enrich:
        try:
            # Build profile dict
            profile = {
                "demographics": persona.demographics,
                "professional": persona.professional,
                "behavioral": persona.behavioral,
            }
            
            # Generate identity
            identity = persona_writer.write_identity(profile)
            
            # Update persona
            persona.name = identity["name"]
            persona.backstory = identity["backstory"]
            db.commit()
            db.refresh(persona)
            
            enriched_count += 1
            enriched_personas.append(persona)
            
            # Sleep between calls (except after the last one)
            if persona != personas_to_enrich[-1]:
                time.sleep(settings.LLM_DELAY_SECONDS)
                
        except LLMError:
            # Continue to next persona on failure
            failed_count += 1
            db.rollback()
            continue
    
    return {
        "enriched": enriched_count,
        "failed": failed_count,
        "personas": enriched_personas
    }


@router.post("/{id}/enrich", response_model=PersonaRead)
def enrich_persona(id: str, db: Session = Depends(get_db)):
    """
    Generate name and backstory for a specific persona.
    
    Does not change version or status.
    Returns 502 if LLM fails.
    """
    persona = db.query(Persona).filter(Persona.id == id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    
    try:
        # Build profile dict
        profile = {
            "demographics": persona.demographics,
            "professional": persona.professional,
            "behavioral": persona.behavioral,
        }
        
        # Generate identity
        identity = persona_writer.write_identity(profile)
        
        # Update persona (no version or status change)
        persona.name = identity["name"]
        persona.backstory = identity["backstory"]
        db.commit()
        db.refresh(persona)
        
        return persona
        
    except LLMError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate persona identity: {str(e)}"
        )
