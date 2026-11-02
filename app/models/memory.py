"""Persona memory: things a persona has said or decided, kept for consistent behavior."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, event

from app.db import Base
from app.models.persona import Persona


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PersonaMemory(Base):
    __tablename__ = "persona_memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    persona_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False, default="note")
    topic = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


@event.listens_for(Persona, "after_delete")
def _delete_memories_with_persona(mapper, connection, target):
    """When a persona is deleted, remove its memories too."""
    connection.execute(
        PersonaMemory.__table__.delete().where(PersonaMemory.persona_id == target.id)
    )
