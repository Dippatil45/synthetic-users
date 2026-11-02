from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Demographics(BaseModel):
    age: int
    gender: str
    location: str
    education: str
    income_band: str
    marital_status: str


class Professional(BaseModel):
    occupation: str
    industry: str
    experience_years: int


class Behavioral(BaseModel):
    tech_savviness: int = Field(..., ge=1, le=10)
    shopping_habits: str
    brand_loyalty: str
    preferred_devices: list[str]
    spending_style: str


class PersonaCreate(BaseModel):
    name: str
    tags: list[str]
    demographics: Demographics
    professional: Professional
    behavioral: Behavioral
    psychological: Optional[dict] = None
    backstory: Optional[str] = None


class PersonaRead(BaseModel):
    id: str
    name: str
    version: int
    status: str
    tags: list[str]
    demographics: Demographics
    professional: Professional
    behavioral: Behavioral
    psychological: Optional[dict] = None
    backstory: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None
    demographics: Optional[Demographics] = None
    professional: Optional[Professional] = None
    behavioral: Optional[Behavioral] = None
    psychological: Optional[dict] = None
    backstory: Optional[str] = None
