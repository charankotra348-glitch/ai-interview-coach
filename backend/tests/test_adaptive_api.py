import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_llm_client
from app.db.models import InterviewSession, Question, User
from app.db.session import get_db
from app.interview.rubrics import RUBRICS
from app.llm.client import LLMClient
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable
from app.llm.types import ProviderResponse
from app.main import create_app

pytestmark = pytest.mark.integration

NAMES = [c.name for c in RUBRICS["behavioral"]]   # Structure, Specificity, Ownership, Impact, Reflection
ANSWER = "I owned the tracking pipeline and cut false alerts by about thirty percent."
FOLLOW_UP = "How exactly did you measure the drop in false alerts?"


def question_reply(text):
    return ProviderResponse(text=json.dumps({"question": text}), model="fake-1")


def eval_reply(default, follow_up=FOLLOW_UP, **overrides):
    """Every criterion scores `default`, except the ones named in overrides."""
    scores = {n: overrides.get(n, default) for n in NAMES}
    return ProviderResponse(text=json.dumps({
        "rubric": [{"name": n, "score": s, "evidence": "", "note": "ok"} for n, s in scores.items()],
        "strengths": ["Clear ownership"],
        "improvements": ["Add more context"],
        "follow_up_question": follow_up,
    }), model="fake-1")


@pytest.fixture
def api(db):
    def make(*replies):
        provider = FakeProvider(list(replies))
        llm = LLMClient(provider, model="fake-1",
                        prices=PriceTable(version="t", models={}), sleep=lambda s: None)
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_llm_client] = lambda: llm
        return TestClient(app), provider
    return make


def start(client, max_questions=3):
    response = client.post("/sessions", json={"mode": "behavioral", "max_questions": max_questions})
    assert response.status_code == 201
    return response.json()["id"]


def ask(client, session_id):
    response = client.post(f"/sessions/{session_id}/questions")
    assert response.status_code == 200
    return response.json()


def answer(client, session_id, question_id):
    response = client.post(f"/sessions/{session_id}/questions/{question_id}/answer",
                           json={"text": ANSWER})
    assert response.status_code == 200
    return response.json()


def test_weak_criterion_gets_a_free_follow_up_then_the_interview_moves_on(api):
    client, provider = api(
        question_reply("Tell me about a time you owned a hard bug."),
        eval_reply(4, Impact=2),                    # 7/10 overall, Impact weak
        eval_reply(3, Impact=4),                    # the follow-up answer: Impact recovered
        question_reply("Describe a disagreement you had with a teammate."),
        eval_reply(3),
    )
    session_id = start(client, max_questions=3)

    q1 = ask(client, session_id)
    assert (q1["difficulty"], q1["is_follow_up"]) == (2, False)
    answer(client, session_id, q1["id"])

    calls_before = len(provider.calls)
    q2 = ask(client, session_id)
    assert q2["is_follow_up"] is True
    assert q2["text"] == FOLLOW_UP
    assert q2["rationale"] == "follow-up: Impact scored 2/5"
    assert len(provider.calls) == calls_before      # the follow-up cost no model call
    answer(client, session_id, q2["id"])

    q3 = ask(client, session_id)
    assert q3["is_follow_up"] is False
    assert q3["difficulty"] == 2                    # follows Q1's 7/10, not the follow-up
    answer(client, session_id, q3["id"])

    summary = client.get(f"/sessions/{session_id}/summary").json()
    assert summary["answered"] == 3
    assert summary["follow_ups"] == 1
    assert summary["follow_up_target_delta"] == 2.0  # Impact 2 -> 4
    assert summary["average_overall"] == 6.5         # main answers only: (7 + 6) / 2
    assert summary["difficulty_path"] == [2, 2]
    assert len(provider.calls) == 5                 # 2 questions + 3 gradings; the follow-up was free


def test_strong_answer_raises_the_next_difficulty(api):
    client, provider = api(
        question_reply("Tell me about a time you owned a hard bug."),
        eval_reply(5),                              # 10/10
        question_reply("Describe a disagreement you had with a teammate."),
    )
    session_id = start(client)
    answer(client, session_id, ask(client, session_id)["id"])

    q2 = ask(client, session_id)
    assert (q2["difficulty"], q2["is_follow_up"]) == (3, False)
    assert q2["rationale"].startswith("new topic, stretch")
    assert "stretch" in provider.calls[-1]["request"].system


def test_weak_answer_lowers_the_next_difficulty(api):
    client, _ = api(
        question_reply("Tell me about a time you owned a hard bug."),
        eval_reply(2, follow_up=""),                # 3/10, and no usable follow-up
        question_reply("Describe a disagreement you had with a teammate."),
    )
    session_id = start(client)
    answer(client, session_id, ask(client, session_id)["id"])

    q2 = ask(client, session_id)
    assert (q2["difficulty"], q2["is_follow_up"]) == (1, False)


def test_follow_up_is_idempotent_too(api):
    client, _ = api(question_reply("Tell me about a time you owned a hard bug."),
                    eval_reply(4, Impact=1))
    session_id = start(client)
    answer(client, session_id, ask(client, session_id)["id"])
    assert ask(client, session_id)["id"] == ask(client, session_id)["id"]


def test_database_rejects_a_follow_up_without_a_target(db):
    user = User(email="policy@example.com", password_hash="!")
    db.add(user)
    db.flush()
    s = InterviewSession(user_id=user.id, mode="behavioral", target_role="Intern")
    db.add(s)
    db.flush()
    parent = Question(session=s, position=1, text="Main question")
    db.add(parent)
    db.flush()
    db.add(Question(session=s, position=2, text="Follow-up", parent_question_id=parent.id))
    with pytest.raises(IntegrityError):
        db.flush()