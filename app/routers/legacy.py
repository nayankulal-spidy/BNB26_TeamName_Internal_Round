from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Question
from app.services.pipeline import process_attempt

router = APIRouter(tags=["legacy"])


class AnalyzeRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str
    domain: str = "programming"
    reasoning: str = ""
    code: str = ""


class AnalyzeResponse(BaseModel):
    misconception_type: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    intervention: str
    is_correct: bool


class SaveSessionRequest(AnalyzeResponse):
    question: str
    student_answer: str
    correct_answer: str
    domain: str = "programming"
    resolved: bool = False


def _demo_user_id(db: Session) -> str:
    from app.models import User

    user = db.query(User).filter(User.email == "demo@relearn.dev").first()
    if user is None:
        raise HTTPException(status_code=500, detail="Demo user missing. Restart the server.")
    return user.id


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    db = SessionLocal()
    try:
        question = (
            db.query(Question)
            .filter(Question.prompt == request.question)
            .first()
        )
        if question is None:
            question = Question(
                prompt=request.question,
                correct_answer=request.correct_answer,
                concept_id="java_operators",
                domain=request.domain,
                difficulty="intro",
            )
            db.add(question)
            db.flush()
        bundle = process_attempt(
            db,
            _demo_user_id(db),
            question,
            request.student_answer,
            request.reasoning,
            request.code,
        )
        diagnosis = bundle["diagnosis"]
        primary = diagnosis.get("primaryMisconception") or {}
        intervention = bundle.get("intervention") or {}
        return AnalyzeResponse(
            misconception_type=primary.get("name") or "No Misconception Detected",
            confidence=float(diagnosis.get("confidence") or 0),
            explanation=diagnosis.get("explanation") or bundle["learnerView"].get("detail", ""),
            intervention=intervention.get("content") or bundle["learnerView"].get("headline", ""),
            is_correct=bool(bundle["attempt"]["isCorrect"]),
        )
    finally:
        db.close()


@router.post("/save-session")
def save_session(request: SaveSessionRequest) -> dict[str, Any]:
    from supabase import Client, create_client

    if not settings.supabase_url or not settings.supabase_key:
        return {"saved": True, "session": request.model_dump(), "storage": "local-only"}
    client: Client = create_client(settings.supabase_url, settings.supabase_key)
    try:
        response = client.table("sessions").insert(request.model_dump()).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to save session.") from exc
    data = response.data or []
    return {"saved": True, "session": data[0] if data else request.model_dump(), "storage": "supabase"}


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    from supabase import Client, create_client

    if not settings.supabase_url or not settings.supabase_key:
        return {"sessions": [], "count": 0, "storage": "local-only"}
    client: Client = create_client(settings.supabase_url, settings.supabase_key)
    try:
        response = client.table("sessions").select("*").order("created_at", desc=True).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to load sessions.") from exc
    sessions = response.data or []
    return {"sessions": sessions, "count": len(sessions)}


@router.patch("/sessions/{session_id}/resolve")
def resolve_session(session_id: str) -> dict[str, Any]:
    from supabase import Client, create_client

    if not settings.supabase_url or not settings.supabase_key:
        raise HTTPException(status_code=404, detail="Session not found.")
    client: Client = create_client(settings.supabase_url, settings.supabase_key)
    try:
        response = client.table("sessions").update({"resolved": True}).eq("id", session_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to resolve session.") from exc
    data = response.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"resolved": True, "session": data[0]}
