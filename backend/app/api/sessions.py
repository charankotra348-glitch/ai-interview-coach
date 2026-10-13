import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_llm_client
from app.db.models import (
    CandidateProfileRecord,
    InterviewSession,
    JobProfileRecord,
    Question,
    User,
)
from app.db.session import get_db
from app.interview.service import (
    AlreadyAnswered,
    SessionComplete,
    next_question,
    submit_answer,
    summarize,
)
from app.llm.client import LLMClient

router = APIRouter(prefix="/sessions", tags=["interview"])

DEFAULT_ROLE = "Software Engineering Intern"


# --- request and response shapes ------------------------------------------------

class SessionCreate(BaseModel):
    mode: Literal["behavioral", "project", "system_design"]
    candidate_profile_id: uuid.UUID | None = None
    job_profile_id: uuid.UUID | None = None
    target_role: str | None = Field(default=None, max_length=120)
    max_questions: int = Field(default=5, ge=1, le=10)


class AnswerCreate(BaseModel):
    text: str = Field(min_length=20, max_length=6000)
    duration_seconds: int | None = Field(default=None, ge=0, le=3600)


class EvaluationOut(BaseModel):
    overall: int
    rubric: list[dict]
    strengths: list[str]
    improvements: list[str]
    feedback_source: str
    follow_up_question: str
    ungrounded_evidence: int


class QuestionOut(BaseModel):
    id: uuid.UUID
    position: int
    text: str
    answer: str | None
    evaluation: EvaluationOut | None


class SessionOut(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    target_role: str
    max_questions: int
    questions: list[QuestionOut]


class SummaryOut(BaseModel):
    answered: int
    average_overall: float | None
    criteria_averages: dict[str, float]
    llm_calls: int
    failed_llm_calls: int
    estimated_cost_usd: str
    calls_without_cost: int
    llm_latency_ms: int


# --- helpers ---------------------------------------------------------------------

def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": f"{what} not found."})


def _owned_session(db: Session, session_id: uuid.UUID, user: User) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    if s is None or s.user_id != user.id:
        raise _not_found("Interview")
    return s


def _owned_profile(db: Session, model, profile_id: uuid.UUID | None, user: User):
    if profile_id is None:
        return None
    record = db.get(model, profile_id)
    if record is None or record.user_id != user.id:
        raise _not_found("Profile")
    return record


def _question_out(q: Question) -> QuestionOut:
    ev = q.answer.evaluation if q.answer else None
    return QuestionOut(
        id=q.id,
        position=q.position,
        text=q.text,
        answer=q.answer.text if q.answer else None,
        evaluation=EvaluationOut(overall=ev.overall_score, rubric=ev.rubric, **ev.feedback) if ev else None,
    )


def _session_out(s: InterviewSession) -> SessionOut:
    return SessionOut(
        id=s.id,
        mode=s.mode,
        status=s.status,
        target_role=s.target_role,
        max_questions=s.max_questions,
        questions=[_question_out(q) for q in s.questions],
    )


# --- routes ----------------------------------------------------------------------

@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = _owned_profile(db, CandidateProfileRecord, body.candidate_profile_id, user)
    job = _owned_profile(db, JobProfileRecord, body.job_profile_id, user)
    role = body.target_role or (job.data.get("title") if job else "") or DEFAULT_ROLE

    s = InterviewSession(
        user_id=user.id,
        mode=body.mode,
        target_role=role[:120],
        company=(job.data.get("company") or None) if job else None,
        max_questions=body.max_questions,
        candidate_profile_id=candidate.id if candidate else None,
        job_profile_id=job.id if job else None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.post("/{session_id}/questions", response_model=QuestionOut)
def ask_next_question(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    s = _owned_session(db, session_id, user)
    try:
        q = next_question(db, s, llm)
    except SessionComplete:
        raise HTTPException(status_code=409, detail={
            "code": "session_complete", "message": "This interview is finished.",
        })
    return _question_out(q)


@router.post("/{session_id}/questions/{question_id}/answer", response_model=QuestionOut)
def answer_question(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    s = _owned_session(db, session_id, user)
    q = db.get(Question, question_id)
    if q is None or q.session_id != s.id:
        raise _not_found("Question")
    try:
        submit_answer(db, s, q, body.text, body.duration_seconds, llm)
    except AlreadyAnswered:
        raise HTTPException(status_code=409, detail={
            "code": "already_answered", "message": "This question has already been answered.",
        })
    return _question_out(q)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _session_out(_owned_session(db, session_id, user))


@router.get("/{session_id}/summary", response_model=SummaryOut)
def get_summary(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return summarize(db, _owned_session(db, session_id, user))