import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.db.models import InterviewSession, JobProfileRecord, User
from app.db.session import get_db
from app.interview.rubrics import RUBRICS
from app.llm.client import LLMClient
from app.llm.errors import ProviderUnavailable
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable
from app.llm.types import ProviderResponse
from app.main import create_app
from tests.auth_helpers import sign_in

pytestmark = pytest.mark.integration

NAMES = [c.name for c in RUBRICS["behavioral"]]
ANSWER = "I owned the tracking pipeline and cut false alerts by about thirty percent."


def reply(obj) -> ProviderResponse:
    return ProviderResponse(text=json.dumps(obj), model="fake-1")


def question_reply(text):
    return reply({"question": text})


def eval_reply(score):
    return reply({
        "rubric": [{"name": n, "score": score, "evidence": "", "note": "ok"} for n in NAMES],
        "strengths": ["Clear ownership"],
        "improvements": ["Add more context"],
        "follow_up_question": "How did you measure that?",
    })


@pytest.fixture
def api(db, fast_hashing):
    def make(*replies):
        provider = FakeProvider(list(replies))
        llm = LLMClient(provider, model="fake-1",
                        prices=PriceTable(version="t", models={}), sleep=lambda s: None)
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_llm_client] = lambda: llm
        client = TestClient(app)
        sign_in(client)
        return client, provider
    return make


def start(client, **body):
    response = client.post("/sessions", json={"mode": "behavioral", **body})
    assert response.status_code == 201
    return response.json()["id"]


def answer(client, session_id, question_id, text=ANSWER):
    return client.post(f"/sessions/{session_id}/questions/{question_id}/answer", json={"text": text})


# --- the interview flow ---------------------------------------------------------

def test_creating_a_session_makes_no_ai_call(api):
    client, provider = api()
    session_id = start(client)
    body = client.get(f"/sessions/{session_id}").json()
    assert body["status"] == "active"
    assert body["questions"] == []
    assert provider.calls == []


def test_next_question_is_idempotent_until_answered(api):
    client, provider = api(question_reply("Tell me about a time you owned a hard bug."))
    session_id = start(client)
    first = client.post(f"/sessions/{session_id}/questions").json()
    again = client.post(f"/sessions/{session_id}/questions").json()
    assert first["id"] == again["id"]
    assert len(provider.calls) == 1        # the second request reused the stored question


def test_answer_is_evaluated_and_stored(api):
    client, _ = api(question_reply("Tell me about a time you owned a hard bug."), eval_reply(4))
    session_id = start(client)
    q = client.post(f"/sessions/{session_id}/questions").json()

    result = answer(client, session_id, q["id"])
    assert result.status_code == 200
    evaluation = result.json()["evaluation"]
    assert evaluation["overall"] == 8                      # all 4s -> 8, computed by our code
    assert evaluation["strengths"] == ["Clear ownership"]

    stored = client.get(f"/sessions/{session_id}").json()["questions"][0]
    assert stored["answer"] == ANSWER
    assert stored["evaluation"]["overall"] == 8


def test_full_interview_completes_and_summarizes(api):
    client, _ = api(
        question_reply("Tell me about a time you owned a hard bug."), eval_reply(4),
        question_reply("Describe a disagreement with a teammate about a design."), eval_reply(2),
    )
    session_id = start(client, max_questions=2)
    for _ in range(2):
        q = client.post(f"/sessions/{session_id}/questions").json()
        assert answer(client, session_id, q["id"]).status_code == 200

    assert client.get(f"/sessions/{session_id}").json()["status"] == "completed"
    more = client.post(f"/sessions/{session_id}/questions")
    assert more.status_code == 409
    assert more.json()["detail"]["code"] == "session_complete"

    summary = client.get(f"/sessions/{session_id}/summary").json()
    assert summary["answered"] == 2
    assert summary["average_overall"] == 5.5               # (8 + 3) / 2
    assert summary["criteria_averages"]["Ownership"] == 3.0


# --- rejections -----------------------------------------------------------------

def test_short_answer_is_rejected_without_an_ai_call(api):
    client, provider = api(question_reply("Tell me about a time you owned a hard bug."))
    session_id = start(client)
    q = client.post(f"/sessions/{session_id}/questions").json()
    assert answer(client, session_id, q["id"], text="idk").status_code == 422
    assert len(provider.calls) == 1                        # only the question was generated


def test_answering_twice_is_rejected(api):
    client, _ = api(question_reply("Tell me about a time you owned a hard bug."), eval_reply(3))
    session_id = start(client)
    q = client.post(f"/sessions/{session_id}/questions").json()
    assert answer(client, session_id, q["id"]).status_code == 200
    second = answer(client, session_id, q["id"])
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "already_answered"


def test_failed_grading_stores_nothing(api):
    client, _ = api(question_reply("Tell me about a time you owned a hard bug."),
                    ProviderUnavailable(), ProviderUnavailable(), ProviderUnavailable())
    session_id = start(client)
    q = client.post(f"/sessions/{session_id}/questions").json()
    failed = answer(client, session_id, q["id"])
    assert failed.status_code == 503
    assert failed.json()["detail"]["retryable"] is True
    assert client.get(f"/sessions/{session_id}").json()["questions"][0]["answer"] is None


def test_question_from_another_session_is_404(api):
    client, _ = api(question_reply("Tell me about a time you owned a hard bug."))
    first = start(client)
    q = client.post(f"/sessions/{first}/questions").json()
    second = start(client)
    assert answer(client, second, q["id"]).status_code == 404


# --- ownership ------------------------------------------------------------------

def _other_user(db):
    other = User(email="other@example.com", password_hash="!")
    db.add(other)
    db.flush()
    return other


def test_cannot_read_another_users_session(api, db):
    other = _other_user(db)
    foreign = InterviewSession(user_id=other.id, mode="behavioral", target_role="Intern")
    db.add(foreign)
    db.flush()
    client, _ = api()
    assert client.get(f"/sessions/{foreign.id}").status_code == 404
    assert client.post(f"/sessions/{foreign.id}/questions").status_code == 404


def test_cannot_start_a_session_with_another_users_profile(api, db):
    other = _other_user(db)
    job = JobProfileRecord(user_id=other.id, data={"title": "x"}, source_format="text",
                           source_chars=1, truncated=False, parse_attempts=1, dropped_count=0)
    db.add(job)
    db.flush()
    client, _ = api()
    response = client.post("/sessions", json={"mode": "behavioral", "job_profile_id": str(job.id)})
    assert response.status_code == 404