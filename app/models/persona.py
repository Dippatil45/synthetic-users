from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, JSON
from sqlalchemy.sql import func
import enum
from app.db import Base


class PersonaStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Persona(Base):
    __tablename__ = "personas"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    status = Column(Enum(PersonaStatus), default=PersonaStatus.draft, nullable=False)
    tags = Column(JSON, nullable=False)
    demographics = Column(JSON, nullable=False)
    professional = Column(JSON, nullable=False)
    behavioral = Column(JSON, nullable=False)
    psychological = Column(JSON, nullable=True)
    backstory = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
