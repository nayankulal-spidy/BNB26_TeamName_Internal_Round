from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Concept

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("")
def list_concepts(db: Session = Depends(get_db)):
    return {
        "concepts": [
            {"id": c.id, "name": c.name, "domain": c.domain, "description": c.description}
            for c in db.query(Concept).all()
        ]
    }
