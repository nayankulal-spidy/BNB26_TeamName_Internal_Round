from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ConceptProgress, LearnerMisconception
from app.services.diagnosis import answers_match


def record_detection(db: Session, student_id: str, misconception_id: str | None, confidence: float) -> None:
    if not misconception_id:
        return
    row = (
        db.query(LearnerMisconception)
        .filter(
            LearnerMisconception.student_id == student_id,
            LearnerMisconception.misconception_id == misconception_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        db.add(
            LearnerMisconception(
                student_id=student_id,
                misconception_id=misconception_id,
                status="active",
                detections=1,
                confidence=confidence,
                last_detected_at=now,
            )
        )
        return
    row.detections += 1
    row.confidence = max(row.confidence, confidence)
    row.last_detected_at = now
    if row.status == "resolved":
        row.status = "recurring"
    elif row.status != "recurring":
        row.status = "active"


def mark_resolution(db: Session, student_id: str, misconception_id: str | None, status: str) -> None:
    if not misconception_id:
        return
    row = (
        db.query(LearnerMisconception)
        .filter(
            LearnerMisconception.student_id == student_id,
            LearnerMisconception.misconception_id == misconception_id,
        )
        .first()
    )
    if row is None:
        return
    if status == "RESOLVED":
        row.status = "resolved"
        row.last_resolved_at = datetime.utcnow()
    elif status in {"NOT_RESOLVED", "PARTIALLY_RESOLVED"}:
        if row.status == "resolved":
            row.status = "recurring"
        else:
            row.status = "active"


def bump_concept(db: Session, student_id: str, concept_id: str, correct: bool) -> None:
    row = (
        db.query(ConceptProgress)
        .filter(ConceptProgress.student_id == student_id, ConceptProgress.concept_id == concept_id)
        .first()
    )
    if row is None:
        row = ConceptProgress(student_id=student_id, concept_id=concept_id)
        db.add(row)
        db.flush()
    row.attempts += 1
    if correct:
        row.correct += 1
    row.mastery = round(row.correct / max(row.attempts, 1), 3)
    row.updated_at = datetime.utcnow()


def resolution_status(is_correct: bool, previous_correct: bool, cycle: int) -> str:
    if is_correct and previous_correct:
        return "RESOLVED"
    if is_correct and not previous_correct:
        return "PARTIALLY_RESOLVED" if cycle == 1 else "RESOLVED"
    if not is_correct and cycle >= 3:
        return "UNCERTAIN"
    return "NOT_RESOLVED"


def grade(student_answer: str, correct_answer: str) -> bool:
    return answers_match(student_answer, correct_answer)
