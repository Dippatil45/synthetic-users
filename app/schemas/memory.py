from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    kind: Literal["note", "opinion", "answer", "event"] = "note"
    topic: Optional[str] = None
    content: str = Field(min_length=1, max_length=2000)
    source: Optional[str] = None


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    persona_id: str
    kind: str
    topic: Optional[str] = None
    content: str
    source: Optional[str] = None
    created_at: datetime
