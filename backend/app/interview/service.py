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
from app.interview.graph import TurnState, run_turn
from app.interview.policy import Turn, weakest_criterion
from app.llm.client import LLMClient
from app.profiles.schemas import CandidateProfile, JobProfile


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


def _turn(q: Question) -> Turn:
    ev = q.answer.evaluation if q.answer else None
    return Turn(
        is_follow_up=q.parent_question_id is not None,
        difficulty=q.difficulty,
        overall=ev.overall_score if ev else None,
        weakest=weakest_criterion(ev.rubric) if ev else None,
        follow_up_question=ev.feedback.get("follow_up_question", "") if ev else "",
    )


def _turn_state(db: Session, s: InterviewSession) -> TurnState:
    candidate, job = load_profiles(db, s)
    return {
        "mode": s.mode,
        "target_role": s.target_role,
        "max_questions": s.max_questions,
        "turns": [_turn(q) for q in s.questions],
        "previous": [q.text for q in s.questions],
        "asked_topics": [q.focus_topic for q in s.questions if q.focus_topic],
        "candidate": candidate,
        "job": job,
        "session_id": s.id,
    }


def next_question(db: Session, s: InterviewSession, llm: LLMClient) -> Question:
    pending = current_question(s)
    if pending is not None:
        return pending  # idempotent: never generate a second unanswered question
    if s.status != "active":
        raise SessionComplete()

    result = run_turn(_turn_state(db, s), llm)
    decision = result["decision"]
    if decision.action == "finish":
        raise SessionComplete()

    follow_up = decision.action == "follow_up"
    question = Question(
        session=s,
        parent_question_id=s.questions[-1].id if follow_up else None,
        position=len(s.questions) + 1,
        text=result["question"],
        focus_topic=result["focus_topic"] or None,
        difficulty=decision.difficulty,
        rationale=decision.rationale[:200],
        target_criterion=decision.target if follow_up else None,
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


def _score(evaluation: EvaluationRecord, criterion: str) -> int | None:
    for item in evaluation.rubric:
        if item["name"] == criterion:
            return item["score"]
    return None


def summarize(db: Session, s: InterviewSession) -> dict:
    graded = [q for q in s.questions if q.answer and q.answer.evaluation]
    main = [q for q in graded if q.parent_question_id is None]
    follow_ups = [q for q in graded if q.parent_question_id is not None]

    # Scores come from main answers only. Follow-ups are short by design, so they are
    # measured only on the criterion they targeted: did probing help the candidate recover?
    overall = [q.answer.evaluation.overall_score for q in main]
    per_criterion: dict[str, list[int]] = {}
    for q in main:
        for item in q.answer.evaluation.rubric:
            per_criterion.setdefault(item["name"], []).append(item["score"])

    by_id = {q.id: q for q in graded}
    deltas = []
    for f in follow_ups:
        parent = by_id.get(f.parent_question_id)
        before = _score(parent.answer.evaluation, f.target_criterion) if parent else None
        after = _score(f.answer.evaluation, f.target_criterion)
        if before is not None and after is not None:
            deltas.append(after - before)

    calls = db.scalars(select(LLMCall).where(LLMCall.session_id == s.id)).all()
    priced = [c.cost_usd for c in calls if c.cost_usd is not None]

    return {
        "answered": len(graded),
        "average_overall": round(sum(overall) / len(overall), 1) if overall else None,
        "criteria_averages": {
            name: round(sum(scores) / len(scores), 2) for name, scores in per_criterion.items()
        },
        "follow_ups": len(follow_ups),
        "follow_up_target_delta": round(sum(deltas) / len(deltas), 2) if deltas else None,
        "difficulty_path": [q.difficulty for q in s.questions if q.parent_question_id is None],
        "llm_calls": len(calls),
        "failed_llm_calls": sum(1 for c in calls if not c.success),
        "estimated_cost_usd": str(sum(priced, Decimal(0))),
        "calls_without_cost": len(calls) - len(priced),
        "llm_latency_ms": round(sum(c.latency_ms for c in calls)),
    }