from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.catalog import MISCONCEPTIONS
from app.config import settings
from app.groq_client import extract_json, groq_chat
from app.models import Attempt, Diagnosis, Misconception, Question, QuestionMisconception

SIGNATURES = {row["id"]: [s.lower() for s in row.get("signatures", [])] for row in MISCONCEPTIONS}


def normalize_answer(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().strip("\"'`."))


def answers_match(student: str, correct: str) -> bool:
    a, b = normalize_answer(student), normalize_answer(correct)
    if not a or not b:
        return False
    if a == b:
        return True
    if b in a or a in b:
        return len(min(a, b, key=len)) >= 3
    return False


def rule_diagnose(question: Question, answer: str, reasoning: str, code: str) -> dict[str, Any]:
    blob = f"{answer} {reasoning} {code}".lower()
    scored: list[tuple[str, int, str]] = []
    for mid, phrases in SIGNATURES.items():
        hits = [p for p in phrases if p in blob]
        if hits:
            scored.append((mid, len(hits), hits[0]))
    scored.sort(key=lambda x: x[1], reverse=True)
    primary = scored[0][0] if scored else None
    evidence = []
    if scored:
        evidence.append(f"Learner language matched '{scored[0][2]}'.")
    alts = [{"id": m, "confidence": min(0.45 + 0.1 * n, 0.8)} for m, n, _ in scored[1:3]]
    confidence = 0.86 if scored else 0.35
    if question.links:
        linked = {link.misconception_id for link in question.links}
        if primary and primary in linked:
            confidence = min(confidence + 0.06, 0.95)
        elif primary is None and len(linked) == 1:
            primary = next(iter(linked))
            confidence = 0.48
            evidence.append("Answer is incorrect on a question tagged with a single common misconception; confidence is moderate.")
    return {
        "primary_misconception_id": primary,
        "confidence": confidence,
        "evidence": evidence or ["No strong lexical cue; diagnosis is uncertain."],
        "alternatives": alts,
        "explanation": "Pattern-matched against the Java intro misconception catalog.",
        "source": "rules",
        "needs_followup": confidence < settings.low_confidence_threshold,
    }


def groq_diagnose(
    question: Question,
    answer: str,
    reasoning: str,
    code: str,
    candidates: list[Misconception],
) -> dict[str, Any] | None:
    catalog = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "patterns": m.common_patterns,
        }
        for m in candidates
    ]
    prompt = f"""Diagnose the Java learner's misconception. Do NOT only mark right/wrong.

Choose primaryMisconceptionId from this catalog, or null if the answer is conceptually correct:
{json.dumps(catalog, indent=2)}

Question: {question.prompt}
Correct answer: {question.correct_answer}
Student answer: {answer}
Student reasoning: {reasoning or "(none)"}
Student code: {code or "(none)"}

Same wrong output can come from different misconceptions. Use reasoning and code to differentiate.
If unsure, lower confidence and set needsFollowup true.

Return JSON:
{{
  "isCorrect": false,
  "primaryMisconceptionId": "assignment_vs_comparison" or null,
  "confidence": 0.0,
  "evidence": ["short quote or observation"],
  "alternativeMisconceptions": [{{"id": "...", "confidence": 0.0}}],
  "explanation": "2 sentences on the thinking error",
  "needsFollowup": false,
  "followupQuestion": ""
}}"""
    try:
        raw = groq_chat(
            prompt,
            "You diagnose Java misconceptions. Reply with valid JSON only. Never invent catalog ids.",
        )
        data = extract_json(raw)
    except Exception:
        return None

    allowed = {m.id for m in candidates}
    mid = data.get("primaryMisconceptionId") or data.get("primary_misconception_id")
    if mid not in allowed:
        mid = None
    alts = []
    for item in data.get("alternativeMisconceptions") or data.get("alternatives") or []:
        if isinstance(item, dict) and item.get("id") in allowed:
            alts.append({"id": item["id"], "confidence": float(item.get("confidence") or 0)})
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.4
    evidence = data.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    return {
        "primary_misconception_id": mid,
        "confidence": confidence,
        "evidence": [str(x) for x in evidence][:4],
        "alternatives": alts[:3],
        "explanation": str(data.get("explanation") or "").strip(),
        "source": "groq",
        "needs_followup": bool(data.get("needsFollowup") or confidence < settings.low_confidence_threshold),
        "followup_question": str(data.get("followupQuestion") or ""),
    }


def diagnose_attempt(db: Session, attempt: Attempt) -> Diagnosis:
    question = db.get(Question, attempt.question_id)
    assert question is not None
    is_correct = answers_match(attempt.answer, question.correct_answer)
    attempt.is_correct = is_correct

    candidates = db.query(Misconception).all()
    linked_ids = [
        row.misconception_id
        for row in db.query(QuestionMisconception).filter(
            QuestionMisconception.question_id == question.id
        )
    ]
    if linked_ids:
        linked = [m for m in candidates if m.id in linked_ids]
        if linked:
            candidates = linked + [m for m in candidates if m.id not in linked_ids]

    result = None
    if not is_correct:
        result = groq_diagnose(question, attempt.answer, attempt.reasoning, attempt.code, candidates)
        if result is None:
            result = rule_diagnose(question, attempt.answer, attempt.reasoning, attempt.code)
        elif result["confidence"] < 0.4:
            fallback = rule_diagnose(question, attempt.answer, attempt.reasoning, attempt.code)
            if fallback["confidence"] > result["confidence"]:
                result = fallback
                result["source"] = "hybrid"
    else:
        result = {
            "primary_misconception_id": None,
            "confidence": 0.9,
            "evidence": ["Answer matches the expected idea."],
            "alternatives": [],
            "explanation": "No misconception detected.",
            "source": "rules",
            "needs_followup": False,
            "followup_question": "",
        }

    if result["needs_followup"] and not result.get("followup_question"):
        result["followup_question"] = question.diagnostic_followup

    diagnosis = Diagnosis(
        attempt_id=attempt.id,
        primary_misconception_id=result["primary_misconception_id"],
        confidence=result["confidence"],
        evidence=json.dumps(result["evidence"]),
        alternatives=json.dumps(result["alternatives"]),
        explanation=result["explanation"],
        source=result["source"],
        needs_followup=result["needs_followup"] and not is_correct,
        followup_question=result.get("followup_question") or "",
    )
    db.add(diagnosis)
    db.flush()
    return diagnosis
