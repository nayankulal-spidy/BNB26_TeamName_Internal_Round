from __future__ import annotations

import json

from app.models import (
    Attempt,
    Concept,
    Diagnosis,
    Intervention,
    LearnerMisconception,
    Misconception,
    Question,
    Reassessment,
    User,
)


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
    }


def question_public(q: Question) -> dict:
    return {
        "id": q.id,
        "conceptId": q.concept_id,
        "prompt": q.prompt,
        "difficulty": q.difficulty,
        "domain": q.domain,
        "type": q.question_type,
        "isReassessment": q.is_reassessment,
        "misconceptionIds": [link.misconception_id for link in (q.links or [])],
    }


def misconception_public(m: Misconception) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "conceptId": m.concept_id,
        "description": m.description,
        "examples": m.examples,
        "commonMistakePatterns": m.common_patterns,
        "interventionStrategy": m.intervention_strategy,
        "assessmentStrategy": m.assessment_strategy,
    }


def diagnosis_public(d: Diagnosis) -> dict:
    primary = None
    if d.primary_misconception_id:
        primary = {
            "id": d.primary_misconception_id,
            "name": d.primary_misconception.name if d.primary_misconception else d.primary_misconception_id,
            "confidence": d.confidence,
        }
    return {
        "id": d.id,
        "isCorrect": d.attempt.is_correct if d.attempt else None,
        "primaryMisconception": primary,
        "alternativeMisconceptions": json.loads(d.alternatives or "[]"),
        "evidence": json.loads(d.evidence or "[]"),
        "explanation": d.explanation,
        "confidence": d.confidence,
        "source": d.source,
        "needsFollowup": d.needs_followup,
        "followupQuestion": d.followup_question or None,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
    }


def attempt_public(a: Attempt) -> dict:
    return {
        "id": a.id,
        "studentId": a.student_id,
        "questionId": a.question_id,
        "answer": a.answer,
        "reasoning": a.reasoning,
        "code": a.code,
        "isCorrect": a.is_correct,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
        "diagnosis": diagnosis_public(a.diagnosis) if a.diagnosis else None,
    }


def intervention_public(i: Intervention) -> dict:
    return {
        "id": i.id,
        "diagnosisId": i.diagnosis_id,
        "type": i.intervention_type,
        "content": i.content,
        "cycle": i.cycle,
        "misconceptionId": i.misconception_id,
        "createdAt": i.created_at.isoformat() if i.created_at else None,
    }


def reassessment_public(r: Reassessment) -> dict:
    return {
        "id": r.id,
        "diagnosisId": r.diagnosis_id,
        "questionId": r.question_id,
        "answer": r.answer,
        "isCorrect": r.is_correct,
        "resolutionStatus": r.resolution_status,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }


def learner_misc_public(row: LearnerMisconception) -> dict:
    return {
        "id": row.misconception_id,
        "name": row.misconception.name if row.misconception else row.misconception_id,
        "status": row.status,
        "detections": row.detections,
        "confidence": row.confidence,
        "lastDetectedAt": row.last_detected_at.isoformat() if row.last_detected_at else None,
        "lastResolvedAt": row.last_resolved_at.isoformat() if row.last_resolved_at else None,
    }
