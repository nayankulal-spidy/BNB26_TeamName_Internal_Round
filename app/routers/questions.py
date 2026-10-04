from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question, QuestionMisconception
from app.serializers import question_public

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
def list_questions(
    concept: str | None = None,
    difficulty: str | None = None,
    domain: str | None = None,
    misconception: str | None = None,
    include_reassessment: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Question)
    if concept:
        query = query.filter(Question.concept_id == concept)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if domain:
        query = query.filter(Question.domain == domain)
    if not include_reassessment:
        query = query.filter(Question.is_reassessment.is_(False))
    rows = query.all()
    if misconception:
        allowed = {
            link.question_id
            for link in db.query(QuestionMisconception).filter(
                QuestionMisconception.misconception_id == misconception
            )
        }
        rows = [q for q in rows if q.id in allowed]
    return {"questions": [question_public(q) for q in rows]}


@router.get("/{question_id}")
def get_question(question_id: str, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return question_public(question)
