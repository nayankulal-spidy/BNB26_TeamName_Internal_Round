from sqlalchemy.orm import Session

from app.catalog import CONCEPTS, MISCONCEPTIONS, QUESTIONS
from app.models import Concept, Misconception, Question, QuestionMisconception, User
from app.security import hash_password


def seed_if_empty(db: Session) -> None:
    if db.get(Concept, "java_operators") is None:
        for row in CONCEPTS:
            db.add(Concept(**row))
        for row in MISCONCEPTIONS:
            payload = {k: v for k, v in row.items() if k != "signatures"}
            db.add(Misconception(**payload))
        for row in QUESTIONS:
            data = {k: v for k, v in row.items() if k != "misconceptions"}
            db.add(Question(**data))
            for mid in row.get("misconceptions", []):
                db.add(
                    QuestionMisconception(
                        question_id=data["id"],
                        misconception_id=mid,
                    )
                )

    if db.query(User).filter(User.email == "demo@relearn.dev").first() is None:
        db.add(
            User(
                name="Demo Student",
                email="demo@relearn.dev",
                password_hash=hash_password("demo1234"),
            )
        )
    db.commit()
