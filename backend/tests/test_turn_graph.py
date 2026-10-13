import json

from app.interview.graph import TURN_GRAPH, run_turn
from app.llm.client import LLMClient
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable
from app.llm.types import ProviderResponse
from tests.test_policy import ANSWER, FOLLOW_UP, QUESTION, graded
from tests.timing import measure_ms, percentile


def client_with(*texts):
    provider = FakeProvider([ProviderResponse(text=json.dumps({"question": t}), model="fake-1")
                             for t in texts])
    return LLMClient(provider, model="fake-1", prices=PriceTable(version="t", models={}),
                     sleep=lambda s: None), provider


def state(turns, max_questions=5):
    return {"mode": "behavioral", "target_role": "Intern", "max_questions": max_questions,
            "turns": turns, "previous": [QUESTION], "last_question": QUESTION,
            "last_answer": ANSWER, "asked_topics": ["taking ownership of a problem"],
            "candidate": None, "job": None, "session_id": None}


def test_graph_follow_up_targets_the_weakest_criterion():
    client, provider = client_with(FOLLOW_UP)
    out = run_turn(state([graded(7, weakest=("Reflection", 2))]), client)
    assert out["decision"].action == "follow_up"
    assert out["question"] == FOLLOW_UP
    assert out["focus_topic"] == "taking ownership of a problem"   # same topic as its parent
    assert out["llm_calls"] == 1
    req = provider.calls[0]["request"]
    assert req.purpose == "follow_up"
    assert "Ask only about Reflection" in req.system
    assert ANSWER in req.messages[0].content


def test_graph_new_topic_asks_at_the_new_difficulty():
    client, provider = client_with("Describe a disagreement you had with a teammate.")
    out = run_turn(state([graded(9, weakest=("Impact", 4))]), client)
    assert out["decision"].action == "new_topic"
    assert out["question"] == "Describe a disagreement you had with a teammate."
    assert out["focus_topic"] == "a disagreement with a teammate"  # next unasked topic
    assert out["llm_calls"] == 1
    assert "stretch" in provider.calls[0]["request"].system      # 9/10 raised it to 3


def test_graph_finish_asks_nothing():
    client, provider = client_with()
    out = run_turn(state([graded(6)], max_questions=1), client)
    assert out["decision"].action == "finish"
    assert "question" not in out
    assert provider.calls == []


def test_graph_shape():
    nodes = set(TURN_GRAPH.get_graph().nodes)
    assert {"decide", "follow_up", "new_question"} <= nodes


class RepeatingProvider(FakeProvider):
    """Always gives the same reply, so the timing loop never runs out of script."""

    def complete(self, request, *, model, timeout_s):
        self.calls.append(None)
        return ProviderResponse(text=json.dumps({"question": FOLLOW_UP}), model=model)


def test_graph_overhead_p95_under_5ms():
    """Time spent in LangGraph, the policy and our LLM plumbing, with a model that answers instantly."""
    client = LLMClient(RepeatingProvider(), model="fake-1",
                       prices=PriceTable(version="t", models={}), sleep=lambda s: None)
    s = state([graded(7, weakest=("Reflection", 2))])
    times = measure_ms(lambda: run_turn(s, client))
    p50, p95 = percentile(times, 0.50), percentile(times, 0.95)
    print(f"\nturn graph overhead: p50={p50:.2f} ms  p95={p95:.2f} ms")
    assert p95 < 5