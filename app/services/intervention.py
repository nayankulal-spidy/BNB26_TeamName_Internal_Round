from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import settings
from app.groq_client import extract_json, groq_chat
from app.models import Diagnosis, Intervention, Misconception, Question

TYPE_ROTATION = [
    "explanation",
    "counterexample",
    "analogy",
    "code_example",
    "hint",
    "targeted_practice",
]


def _cycle_for(db: Session, student_id: str, misconception_id: str | None) -> int:
    if not misconception_id:
        return 1
    count = (
        db.query(Intervention)
        .filter(
            Intervention.student_id == student_id,
            Intervention.misconception_id == misconception_id,
        )
        .count()
    )
    return count + 1


def canned_intervention(misc: Misconception | None, cycle: int) -> tuple[str, str]:
    kind = TYPE_ROTATION[(cycle - 1) % len(TYPE_ROTATION)]
    if misc is None:
        return kind, "Let's slow down and compare your steps with what the Java code actually does."
    body = {
        "explanation": f"{misc.name}: {misc.description} {misc.examples}",
        "counterexample": f"Counterexample. {misc.examples} Notice how the wrong mental model fails on this tiny case.",
        "analogy": f"Analogy for {misc.name}. {misc.intervention_strategy}",
        "code_example": f"Look at this Java snippet in your head: {misc.examples}",
        "hint": f"Hint only: {misc.intervention_strategy} Do not jump to the final answer yet.",
        "targeted_practice": f"Practice: {misc.assessment_strategy}",
    }
    return kind, body[kind]


def generate_intervention(db: Session, diagnosis: Diagnosis, student_id: str) -> Intervention | None:
    if diagnosis.primary_misconception_id is None:
        return None
    cycle = _cycle_for(db, student_id, diagnosis.primary_misconception_id)
    if cycle > settings.max_intervention_cycles:
        return None

    misc = db.get(Misconception, diagnosis.primary_misconception_id)
    kind, content = canned_intervention(misc, cycle)

    if misc is not None:
        prompt = f"""Write a short targeted intervention for a Java beginner.
Do NOT reveal a one-line correct answer as the whole response.
Misconception: {misc.name}
Description: {misc.description}
Strategy: {misc.intervention_strategy}
Type requested: {kind}
Learner evidence: {diagnosis.evidence}
Keep it to 4-7 sentences or a tiny code snippet. Tone: encouraging, precise.
Return JSON {{"type": "{kind}", "content": "..."}}"""
        try:
            raw = groq_chat(prompt, "You repair Java mental models. JSON only.")
            data = extract_json(raw)
            content = str(data.get("content") or content)
            kind = str(data.get("type") or kind)
        except Exception:
            pass

    item = Intervention(
        diagnosis_id=diagnosis.id,
        student_id=student_id,
        misconception_id=diagnosis.primary_misconception_id,
        intervention_type=kind,
        content=content,
        cycle=cycle,
    )
    db.add(item)
    db.flush()
    return item


def pick_reassessment_question(db: Session, diagnosis: Diagnosis, original_question_id: str) -> Question | None:
    mid = diagnosis.primary_misconception_id
    if not mid:
        return None
    from app.models import QuestionMisconception

    qids = [
        row.question_id
        for row in db.query(QuestionMisconception).filter(QuestionMisconception.misconception_id == mid)
    ]
    questions = db.query(Question).filter(Question.id.in_(qids), Question.id != original_question_id).all()
    if not questions:
        return None
    reassess = [q for q in questions if q.is_reassessment]
    return (reassess or questions)[0]
