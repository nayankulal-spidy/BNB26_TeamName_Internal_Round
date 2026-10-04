from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Attempt, ConceptProgress, LearnerMisconception, Question, QuestionMisconception


def recommend(db: Session, student_id: str) -> dict:
    active = (
        db.query(LearnerMisconception)
        .filter(
            LearnerMisconception.student_id == student_id,
            LearnerMisconception.status.in_(["active", "recurring"]),
        )
        .order_by(LearnerMisconception.status.desc(), LearnerMisconception.detections.desc())
        .all()
    )
    attempted = {
        row.question_id
        for row in db.query(Attempt).filter(Attempt.student_id == student_id)
    }

    reason = "Practice a new introductory Java concept."
    question = None
    if active:
        target = active[0]
        reason = (
            "Recurring misconception needs another pass."
            if target.status == "recurring"
            else "Active misconception should be repaired next."
        )
        qids = [
            link.question_id
            for link in db.query(QuestionMisconception).filter(
                QuestionMisconception.misconception_id == target.misconception_id
            )
        ]
        unused = db.query(Question).filter(Question.id.in_(qids), Question.id.notin_(attempted or {""})).all()
        question = unused[0] if unused else db.query(Question).filter(Question.id.in_(qids)).first()

    if question is None:
        weak = (
            db.query(ConceptProgress)
            .filter(ConceptProgress.student_id == student_id)
            .order_by(ConceptProgress.mastery.asc())
            .first()
        )
        query = db.query(Question).filter(Question.is_reassessment.is_(False))
        if weak:
            query = query.filter(Question.concept_id == weak.concept_id)
            reason = f"Lowest mastery is {weak.concept_id}."
        unused = query.filter(Question.id.notin_(attempted or {""})).all()
        question = unused[0] if unused else query.first()

    return {
        "reason": reason,
        "questionId": question.id if question else None,
        "prompt": question.prompt if question else None,
        "conceptId": question.concept_id if question else None,
        "priorityMisconceptions": [
            {"id": row.misconception_id, "status": row.status, "detections": row.detections}
            for row in active[:5]
        ],
    }
