from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EvaluationResult, User
from app.security import get_current_user
from app.services.evaluation import run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run")
def evaluate(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = run_evaluation(db)
    return _public(result)


@router.get("/results")
def results(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(EvaluationResult).order_by(EvaluationResult.created_at.desc()).limit(10).all()
    return {"results": [_public(r) for r in rows]}


def _public(row: EvaluationResult) -> dict:
    import json

    return {
        "id": row.id,
        "modelVersion": row.model_version,
        "dataset": row.dataset,
        "accuracy": row.accuracy,
        "precision": row.precision,
        "recall": row.recall,
        "f1": row.f1,
        "confusionMatrix": json.loads(row.confusion_matrix or "{}"),
        "details": json.loads(row.details or "[]"),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
