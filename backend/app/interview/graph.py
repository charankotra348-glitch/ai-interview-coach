"""One interview turn as a LangGraph graph: decide, then ask a follow-up or a new question.

The graph holds no state between requests and never touches the database. The service
rebuilds the state from Postgres on every turn, so the database stays the only source
of truth (see docs/decisions/004).
"""
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.interview.focus import choose_focus
from app.interview.policy import Decision, Turn, decide
from app.interview.questions import generate_question
from app.llm.client import LLMClient
from app.profiles.schemas import CandidateProfile, JobProfile
from app.profiles.skills import compute_gap


class TurnState(TypedDict, total=False):
    # input, rebuilt from the database
    mode: str
    target_role: str
    max_questions: int
    turns: list[Turn]
    previous: list[str]             # earlier question texts, oldest first
    asked_topics: list[str]         # focus topics already used
    candidate: CandidateProfile | None
    job: JobProfile | None
    session_id: UUID | None
    # output
    decision: Decision
    question: str
    focus_topic: str
    llm_calls: int


@dataclass(frozen=True)
class TurnContext:
    llm: LLMClient


def decide_node(state: TurnState) -> dict:
    return {"decision": decide(state["turns"], state["max_questions"], state["previous"])}


def follow_up_node(state: TurnState) -> dict:
    # The grader already wrote this question while grading: no extra model call.
    topics = state["asked_topics"]
    return {
        "question": state["decision"].follow_up,
        "focus_topic": topics[-1] if topics else "",
        "llm_calls": 0,
    }


def new_question_node(state: TurnState, runtime: Runtime[TurnContext]) -> dict:
    candidate, job = state.get("candidate"), state.get("job")
    focus = choose_focus(state["mode"], candidate, job, state["asked_topics"])
    result = generate_question(
        runtime.context.llm,
        mode=state["mode"],
        focus=focus,
        target_role=state["target_role"],
        job=job,
        gap=compute_gap(candidate, job) if candidate and job else None,
        previous=state["previous"],
        difficulty=state["decision"].difficulty,
        session_id=state.get("session_id"),
    )
    return {
        "question": result.value.question,
        "focus_topic": focus.topic[:200],
        "llm_calls": len(result.calls),
    }


def route(state: TurnState) -> str:
    return state["decision"].action


def build_turn_graph():
    graph = StateGraph(TurnState, context_schema=TurnContext)
    graph.add_node("decide", decide_node)
    graph.add_node("follow_up", follow_up_node)
    graph.add_node("new_question", new_question_node)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges("decide", route, {
        "follow_up": "follow_up",
        "new_topic": "new_question",
        "finish": END,
    })
    graph.add_edge("follow_up", END)
    graph.add_edge("new_question", END)
    return graph.compile()


TURN_GRAPH = build_turn_graph()  # compiled once at import; safe to share between requests


def run_turn(state: TurnState, llm: LLMClient) -> TurnState:
    return TURN_GRAPH.invoke(state, context=TurnContext(llm=llm))