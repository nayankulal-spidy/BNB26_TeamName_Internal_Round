import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempts = relationship("Attempt", back_populates="student")
    learner_misconceptions = relationship("LearnerMisconception", back_populates="student")
    progress = relationship("ConceptProgress", back_populates="student")


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    domain: Mapped[str] = mapped_column(String(80), default="programming")
    description: Mapped[str] = mapped_column(Text, default="")

    questions = relationship("Question", back_populates="concept")
    misconceptions = relationship("Misconception", back_populates="concept")


class Misconception(Base):
    __tablename__ = "misconceptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"))
    description: Mapped[str] = mapped_column(Text)
    examples: Mapped[str] = mapped_column(Text, default="")
    common_patterns: Mapped[str] = mapped_column(Text, default="")
    intervention_strategy: Mapped[str] = mapped_column(Text, default="")
    assessment_strategy: Mapped[str] = mapped_column(Text, default="")

    concept = relationship("Concept", back_populates="misconceptions")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"))
    prompt: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), default="intro")
    domain: Mapped[str] = mapped_column(String(80), default="programming")
    question_type: Mapped[str] = mapped_column(String(40), default="short_answer")
    is_reassessment: Mapped[bool] = mapped_column(Boolean, default=False)
    diagnostic_followup: Mapped[str] = mapped_column(Text, default="")

    concept = relationship("Concept", back_populates="questions")
    links = relationship("QuestionMisconception", back_populates="question")


class QuestionMisconception(Base):
    __tablename__ = "question_misconceptions"
    __table_args__ = (UniqueConstraint("question_id", "misconception_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    misconception_id: Mapped[str] = mapped_column(ForeignKey("misconceptions.id"))

    question = relationship("Question", back_populates="links")
    misconception = relationship("Misconception")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    answer: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    code: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student = relationship("User", back_populates="attempts")
    question = relationship("Question")
    diagnosis = relationship("Diagnosis", back_populates="attempt", uselist=False)


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), unique=True)
    primary_misconception_id: Mapped[str | None] = mapped_column(ForeignKey("misconceptions.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, default="[]")
    alternatives: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="hybrid")
    needs_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    followup_question: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempt = relationship("Attempt", back_populates="diagnosis")
    primary_misconception = relationship("Misconception")
    interventions = relationship("Intervention", back_populates="diagnosis")


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    diagnosis_id: Mapped[str] = mapped_column(ForeignKey("diagnoses.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    misconception_id: Mapped[str | None] = mapped_column(ForeignKey("misconceptions.id"), nullable=True)
    intervention_type: Mapped[str] = mapped_column(String(40), default="explanation")
    content: Mapped[str] = mapped_column(Text)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    diagnosis = relationship("Diagnosis", back_populates="interventions")


class Reassessment(Base):
    __tablename__ = "reassessments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    diagnosis_id: Mapped[str] = mapped_column(ForeignKey("diagnoses.id"))
    misconception_id: Mapped[str | None] = mapped_column(ForeignKey("misconceptions.id"), nullable=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    answer: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    code: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_status: Mapped[str] = mapped_column(String(32), default="UNCERTAIN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearnerMisconception(Base):
    __tablename__ = "learner_misconceptions"
    __table_args__ = (UniqueConstraint("student_id", "misconception_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    misconception_id: Mapped[str] = mapped_column(ForeignKey("misconceptions.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    detections: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student = relationship("User", back_populates="learner_misconceptions")
    misconception = relationship("Misconception")


class ConceptProgress(Base):
    __tablename__ = "concept_progress"
    __table_args__ = (UniqueConstraint("student_id", "concept_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student = relationship("User", back_populates="progress")
    concept = relationship("Concept")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    model_version: Mapped[str] = mapped_column(String(120))
    dataset: Mapped[str] = mapped_column(String(80), default="java_intro_mvp")
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    precision: Mapped[float] = mapped_column(Float, default=0.0)
    recall: Mapped[float] = mapped_column(Float, default=0.0)
    f1: Mapped[float] = mapped_column(Float, default=0.0)
    confusion_matrix: Mapped[str] = mapped_column(Text, default="{}")
    details: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
