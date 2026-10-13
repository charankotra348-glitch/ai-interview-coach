import json

from app.interview.graph import TURN_GRAPH, run_turn
from app.llm.client import LLMClient
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable
from app.llm.types import ProviderResponse
from tests.test_policy import FOLLOW_UP, graded
from tests.timing import measure_ms, percentile


def client_with(*texts):
    provider = FakeProvider([ProviderResponse(text=json.dumps({"question": t}), model="fake-1")
                             for t in texts])
    return LLMClient(provider, model="fake-1", prices=PriceTable(version="t", models={}),
                     sleep=lambda s: None), provider


def state(turns, previous, topics=("taking ownership of a problem",)):
    return {"mode": "behavioral", "target_role": "Intern", "max_questions": 5,
            "turns": turns, "previous": previous, "asked_topics": list(topics),
            "candidate": None, "job": None, "session_id": None}


def test_graph_follow_up_makes_no_model_call():
    client, provider = client_with()
    out = run_turn(state([graded(4, weakest=("Impact", 2))], ["Q1"]), client)
    assert out["decision"].action == "follow_up"
    assert out["question"] == FOLLOW_UP
    assert out["focus_topic"] == "taking ownership of a problem"   # same topic as its parent
    assert out["llm_calls"] == 0
    assert provider.calls == []


def test_graph_new_topic_asks_at_the_new_difficulty():
    client, provider = client_with("Describe a disagreement you had with a teammate.")
    out = run_turn(state([graded(9, weakest=("Impact", 4))], ["Q1"]), client)
    assert out["decision"].action == "new_topic"
    assert out["question"] == "Describe a disagreement you had with a teammate."
    assert out["focus_topic"] == "a disagreement with a teammate"  # next unasked topic
    assert out["llm_calls"] == 1
    assert "stretch" in provider.calls[0]["request"].system      # 9/10 raised it to 3


def test_graph_finish_asks_nothing():
    client, provider = client_with()
    s = state([graded(6)], ["Q1"])
    s["max_questions"] = 1
    out = run_turn(s, client)
    assert out["decision"].action == "finish"
    assert "question" not in out
    assert provider.calls == []


def test_graph_shape():
    nodes = set(TURN_GRAPH.get_graph().nodes)
    assert {"decide", "follow_up", "new_question"} <= nodes


def test_graph_overhead_p95_under_5ms():
    """Time spent in LangGraph and the policy, with model calls excluded."""
    client, _ = client_with()
    s = state([graded(4, weakest=("Impact", 2))], ["Q1"])  # the follow-up path: no model call
    times = measure_ms(lambda: run_turn(s, client))
    p50, p95 = percentile(times, 0.50), percentile(times, 0.95)
    print(f"\nturn graph overhead: p50={p50:.2f} ms  p95={p95:.2f} ms")
    assert p95 < 5