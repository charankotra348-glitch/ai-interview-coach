import uuid
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_llm_client
from app.db.models import CandidateProfileRecord, JobProfileRecord, User
from app.db.session import get_db
from app.ingest.extract import MAX_BYTES, extract_text
from app.llm.client import LLMClient
from app.profiles.extractor import extract_candidate_profile, extract_job_profile
from app.profiles.schemas import CandidateProfile, JobProfile
from app.profiles.skills import compute_gap

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfileOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    profile: dict
    source_format: str
    truncated: bool
    dropped_count: int


class GapOut(BaseModel):
    matched: list[dict]
    missing_required: list[str]
    missing_nice_to_have: list[str]
    coverage: float | None


def _read_upload(file: UploadFile) -> bytes:
    # Read at most one byte past the limit: enough to detect "too large"
    # without ever loading a huge upload into memory.
    return file.file.read(MAX_BYTES + 1)


def _out(record) -> ProfileOut:
    return ProfileOut(
        id=record.id,
        created_at=record.created_at,
        profile=record.data,
        source_format=record.source_format,
        truncated=record.truncated,
        dropped_count=record.dropped_count,
    )


def _list(db: Session, model, user: User, limit: int) -> list[ProfileOut]:
    records = db.scalars(
        select(model)
        .where(model.user_id == user.id)
        .order_by(model.created_at.desc(), model.id.desc())
        .limit(limit)
    ).all()
    return [_out(r) for r in records]


@router.get("/candidate", response_model=list[ProfileOut])
def list_candidate_profiles(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Your resume profiles, newest first."""
    return _list(db, CandidateProfileRecord, user, limit)


@router.get("/job", response_model=list[ProfileOut])
def list_job_profiles(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Your job profiles, newest first."""
    return _list(db, JobProfileRecord, user, limit)


@router.post("/candidate", response_model=ProfileOut, status_code=201)
def create_candidate_profile(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    doc = extract_text(_read_upload(file), filename=file.filename or "")
    result = extract_candidate_profile(llm, doc.text)
    record = CandidateProfileRecord(
        user_id=user.id,
        data=result.profile.model_dump(),
        source_format=doc.format,
        source_chars=doc.chars,
        truncated=doc.truncated,
        parse_attempts=result.parse_attempts,
        dropped_count=len(result.dropped),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _out(record)


@router.post("/job", response_model=ProfileOut, status_code=201)
def create_job_profile(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    if (file is None) == (text is None):
        raise HTTPException(status_code=422, detail={
            "code": "bad_input", "message": "Send either a file or pasted text, not both.",
        })
    if file is not None:
        data, name = _read_upload(file), file.filename or ""
    else:
        data, name = text.encode(), "job.txt"

    doc = extract_text(data, filename=name)
    result = extract_job_profile(llm, doc.text)
    record = JobProfileRecord(
        user_id=user.id,
        data=result.profile.model_dump(),
        source_format=doc.format,
        source_chars=doc.chars,
        truncated=doc.truncated,
        parse_attempts=result.parse_attempts,
        dropped_count=len(result.dropped),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _out(record)


@router.get("/gap", response_model=GapOut)
def skill_gap(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = db.get(CandidateProfileRecord, candidate_id)
    job = db.get(JobProfileRecord, job_id)
    # 404 (not 403) for other users' profiles: don't reveal that they exist.
    if (candidate is None or job is None
            or candidate.user_id != user.id or job.user_id != user.id):
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "Profile not found.",
        })
    gap = compute_gap(
        CandidateProfile.model_validate(candidate.data),
        JobProfile.model_validate(job.data),
    )
    return GapOut(
        matched=[asdict(m) for m in gap.matched],
        missing_required=gap.missing_required,
        missing_nice_to_have=gap.missing_nice_to_have,
        coverage=gap.coverage,
    )