# main.py — Re:Learn Complete Backend
# ------------------------------------------------------------
# This file wires together every router, sets up CORS,
# creates the DB schema, seeds initial data, and exposes
# health & demo endpoints.
# ------------------------------------------------------------

import os
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# ------------------------------------------------------------
# Load environment variables (GROQ_API_KEY, GROQ_MODEL, etc.)
# ------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------
# App configuration & metadata
# ------------------------------------------------------------
app = FastAPI(
    title="Re:Learn API",
    description=(
        "Identify *WHY* a learner is wrong, provide a targeted intervention, "
        "and verify the misconception is actually resolved."
    ),
    version="1.0.0",
)

# ------------------------------------------------------------
# CORS – allow the frontend (Vercel) to call the API
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # change to specific domains for production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Database & seed
# ------------------------------------------------------------
from app.config import settings               # your Settings pydantic class
from app.database import Base, SessionLocal, engine
from app import models                        # noqa: F401 – registers tables
from app.seed import seed_if_empty

# Create all tables if they don’t exist yet
Base.metadata.create_all(bind=engine)

# Populate minimal seed data (questions, misconceptions, etc.) on first run
with SessionLocal() as db:
    seed_if_empty(db)

# ------------------------------------------------------------
# Import and include all routers
# ------------------------------------------------------------
from app.routers import (
    attempts,
    auth,
    concepts,
    diagnosis,
    evaluation,
    interventions,
    legacy,
    misconceptions,
    questions,
    reassessments,
    students,
)

app.include_router(auth.router)
app.include_router(concepts.router)
app.include_router(questions.router)
app.include_router(attempts.router)
app.include_router(diagnosis.router)
app.include_router(misconceptions.router)
app.include_router(interventions.router)
app.include_router(reassessments.router)   # <-- NEW endpoint
app.include_router(students.router)
app.include_router(evaluation.router)
app.include_router(legacy.router)

# ------------------------------------------------------------
# Global exception handlers
# ------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    """Return a concise 422 payload for any validation error."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Invalid request. Check required fields."},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception):
    """Catch‑all handler – surface HTTPException correctly, otherwise 500."""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong. Please try again."},
    )

# ------------------------------------------------------------
# Health check endpoint
# ------------------------------------------------------------
@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "relearn-backend",
        "provider": "groq",
        "model": settings.groq_model,          # e.g. "llama-3.1-8b-instant"
        "idea": "Re:Learn diagnoses WHY a learner is wrong, then checks if the misconception is resolved.",
    }

# ------------------------------------------------------------
# Demo scenario endpoint – handy for judges & mentors
# ------------------------------------------------------------
@app.get("/demo/scenario", tags=["Demo"])
def demo_scenario():
    """
    Returns a JSON object describing the exact flow the judges can
    follow step‑by‑step. The front‑end can also use this to pre‑fill
    a demo user.
    """
    return {
        "login": {"email": "demo@relearn.dev", "password": "demo1234"},
        "questionId": "q_eq_meaning",
        "studentAnswer": "It assigns a value to a variable.",
        "reasoning": "== puts the value into the variable.",
        "expectedMisconception": "assignment_vs_comparison",
        "reassessmentQuestionId": "q_eq_result",
        "reassessmentAnswer": "true",
        "flow": [
            "POST /auth/login",
            "POST /attempts with q_eq_meaning",
            "GET /diagnosis → receives misconception & intervention",
            "POST /reassessments with the new question & answer",
            "GET /students/demo_student/progress",
        ],
        "keyMessage": "We do not just mark wrong – we diagnose WHY and verify the fix.",
    }