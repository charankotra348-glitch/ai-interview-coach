import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    Answer,
    CandidateProfileRecord,
    InterviewSession,
    JobProfileRecord,
    Question,
    User,
)
from app.db.session import get_db
from app.main import create_app
from tests.auth_helpers import sign_in

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(db, fast_hashing):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def profile(model, user_id, minutes_ago, **data):
    # created_at is set explicitly: inside one test transaction, now() never changes.
    return model(user_id=user_id, data=data, source_format="text", source_chars=10,
                 truncated=False, parse_attempts=1, dropped_count=0,
                 created_at=NOW - timedelta(minutes=minutes_ago))


def test_profiles_are_listed_newest_first_and_only_your_own(client, db):
    me = uuid.UUID(sign_in(client))
    other = User(email="other@example.com", password_hash="!")
    db.add(other)
    db.flush()
    db.add_all([
        profile(CandidateProfileRecord, me, 30, headline="old resume"),
        profile(CandidateProfileRecord, me, 5, headline="new resume"),
        profile(CandidateProfileRecord, other.id, 1, headline="someone else"),
        profile(JobProfileRecord, me, 10, title="ML Intern"),
    ])
    db.flush()

    resumes = client.get("/profiles/candidate").json()
    assert [r["profile"]["headline"] for r in resumes] == ["new resume", "old resume"]
    assert "created_at" in resumes[0]
    assert [j["profile"]["title"] for j in client.get("/profiles/job").json()] == ["ML Intern"]
    assert len(client.get("/profiles/candidate", params={"limit": 1}).json()) == 1


def test_limit_is_bounded(client):
    sign_in(client)
    assert client.get("/profiles/candidate", params={"limit": 0}).status_code == 422
    assert client.get("/profiles/job", params={"limit": 51}).status_code == 422


def test_interviews_are_listed_with_progress(client, db):
    me = uuid.UUID(sign_in(client))
    older = InterviewSession(user_id=me, mode="behavioral", target_role="Intern",
                             max_questions=3, created_at=NOW - timedelta(days=1))
    newer = InterviewSession(user_id=me, mode="project", target_role="ML Intern",
                             max_questions=5, created_at=NOW)
    db.add_all([older, newer])
    db.flush()
    answered = Question(session=older, position=1, text="Q1")
    db.add_all([answered, Question(session=older, position=2, text="Q2")])
    db.flush()
    db.add(Answer(question=answered, text="An answer that is long enough."))
    db.flush()

    items = client.get("/sessions").json()
    assert [i["mode"] for i in items] == ["project", "behavioral"]
    assert items[1]["answered"] == 1                    # two asked, one answered
    assert items[1]["max_questions"] == 3
    assert items[0]["answered"] == 0


def test_a_new_user_sees_empty_lists(client):
    sign_in(client)
    assert client.get("/profiles/candidate").json() == []
    assert client.get("/sessions").json() == []