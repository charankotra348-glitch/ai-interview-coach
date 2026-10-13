"""What to ask next. Pure functions: no database, no model calls, fully deterministic."""
from dataclasses import dataclass
from typing import Literal

from app.interview.questions import too_similar

START_DIFFICULTY = 2
MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 3
PROBE_AT_OR_BELOW = 2   # a criterion scored this low earns one follow-up
RAISE_AT = 8            # main answer overall at or above this: next topic is harder
LOWER_AT = 4            # at or below this: next topic is easier

DIFFICULTY_NAMES = {1: "warm-up", 2: "standard", 3: "stretch"}


@dataclass(frozen=True)
class Turn:
    """One asked question, as the policy sees it."""
    is_follow_up: bool
    difficulty: int
    overall: int | None = None              # None until the answer is graded
    weakest: tuple[str, int] | None = None  # the lowest-scoring criterion and its score
    follow_up_question: str = ""            # the grader's suggested follow-up


@dataclass(frozen=True)
class Decision:
    action: Literal["new_topic", "follow_up", "finish"]
    difficulty: int
    rationale: str
    follow_up: str = ""
    target: str = ""                        # the criterion a follow-up is aimed at


def weakest_criterion(rubric: list[dict]) -> tuple[str, int] | None:
    if not rubric:
        return None
    item = min(rubric, key=lambda r: r["score"])  # ties: the first in rubric order
    return item["name"], item["score"]


def next_difficulty(current: int, overall: int) -> int:
    if overall >= RAISE_AT:
        current += 1
    elif overall <= LOWER_AT:
        current -= 1
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, current))


def usable_follow_up(text: str, previous: list[str]) -> str:
    """The grader's follow-up, or "" if it is missing, malformed or a repeat."""
    text = (text or "").strip()
    if not 15 <= len(text) <= 400:
        return ""
    if any(too_similar(text, earlier) for earlier in previous):
        return ""
    return text


def decide(turns: list[Turn], max_questions: int, previous: list[str]) -> Decision:
    if not turns:
        return Decision("new_topic", START_DIFFICULTY, "opening question")

    last = turns[-1]
    if len(turns) >= max_questions:
        return Decision("finish", last.difficulty, "question limit reached")
    if last.overall is None:
        raise ValueError("the last question has not been graded yet")

    # 1. Probe: one follow-up on a main question with a clearly weak criterion.
    if not last.is_follow_up and last.weakest and last.weakest[1] <= PROBE_AT_OR_BELOW:
        follow_up = usable_follow_up(last.follow_up_question, previous)
        if follow_up:
            name, score = last.weakest
            return Decision("follow_up", last.difficulty,
                            f"follow-up: {name} scored {score}/5", follow_up, target=name)

    # 2. Move on. Difficulty follows the main answer, never the follow-up: follow-ups are
    #    short by design and would score low on criteria they were never meant to cover.
    main = next(t for t in reversed(turns) if not t.is_follow_up)
    difficulty = next_difficulty(main.difficulty, main.overall)
    if difficulty > main.difficulty:
        why = f"harder after a strong answer ({main.overall}/10)"
    elif difficulty < main.difficulty:
        why = f"easier after a weak answer ({main.overall}/10)"
    else:
        why = f"same level ({main.overall}/10)"
    return Decision("new_topic", difficulty, f"new topic, {DIFFICULTY_NAMES[difficulty]}: {why}")