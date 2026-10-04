from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app.catalog import LABELED_EVAL
from app.config import settings
from app.models import EvaluationResult, Question
from app.services.diagnosis import groq_diagnose, rule_diagnose


class _FakeQuestion:
    def __init__(self, prompt: str, correct: str, links: list):
        self.prompt = prompt
        self.correct_answer = correct
        self.links = links
        self.diagnostic_followup = ""


def run_evaluation(db: Session) -> EvaluationResult:
    from app.models import Misconception

    candidates = db.query(Misconception).all()
    y_true: list[str | None] = []
    y_pred: list[str | None] = []
    details = []
    for item in LABELED_EVAL:
        q = _FakeQuestion(item["question"], item["correct_answer"], [])
        predicted = None
        source = "rules"
        groq = groq_diagnose(q, item["student_answer"], item["reasoning"], item["code"], candidates)  # type: ignore[arg-type]
        if groq and groq.get("primary_misconception_id"):
            predicted = groq["primary_misconception_id"]
            source = "groq"
        else:
            fake = Question(prompt=item["question"], correct_answer=item["correct_answer"])
            fake.links = []
            predicted = rule_diagnose(fake, item["student_answer"], item["reasoning"], item["code"])[
                "primary_misconception_id"
            ]
        y_true.append(item["label"])
        y_pred.append(predicted)
        details.append(
            {
                "label": item["label"],
                "predicted": predicted,
                "source": source,
                "ok": predicted == item["label"],
            }
        )

    n = len(y_true)
    accuracy = sum(1 for a, b in zip(y_true, y_pred) if a == b) / n if n else 0
    labels = sorted({x for x in y_true if x})
    tp = fp = fn = 0
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for a, b in zip(y_true, y_pred):
        matrix[str(a)][str(b)] += 1
        if a and b == a:
            tp += 1
        elif b and b != a:
            fp += 1
        if a and b != a:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    result = EvaluationResult(
        model_version=settings.groq_model,
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        confusion_matrix=json.dumps(matrix),
        details=json.dumps(details),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result
