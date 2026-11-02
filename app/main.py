from fastapi import FastAPI
from app.db import engine, Base
import app.models.memory  # noqa: F401  (registers the persona_memories table)
from app.routers import personas, psychology, interview, survey, validation

app = FastAPI(title="Synthetic User Generation Platform")

app.include_router(psychology.router)
app.include_router(interview.router)
app.include_router(survey.router)
app.include_router(validation.router)
app.include_router(personas.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}
