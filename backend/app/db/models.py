import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Predictable constraint names, so migrations can find and change them later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('behavioral', 'project', 'system_design')", name="mode_valid"
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')", name="status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(20))
    target_role: Mapped[str] = mapped_column(String(120))
    company: Mapped[Optional[str]] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    parent_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    answer: Mapped[Optional["Answer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class Answer(TimestampMixin, Base):
    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="duration_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True
    )
    text: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    question: Mapped[Question] = relationship(back_populates="answer")
    evaluation: Mapped[Optional["Evaluation"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan"
    )


class Evaluation(TimestampMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        CheckConstraint("overall_score BETWEEN 1 AND 10", name="overall_score_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), unique=True
    )
    llm_call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("llm_calls.id", ondelete="SET NULL")
    )
    overall_score: Mapped[int] = mapped_column(Integer)
    rubric: Mapped[list] = mapped_column(JSONB)     # [{"name", "score", "note"}]
    feedback: Mapped[dict] = mapped_column(JSONB)   # strengths, improvements, ...

    answer: Mapped[Answer] = relationship(back_populates="evaluation")


class LLMCall(TimestampMixin, Base):
    """One row per model call. Enforces decision 002 at the database level."""

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(
            "usage_source IN ('provider', 'unavailable')", name="usage_source_valid"
        ),
        CheckConstraint(
            "cost_basis IN ('provider_billing', 'price_table_estimate', 'unavailable')",
            name="cost_basis_valid",
        ),
        # Token counts may only be stored if the provider reported them.
        CheckConstraint(
            "usage_source = 'provider' OR "
            "(input_tokens IS NULL AND output_tokens IS NULL)",
            name="tokens_only_from_provider",
        ),
        # A cost value exists exactly when there is a basis for it.
        CheckConstraint(
            "(cost_basis = 'unavailable') = (cost_usd IS NULL)",
            name="cost_matches_basis",
        ),
        # Estimates need provider tokens and a dated price table.
        CheckConstraint(
            "cost_basis <> 'price_table_estimate' OR "
            "(usage_source = 'provider' AND price_table_version IS NOT NULL)",
            name="estimate_needs_usage_and_prices",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="SET NULL"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(40))      # "question", "evaluation"
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    latency_ms: Mapped[float] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(Boolean)
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    usage_source: Mapped[str] = mapped_column(String(20))
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6))
    cost_basis: Mapped[str] = mapped_column(String(30))
    price_table_version: Mapped[Optional[str]] = mapped_column(String(20))

class CandidateProfileRecord(TimestampMixin, Base):
    """A bounded profile extracted from a resume. The resume itself is never stored."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("source_format IN ('pdf', 'docx', 'text')", name="source_format_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict] = mapped_column(JSONB)
    source_format: Mapped[str] = mapped_column(String(10))
    source_chars: Mapped[int] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean)
    parse_attempts: Mapped[int] = mapped_column(Integer)
    dropped_count: Mapped[int] = mapped_column(Integer)


class JobProfileRecord(TimestampMixin, Base):
    __tablename__ = "job_profiles"
    __table_args__ = (
        CheckConstraint("source_format IN ('pdf', 'docx', 'text')", name="source_format_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict] = mapped_column(JSONB)
    source_format: Mapped[str] = mapped_column(String(10))
    source_chars: Mapped[int] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean)
    parse_attempts: Mapped[int] = mapped_column(Integer)
    dropped_count: Mapped[int] = mapped_column(Integer)
