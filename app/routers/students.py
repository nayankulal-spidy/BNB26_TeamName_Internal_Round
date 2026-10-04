from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt, Concept, ConceptProgress, LearnerMisconception, Reassessment, User
from app.security import get_current_user
from app.serializers import attempt_public, learner_misc_public, user_public
from app.services.recommend import recommend

router = APIRouter(prefix="/students", tags=["students"])


def _self(user: User, student_id: str) -> None:
    if user.id != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own learner model.")


@router.get("/{student_id}/profile")
def profile(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    return user_public(user)


@router.get("/{student_id}/attempts")
def attempts(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    rows = (
        db.query(Attempt)
        .filter(Attempt.student_id == student_id)
        .order_by(Attempt.created_at.desc())
        .all()
    )
    return {"attempts": [attempt_public(a) for a in rows], "count": len(rows)}


@router.get("/{student_id}/misconceptions")
def misconceptions(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    rows = db.query(LearnerMisconception).filter(LearnerMisconception.student_id == student_id).all()
    grouped = {"active": [], "resolved": [], "recurring": []}
    for row in rows:
        grouped.setdefault(row.status, []).append(learner_misc_public(row))
    return grouped


@router.get("/{student_id}/progress")
def progress(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    attempts = db.query(Attempt).filter(Attempt.student_id == student_id).all()
    correct = sum(1 for a in attempts if a.is_correct)
    accuracy = round(correct / len(attempts), 3) if attempts else 0.0
    concepts = []
    for row in db.query(ConceptProgress).filter(ConceptProgress.student_id == student_id):
        concept = db.get(Concept, row.concept_id)
        concepts.append(
            {
                "id": row.concept_id,
                "name": concept.name if concept else row.concept_id,
                "mastery": row.mastery,
                "attempts": row.attempts,
                "correct": row.correct,
                "bar": int(round(row.mastery * 100)),
            }
        )
    misc = db.query(LearnerMisconception).filter(LearnerMisconception.student_id == student_id).all()
    return {
        "accuracy": accuracy,
        "attempts": len(attempts),
        "conceptsAttempted": len(concepts),
        "conceptsUnderstood": sum(1 for c in concepts if c["mastery"] >= 0.8),
        "concepts": concepts,
        "activeMisconceptions": [learner_misc_public(r) for r in misc if r.status == "active"],
        "resolvedMisconceptions": [learner_misc_public(r) for r in misc if r.status == "resolved"],
        "recurringMisconceptions": [learner_misc_public(r) for r in misc if r.status == "recurring"],
        "recommended": recommend(db, student_id),
        "recentAttempts": [attempt_public(a) for a in attempts[-5:][::-1]],
    }


@router.get("/{student_id}/recommendations")
def recommendations(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    return recommend(db, student_id)


@router.get("/{student_id}/history")
def history(student_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _self(user, student_id)
    items = []
    for attempt in (
        db.query(Attempt)
        .filter(Attempt.student_id == student_id)
        .order_by(Attempt.created_at.desc())
        .all()
    ):
        diagnosis = attempt.diagnosis
        intervention = None
        if diagnosis and diagnosis.interventions:
            intervention = max(diagnosis.interventions, key=lambda row: row.created_at)
        reassess = None
        if diagnosis:
            reassess = (
                db.query(Reassessment)
                .filter(Reassessment.diagnosis_id == diagnosis.id)
                .order_by(Reassessment.created_at.desc())
                .first()
            )
        items.append(
            {
                "misconception": diagnosis.primary_misconception_id if diagnosis else None,
                "detectedAt": attempt.created_at.isoformat() if attempt.created_at else None,
                "intervention": intervention.content if intervention else None,
                "interventionType": intervention.intervention_type if intervention else None,
                "reassessment": reassess.resolution_status if reassess else None,
                "resolved": reassess.resolution_status == "RESOLVED" if reassess else False,
                "appearedAgain": False,
            }
        )
    recurring_ids = {
        row.misconception_id
        for row in db.query(LearnerMisconception).filter(
            LearnerMisconception.student_id == student_id,
            LearnerMisconception.status == "recurring",
        )
    }
    for item in items:
        item["appearedAgain"] = item["misconception"] in recurring_ids
    return {"history": items}
