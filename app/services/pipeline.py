from sqlalchemy.orm import Session

from app.models import Attempt, Question
from app.serializers import diagnosis_public, intervention_public, question_public
from app.services.diagnosis import diagnose_attempt
from app.services.intervention import generate_intervention, pick_reassessment_question
from app.services.learner import bump_concept, record_detection


def process_attempt(
    db: Session,
    student_id: str,
    question: Question,
    answer: str,
    reasoning: str,
    code: str,
) -> dict:
    attempt = Attempt(
        student_id=student_id,
        question_id=question.id,
        answer=answer,
        reasoning=reasoning or "",
        code=code or "",
    )
    db.add(attempt)
    db.flush()
    diagnosis = diagnose_attempt(db, attempt)
    bump_concept(db, student_id, question.concept_id, attempt.is_correct)
    if not attempt.is_correct:
        record_detection(db, student_id, diagnosis.primary_misconception_id, diagnosis.confidence)

    intervention = None
    next_question = None
    if not attempt.is_correct and diagnosis.primary_misconception_id:
        intervention = generate_intervention(db, diagnosis, student_id)
        next_question = pick_reassessment_question(db, diagnosis, question.id)

    db.commit()
    db.refresh(attempt)
    db.refresh(diagnosis)

    learner_facing = _learner_copy(attempt.is_correct, diagnosis)
    return {
        "attempt": {
            "id": attempt.id,
            "isCorrect": attempt.is_correct,
            "questionId": question.id,
        },
        "diagnosis": diagnosis_public(diagnosis),
        "learnerView": learner_facing,
        "intervention": intervention_public(intervention) if intervention else None,
        "reassessmentQuestion": question_public(next_question) if next_question else None,
        "loopCap": intervention.cycle >= 3 if intervention else False,
    }


def _learner_copy(is_correct: bool, diagnosis) -> dict:
    if is_correct:
        return {
            "status": "correct",
            "headline": "That matches the intended Java idea.",
            "detail": "No active misconception was detected on this attempt.",
        }
    name = None
    if diagnosis.primary_misconception:
        name = diagnosis.primary_misconception.name
    elif diagnosis.primary_misconception_id:
        name = diagnosis.primary_misconception_id.replace("_", " ")
    if diagnosis.needs_followup or diagnosis.confidence < 0.55:
        return {
            "status": "uncertain",
            "headline": "There may be more than one reason this went wrong.",
            "detail": diagnosis.explanation,
            "followupQuestion": diagnosis.followup_question,
        }
    return {
        "status": "misconception",
        "headline": f"Your answer suggests you may be confusing: {name}." if name else "A specific thinking error showed up.",
        "detail": diagnosis.explanation,
        "confidenceBand": "high" if diagnosis.confidence >= 0.8 else "medium",
    }
