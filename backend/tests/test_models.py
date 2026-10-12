import time
import uuid
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Answer,
    Evaluation,
    InterviewSession,
    LLMCall,
    Question,
    User,
)
from tests.conftest import alembic_config

pytestmark = pytest.mark.integration


def make_session(db, mode="behavioral"):
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-a-real-hash")
    session = InterviewSession(
        user=user, mode=mode, target_role="Software Engineering Intern"
    )
    db.add(session)
    db.flush()
    return session


def llm_call(**overrides):
    fields = dict(
        purpose="evaluation",
        provider="fake",
        model="fake-1",
        latency_ms=12.5,
        success=True,
        usage_source="unavailable",
        cost_basis="unavailable",
    )
    fields.update(overrides)
    return LLMCall(**fields)


# --- migrations -------------------------------------------------------------

def test_migrations_round_trip(migrated_engine):
    cfg = alembic_config()
    start = time.perf_counter()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    print(f"\nmigration round trip: {(time.perf_counter() - start) * 1000:.0f}ms")


def test_models_match_migrations(migrated_engine):
    # Fails if someone edits models.py without generating a migration.
    command.check(alembic_config())


# --- interview data -----------------------------------------------------------

def test_full_interview_chain_saves(db):
    session = make_session(db)
    question = Question(session=session, position=1, text="Tell me about a time...")
    answer = Answer(question=question, text="In my last project...", duration_seconds=95)
    db.add(
        Evaluation(
            answer=answer,
            overall_score=7,
            rubric=[{"name": "Impact", "score": 4, "note": "Quantified result"}],
            feedback={"strengths": ["Clear structure"]},
        )
    )
    db.flush()
    assert session.questions[0].answer.evaluation.overall_score == 7


def test_invalid_mode_is_rejected(db):
    with pytest.raises(IntegrityError):
        make_session(db, mode="coding")


def test_score_outside_1_to_10_is_rejected(db):
    session = make_session(db)
    question = Question(session=session, position=1, text="Q")
    answer = Answer(question=question, text="A")
    db.add(Evaluation(answer=answer, overall_score=11, rubric=[], feedback={}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_answer_per_question(db):
    session = make_session(db)
    question = Question(session=session, position=1, text="Q")
    db.add(question)
    db.flush()
    db.add_all([
        Answer(question_id=question.id, text="first"),
        Answer(question_id=question.id, text="second"),
    ])
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_session_removes_questions_but_keeps_llm_usage(db):
    session = make_session(db)
    question = Question(session=session, position=1, text="Q")
    db.add(question)
    db.flush()
    call = llm_call(session_id=session.id)
    db.add(call)
    db.flush()
    question_id = question.id

    db.delete(session)
    db.flush()
    db.expire_all()

    assert db.get(Question, question_id) is None
    assert db.get(LLMCall, call.id).session_id is None


# --- decision 002: usage and cost honesty -------------------------------------

def test_tokens_rejected_without_provider_usage(db):
    db.add(llm_call(input_tokens=100, output_tokens=20))
    with pytest.raises(IntegrityError):
        db.flush()


def test_cost_value_requires_a_basis(db):
    db.add(llm_call(cost_usd=Decimal("0.01")))
    with pytest.raises(IntegrityError):
        db.flush()


def test_estimate_rejected_without_price_table_version(db):
    db.add(llm_call(
        usage_source="provider",
        input_tokens=1200,
        output_tokens=300,
        cost_basis="price_table_estimate",
        cost_usd=Decimal("0.0081"),
    ))
    with pytest.raises(IntegrityError):
        db.flush()


def test_valid_estimated_call_saves(db):
    db.add(llm_call(
        usage_source="provider",
        input_tokens=1200,
        output_tokens=300,
        cost_basis="price_table_estimate",
        cost_usd=Decimal("0.0081"),
        price_table_version="2026-10-11",
    ))
    db.flush()


def test_full_chain_write_p95_under_50ms(db):
    times = []
    for i in range(20):
        start = time.perf_counter()
        session = make_session(db)
        question = Question(session=session, position=1, text=f"Q{i}")
        answer = Answer(question=question, text="A")
        db.add(Evaluation(answer=answer, overall_score=6, rubric=[], feedback={}))
        db.flush()
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"\nchain write p50={times[9]:.2f}ms p95={times[18]:.2f}ms")
    assert times[18] < 50