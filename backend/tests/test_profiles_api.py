import json
import time

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import get_llm_client
from app.db.models import CandidateProfileRecord, JobProfileRecord, User
from app.db.session import get_db
from app.llm.client import LLMClient
from app.llm.errors import ProviderUnavailable
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable
from app.llm.types import ProviderResponse
from app.main import create_app

pytestmark = pytest.mark.integration

RESUME = (
    "Jordan Example, jordan@example.com\n"
    "Skills: Python, FastAPI, Postgres, Docker\n"
    "Built a RAG system with Python and pgvector."
)
JOB = "Software Engineering Intern. Required: Python, PostgreSQL, Kubernetes. Nice to have: AWS."

CANDIDATE_REPLY = {
    "headline": "Backend and AI student",
    "skills": ["Python", "FastAPI", "Postgres", "Docker"],
    "projects": [{"name": "RAG system", "summary": "", "technologies": ["Python", "pgvector"]}],
}
JOB_REPLY = {
    "title": "Software Engineering Intern",
    "required_skills": ["Python", "PostgreSQL", "Kubernetes"],
    "nice_to_have_skills": ["AWS"],
}


def reply(obj) -> ProviderResponse:
    return ProviderResponse(text=json.dumps(obj), model="fake-1")


@pytest.fixture
def api(db):
    """Build a TestClient whose LLM plays back the given replies, in order, across requests."""
    def make(*replies):
        provider = FakeProvider(list(replies))
        llm = LLMClient(provider, model="fake-1",
                        prices=PriceTable(version="t", models={}), sleep=lambda s: None)
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_llm_client] = lambda: llm
        return TestClient(app)
    return make


def upload_resume(client, text=RESUME, name="resume.txt"):
    return client.post("/profiles/candidate", files={"file": (name, text.encode(), "text/plain")})


# --- happy paths ------------------------------------------------------------------

def test_resume_upload_creates_a_stored_profile(api, db):
    response = upload_resume(api(reply(CANDIDATE_REPLY)))
    assert response.status_code == 201
    body = response.json()
    assert "FastAPI" in body["profile"]["skills"]
    assert body["source_format"] == "text"
    assert body["dropped_count"] == 0

    record = db.get(CandidateProfileRecord, body["id"])
    assert db.get(User, record.user_id).email == deps.DEV_EMAIL


def test_job_from_pasted_text(api):
    response = api(reply(JOB_REPLY)).post("/profiles/job", data={"text": JOB})
    assert response.status_code == 201
    assert response.json()["profile"]["title"] == "Software Engineering Intern"


def test_gap_end_to_end(api):
    client = api(reply(CANDIDATE_REPLY), reply(JOB_REPLY))
    candidate_id = upload_resume(client).json()["id"]
    job_id = client.post("/profiles/job", data={"text": JOB}).json()["id"]

    gap = client.get("/profiles/gap", params={"candidate_id": candidate_id, "job_id": job_id})
    assert gap.status_code == 200
    body = gap.json()
    assert body["coverage"] == 0.67
    assert body["missing_required"] == ["Kubernetes"]
    assert body["missing_nice_to_have"] == ["AWS"]


# --- rejections -------------------------------------------------------------------

def test_job_needs_exactly_one_input(api):
    response = api().post("/profiles/job")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_input"


def test_unsupported_file_type_is_422(api):
    response = upload_resume(api(), text="\x89PNG fake image", name="photo.png")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_type"


def test_oversized_upload_is_rejected(api):
    client = api()
    big = b"%PDF" + b"0" * (5 * 1024 * 1024)
    response = client.post("/profiles/candidate", files={"file": ("big.pdf", big, "application/pdf")})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "too_large"


def test_ai_outage_returns_retryable_503(api):
    client = api(ProviderUnavailable(), ProviderUnavailable(), ProviderUnavailable())
    response = upload_resume(client)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_unavailable"
    assert response.json()["detail"]["retryable"] is True


# --- security ---------------------------------------------------------------------

def test_cannot_use_another_users_profile(api, db):
    other = User(email="other@example.com", password_hash="!")
    db.add(other)
    db.flush()
    foreign_job = JobProfileRecord(
        user_id=other.id, data=JOB_REPLY, source_format="text",
        source_chars=10, truncated=False, parse_attempts=1, dropped_count=0,
    )
    db.add(foreign_job)
    db.flush()

    client = api(reply(CANDIDATE_REPLY))
    candidate_id = upload_resume(client).json()["id"]
    response = client.get("/profiles/gap",
                          params={"candidate_id": candidate_id, "job_id": str(foreign_job.id)})
    assert response.status_code == 404


def test_dev_user_is_refused_outside_development(api, monkeypatch):
    monkeypatch.setattr(deps.settings, "environment", "production")
    response = upload_resume(api(reply(CANDIDATE_REPLY)))
    assert response.status_code == 401


# --- metric -----------------------------------------------------------------------

def test_upload_overhead_without_model_p95_under_100ms(api):
    client = api(*[reply(CANDIDATE_REPLY) for _ in range(20)])
    times = []
    for _ in range(20):
        start = time.perf_counter()
        assert upload_resume(client).status_code == 201
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    print(f"\nupload overhead (no model) p50={times[9]:.1f}ms p95={times[18]:.1f}ms")
    assert times[18] < 100