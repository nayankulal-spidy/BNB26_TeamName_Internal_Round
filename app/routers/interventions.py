from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Diagnosis, Intervention, User
from app.security import get_current_user
from app.serializers import intervention_public
from app.services.intervention import generate_intervention

router = APIRouter(tags=["interventions"])


class InterventionIn(BaseModel):
    diagnosisId: str


@router.get("/interventions/{diagnosis_id}")
def get_intervention(
    diagnosis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagnosis = db.get(Diagnosis, diagnosis_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="Diagnosis not found.")
    if diagnosis.attempt.student_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot view this intervention.")
    if diagnosis.interventions:
        latest = max(diagnosis.interventions, key=lambda row: row.created_at)
        return intervention_public(latest)
    created = generate_intervention(db, diagnosis, user.id)
    db.commit()
    if created is None:
        raise HTTPException(
            status_code=409,
            detail="Intervention loop cap reached. Revisit the concept later.",
        )
    return intervention_public(created)


@router.post("/interventions")
def create_intervention(
    body: InterventionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_intervention(body.diagnosisId, user, db)
