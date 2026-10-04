from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Diagnosis, Question, Reassessment, User
from app.security import get_current_user
from app.serializers import question_public, reassessment_public
from app.services.intervention import generate_intervention, pick_reassessment_question
from app.services.learner import bump_concept, grade, mark_resolution, record_detection

router = APIRouter(tags=["reassessments"])


class ReassessmentIn(BaseModel):
    diagnosisId: str
    answer: str = Field(min_length=1)
    reasoning: str = ""
    code: str = ""
    questionId: str | None = None


@router.post("/reassessments")
def create_reassessment(
    body: ReassessmentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagnosis = db.get(Diagnosis, body.diagnosisId)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="Diagnosis not found.")
    if diagnosis.attempt.student_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot reassess this diagnosis.")

    question_id = body.questionId
    if question_id is None:
        nxt = pick_reassessment_question(db, diagnosis, diagnosis.attempt.question_id)
        if nxt is None:
            raise HTTPException(status_code=404, detail="No equivalent reassessment question is available.")
        question_id = nxt.id
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    correct = grade(body.answer, question.correct_answer)
    cycle = max((row.cycle for row in diagnosis.interventions), default=1)
    if correct:
        status = "RESOLVED"
    elif diagnosis.confidence < 0.45:
        status = "UNCERTAIN"
    elif cycle >= settings.max_intervention_cycles:
        status = "UNCERTAIN"
    else:
        status = "NOT_RESOLVED"

    row = Reassessment(
        student_id=user.id,
        diagnosis_id=diagnosis.id,
        misconception_id=diagnosis.primary_misconception_id,
        question_id=question.id,
        answer=body.answer,
        reasoning=body.reasoning,
        code=body.code,
        is_correct=correct,
        resolution_status=status,
    )
    db.add(row)
    bump_concept(db, user.id, question.concept_id, correct)
    mark_resolution(db, user.id, diagnosis.primary_misconception_id, status)

    next_intervention = None
    next_question = None
    if status in {"NOT_RESOLVED", "PARTIALLY_RESOLVED", "UNCERTAIN"} and cycle < settings.max_intervention_cycles:
        if status == "NOT_RESOLVED":
            record_detection(db, user.id, diagnosis.primary_misconception_id, diagnosis.confidence)
            next_intervention = generate_intervention(db, diagnosis, user.id)
            next_question = pick_reassessment_question(db, diagnosis, question.id)

    db.commit()
    db.refresh(row)
    return {
        **reassessment_public(row),
        "learnerView": {
            "status": status.lower(),
            "headline": _headline(status),
            "detail": "This used a new question on the same idea, not the original prompt.",
        },
        "nextIntervention": {
            "id": next_intervention.id,
            "type": next_intervention.intervention_type,
            "content": next_intervention.content,
        }
        if next_intervention
        else None,
        "nextQuestion": question_public(next_question) if next_question else None,
        "loopCap": cycle >= settings.max_intervention_cycles,
    }


@router.get("/reassessments/{reassessment_id}")
def get_reassessment(
    reassessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(Reassessment, reassessment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Reassessment not found.")
    if row.student_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot view this reassessment.")
    return reassessment_public(row)


def _headline(status: str) -> str:
    return {
        "RESOLVED": "Misconception resolved — the new question shows a repaired mental model.",
        "PARTIALLY_RESOLVED": "Better, but the idea is not fully stable yet.",
        "NOT_RESOLVED": "The same misconception still appears. We'll try a different intervention.",
        "UNCERTAIN": "Not enough signal yet, or the repair loop has reached its cap.",
    }[status]
