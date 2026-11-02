"""Validation and diversity report endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.persona import Persona
from app.validation import diversity_report, validate_persona

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/report")
def validation_report(db: Session = Depends(get_db)):
    """Check every persona for realism problems and report population diversity (no LLM)."""
    personas = db.query(Persona).order_by(Persona.created_at.desc()).all()
    data = [
        {
            "id": p.id,
            "name": p.name,
            "demographics": p.demographics,
            "professional": p.professional,
            "behavioral": p.behavioral,
            "psychological": p.psychological,
            "backstory": p.backstory,
        }
        for p in personas
    ]
    issues = []
    for item in data:
        for issue in validate_persona(item):
            issues.append({"persona_id": item["id"], "name": item["name"], **issue})
    return {
        "personas_checked": len(data),
        "personas_with_errors": len({i["persona_id"] for i in issues if i["level"] == "error"}),
        "personas_with_warnings": len({i["persona_id"] for i in issues if i["level"] == "warning"}),
        "issues": issues,
        "diversity": diversity_report(data),
    }
