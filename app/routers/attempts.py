from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Attempt, Question, User
from app.security import get_current_user
from app.serializers import attempt_public
from app.services.pipeline import process_attempt

router = APIRouter(tags=["attempts"])


class AttemptIn(BaseModel):
    questionId: str
    answer: str = Field(min_length=1)
    reasoning: str = ""
    code: str = ""


@router.post("/attempts")
def create_attempt(
    body: AttemptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.get(Question, body.questionId)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return process_attempt(db, user.id, question, body.answer, body.reasoning, body.code)


@router.get("/attempts/{attempt_id}")
def get_attempt(
    attempt_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    if attempt.student_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot view this attempt.")
    return attempt_public(attempt)
