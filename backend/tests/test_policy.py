import pytest

from app.interview.focus import choose_focus
from app.interview.policy import (
    START_DIFFICULTY,
    Turn,
    decide,
    next_difficulty,
    usable_follow_up,
    weakest_criterion,
)
from app.interview.questions import build_question_system, generate_question
from app.llm.client import LLMClient
from app.llm.fake import FakeProvider
from app.llm.pricing import PriceTable

FOLLOW_UP = "How exactly did you measure the drop in false alerts?"


def graded(overall, weakest=("Impact", 3), follow_up=FOLLOW_UP, difficulty=2, is_follow_up=False):
    return Turn(is_follow_up=is_follow_up, difficulty=difficulty, overall=overall,
                weakest=weakest, follow_up_question=follow_up)


# --- the policy: what to ask next --------------------------------------------------

def test_first_question_is_a_standard_new_topic():
    d = decide([], max_questions=5, previous=[])
    assert (d.action, d.difficulty) == ("new_topic", START_DIFFICULTY)


def test_weak_criterion_earns_one_follow_up():
    d = decide([graded(5, weakest=("Impact", 2))], max_questions=5, previous=["Q1"])
    assert d.action == "follow_up"
    assert d.follow_up == FOLLOW_UP
    assert d.target == "Impact"
    assert d.difficulty == 2                     # a follow-up stays at the topic's level
    assert "Impact scored 2/5" in d.rationale


def test_no_follow_up_on_a_follow_up():
    turns = [graded(5, weakest=("Impact", 2)),
             graded(3, weakest=("Impact", 1), is_follow_up=True)]
    assert decide(turns, max_questions=5, previous=["Q1", FOLLOW_UP]).action == "new_topic"


def test_adequate_answer_moves_on():
    d = decide([graded(6, weakest=("Impact", 3))], max_questions=5, previous=["Q1"])
    assert d.action == "new_topic"


def test_unusable_follow_up_moves_on_instead():
    weak = ("Impact", 1)
    assert decide([graded(4, weak, follow_up="")], 5, ["Q1"]).action == "new_topic"
    assert decide([graded(4, weak, follow_up="Why?")], 5, ["Q1"]).action == "new_topic"
    # The grader suggested something we already asked: not a follow-up.
    assert decide([graded(4, weak)], 5, ["Q1", FOLLOW_UP]).action == "new_topic"


def test_question_limit_finishes_even_with_a_weak_answer():
    d = decide([graded(3, weakest=("Impact", 1))], max_questions=1, previous=["Q1"])
    assert d.action == "finish"


def test_ungraded_last_question_is_an_error():
    with pytest.raises(ValueError):
        decide([Turn(is_follow_up=False, difficulty=2)], max_questions=5, previous=["Q1"])


@pytest.mark.parametrize("current, overall, expected", [
    (2, 8, 3), (2, 10, 3), (3, 9, 3),            # strong: up, capped at 3
    (2, 4, 1), (2, 1, 1), (1, 2, 1),             # weak: down, floored at 1
    (2, 5, 2), (2, 7, 2),                        # in between: unchanged
])
def test_difficulty_steps_and_clamps(current, overall, expected):
    assert next_difficulty(current, overall) == expected


def test_difficulty_follows_the_main_answer_not_the_follow_up():
    # Main answer 8/10 (strong) with one weak criterion; the short follow-up scored 3/10.
    turns = [graded(8, weakest=("Impact", 2)),
             graded(3, weakest=("Structure", 1), is_follow_up=True)]
    d = decide(turns, max_questions=5, previous=["Q1", FOLLOW_UP])
    assert (d.action, d.difficulty) == ("new_topic", 3)
    assert "harder" in d.rationale


def test_weakest_criterion_breaks_ties_by_rubric_order():
    rubric = [{"name": "Structure", "score": 4}, {"name": "Impact", "score": 2},
              {"name": "Reflection", "score": 2}]
    assert weakest_criterion(rubric) == ("Impact", 2)
    assert weakest_criterion([]) is None


def test_usable_follow_up_strips_and_rejects_repeats():
    assert usable_follow_up(f"  {FOLLOW_UP} ", []) == FOLLOW_UP
    assert usable_follow_up(FOLLOW_UP, [FOLLOW_UP.lower()]) == ""


# --- difficulty reaches the question prompt -----------------------------------------

def test_each_difficulty_changes_the_prompt():
    prompts = {build_question_system("behavioral", d) for d in (1, 2, 3)}
    assert len(prompts) == 3
    assert "stretch" in build_question_system("behavioral", 3)


def test_invalid_difficulty_is_rejected_without_a_model_call():
    provider = FakeProvider([])
    client = LLMClient(provider, model="fake-1", prices=PriceTable(version="t", models={}))
    with pytest.raises(ValueError):
        generate_question(client, mode="behavioral", focus=choose_focus("behavioral", None, None, []),
                          target_role="Intern", difficulty=4)
    assert provider.calls == []