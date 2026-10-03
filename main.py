import json
import os
import re
from typing import Any, Optional

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import Client, create_client

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SESSIONS_TABLE = "sessions"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Re:Learn Misconception Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str
    domain: str = "programming"


class AnalyzeResponse(BaseModel):
    misconception_type: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    intervention: str
    is_correct: bool


class SaveSessionRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str
    domain: str = "programming"
    misconception_type: str
    confidence: float
    explanation: str
    intervention: str
    is_correct: bool
    resolved: bool = False


ANALYSIS_PROMPT = """You are an expert learning-science tutor for {domain}.

Your job is NOT to grade right vs wrong as the main output. Diagnose the student's
underlying misconception: the specific faulty mental model that produced this answer.

Identify a concrete misconception TYPE using a short title, such as:
- Operator Precedence Confusion
- Variable Scope Misunderstanding
- Off-by-one Error Pattern
- Pass-by-Reference vs Pass-by-Value Mixup
- Boolean Short-Circuit Misread
Only use "No Misconception Detected" when the student answer is conceptually aligned
with the correct answer (minor wording differences are still correct).

Question:
{question}

Student answer:
{student_answer}

Correct answer:
{correct_answer}

Return ONLY valid JSON with these keys:
- misconception_type: string (specific type name, not "wrong" or "incorrect")
- confidence: number from 0 to 1
- explanation: 2-3 sentences describing the thinking error, not just the correct fact
- intervention: a concrete tip or exercise that repairs that mental model
- is_correct: boolean

Do not wrap the JSON in markdown. Do not add extra keys."""


def get_supabase() -> Client:
    if supabase is None:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.",
        )
    return supabase


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


def build_analysis_prompt(payload: AnalyzeRequest) -> str:
    # Avoid str.format so student code containing { or } cannot crash the prompt.
    return (
        ANALYSIS_PROMPT.replace("{domain}", payload.domain)
        .replace("{question}", payload.question)
        .replace("{student_answer}", payload.student_answer)
        .replace("{correct_answer}", payload.correct_answer)
    )


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned non-JSON output: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Gemini JSON was not an object.")
    return parsed


def analyze_with_gemini(payload: AnalyzeRequest) -> AnalyzeResponse:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not set.",
        )

    prompt = build_analysis_prompt(payload)

    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        result = model.generate_content(prompt)
        raw_text = (getattr(result, "text", None) or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini analysis failed: {exc}",
        ) from exc

    if not raw_text:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an empty response.",
        )

    data = extract_json(raw_text)

    try:
        confidence = float(data.get("confidence", 0))
        confidence = max(0.0, min(1.0, confidence))
        return AnalyzeResponse(
            misconception_type=str(data.get("misconception_type", "")).strip()
            or "Unclassified Misconception",
            confidence=confidence,
            explanation=str(data.get("explanation", "")).strip(),
            intervention=str(data.get("intervention", "")).strip(),
            is_correct=parse_bool(data.get("is_correct", False)),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini response missing required fields: {exc}",
        ) from exc


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "relearn-backend"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return analyze_with_gemini(request)


@app.post("/save-session")
def save_session(request: SaveSessionRequest) -> dict[str, Any]:
    client = get_supabase()
    row = request.model_dump()
    try:
        response = client.table(SESSIONS_TABLE).insert(row).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to save session: {exc}") from exc

    data = response.data or []
    return {"saved": True, "session": data[0] if data else row}


@app.get("/sessions")
def list_sessions() -> dict[str, Any]:
    client = get_supabase()
    try:
        response = (
            client.table(SESSIONS_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load sessions: {exc}") from exc

    sessions = response.data or []
    return {"sessions": sessions, "count": len(sessions)}


@app.patch("/sessions/{session_id}/resolve")
def resolve_session(session_id: str) -> dict[str, Any]:
    client = get_supabase()
    try:
        response = (
            client.table(SESSIONS_TABLE)
            .update({"resolved": True})
            .eq("id", session_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to resolve session: {exc}") from exc

    data = response.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"resolved": True, "session": data[0]}
