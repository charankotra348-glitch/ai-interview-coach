from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Answer,
    CandidateProfileRecord,
    Evaluation as EvaluationRecord,
    InterviewSession,
    JobProfileRecord,
    LLMCall,
    Question,
)
from app.interview.evaluation import evaluate_answer
from app.interview.focus import choose_focus
from app.interview.questions import generate_question
from app.llm.client import LLMClient
from app.profiles.schemas import CandidateProfile, JobProfile
from app.profiles.skills import compute_gap


class SessionComplete(Exception):
    pass


class AlreadyAnswered(Exception):
    pass


def load_profiles(db: Session, s: InterviewSession):
    candidate = db.get(CandidateProfileRecord, s.candidate_profile_id) if s.candidate_profile_id else None
    job = db.get(JobProfileRecord, s.job_profile_id) if s.job_profile_id else None
    return (
        CandidateProfile.model_validate(candidate.data) if candidate else None,
        JobProfile.model_validate(job.data) if job else None,
    )


def current_question(s: InterviewSession) -> Question | None:
    for q in s.questions:
        if q.answer is None:
            return q
    return None


def next_question(db: Session, s: InterviewSession, llm: LLMClient) -> Question:
    pending = current_question(s)
    if pending is not None:
        return pending  # idempotent: never generate a second unanswered question

    if s.status != "active" or len(s.questions) >= s.max_questions:
        raise SessionComplete()

    candidate, job = load_profiles(db, s)
    gap = compute_gap(candidate, job) if candidate and job else None
    asked = [q.focus_topic for q in s.questions if q.focus_topic]
    focus = choose_focus(s.mode, candidate, job, asked)

    result = generate_question(
        llm,
        mode=s.mode,
        focus=focus,
        target_role=s.target_role,
        job=job,
        gap=gap,
        previous=[q.text for q in s.questions],
        session_id=s.id,
    )
    question = Question(
        session=s,
        position=len(s.questions) + 1,
        text=result.value.question,
        focus_topic=focus.topic[:200],
    )
    # SQLAlchemy 2.0: linking to the parent does not add the object; add it explicitly.
    db.add(question)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request created this position first; return that one instead.
        db.rollback()
        return current_question(s)
    return question


def submit_answer(db: Session, s: InterviewSession, q: Question, text: str,
                  duration_seconds: int | None, llm: LLMClient) -> EvaluationRecord:
    if q.answer is not None:
        raise AlreadyAnswered()

    # Grade first. If this fails, nothing is stored and the user can resubmit.
    ev = evaluate_answer(llm, mode=s.mode, question=q.text, answer=text, session_id=s.id).value

    answer = Answer(question=q, text=text, duration_seconds=duration_seconds)
    record = EvaluationRecord(
        answer=answer,
        overall_score=ev.overall,
        rubric=[item.model_dump() for item in ev.rubric],
        feedback={
            "strengths": ev.strengths,
            "improvements": ev.improvements,
            "feedback_source": ev.feedback_source,
            "follow_up_question": ev.follow_up_question,
            "ungrounded_evidence": ev.ungrounded_evidence,
        },
    )
    db.add(answer)
    db.add(record)

    answered = sum(1 for question in s.questions if question.answer is not None)
    if answered >= s.max_questions:
        s.status = "completed"
        s.completed_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AlreadyAnswered()  # a concurrent submission won the race
    return record


def summarize(db: Session, s: InterviewSession) -> dict:
    evaluations = [q.answer.evaluation for q in s.questions if q.answer and q.answer.evaluation]
    overall = [e.overall_score for e in evaluations]

    per_criterion: dict[str, list[int]] = {}
    for e in evaluations:
        for item in e.rubric:
            per_criterion.setdefault(item["name"], []).append(item["score"])

    calls = db.scalars(select(LLMCall).where(LLMCall.session_id == s.id)).all()
    priced = [c.cost_usd for c in calls if c.cost_usd is not None]

    return {
        "answered": len(evaluations),
        "average_overall": round(sum(overall) / len(overall), 1) if overall else None,
        "criteria_averages": {
            name: round(sum(scores) / len(scores), 2) for name, scores in per_criterion.items()
        },
        "llm_calls": len(calls),
        "failed_llm_calls": sum(1 for c in calls if not c.success),
        "estimated_cost_usd": str(sum(priced, Decimal(0))),
        "calls_without_cost": len(calls) - len(priced),
        "llm_latency_ms": round(sum(c.latency_ms for c in calls)),
    }