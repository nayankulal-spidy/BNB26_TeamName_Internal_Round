from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Misconception
from app.serializers import misconception_public

router = APIRouter(prefix="/misconceptions", tags=["misconceptions"])


@router.get("")
def list_misconceptions(concept: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Misconception)
    if concept:
        query = query.filter(Misconception.concept_id == concept)
    return {"misconceptions": [misconception_public(m) for m in query.all()]}


@router.get("/{misconception_id}")
def get_misconception(misconception_id: str, db: Session = Depends(get_db)):
    item = db.get(Misconception, misconception_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Misconception not found.")
    return misconception_public(item)
