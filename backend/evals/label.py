"""Score the dataset yourself, blind: you never see the AI's scores or what a case is testing.

    python -m evals.label --rater charan

Each case is saved the moment you finish it, so you can quit (q) and resume later.
Cases come in a shuffled order that is fixed per rater.
"""
import argparse
import json
import random
import re
import textwrap
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.interview.rubrics import RUBRICS, SCALE
from evals.dataset import RATER_PATTERN, Case, load_cases, load_labels, labels_path

Ask = Callable[[str], str]


def _wrap(text: str) -> str:
    return "\n".join(textwrap.fill(p, 88) for p in text.splitlines())


def ask_score(ask: Ask, prompt: str) -> int | str:
    """A score from 1 to 5, or "skip" / "quit"."""
    while True:
        reply = ask(prompt).strip().lower()
        if reply in ("s", "q"):
            return {"s": "skip", "q": "quit"}[reply]
        if re.fullmatch(r"[1-5]", reply):
            return int(reply)
        print("  Type 1 to 5, s to skip this case, or q to quit.")


def label_case(case: Case, ask: Ask, show: Callable[[str], None]) -> dict[str, int] | str:
    show(f"\nMode: {case.mode}\n\nQUESTION\n{_wrap(case.question)}\n\nANSWER\n{_wrap(case.answer)}\n")
    show(f"Scale: {SCALE}\n")
    scores = {}
    for criterion in RUBRICS[case.mode]:
        show(f"  {criterion.name}: {criterion.description}")
        reply = ask_score(ask, f"  {criterion.name} (1-5): ")
        if isinstance(reply, str):
            return reply
        scores[criterion.name] = reply
    return scores


def run(cases: list[Case], rater: str, path: Path, ask: Ask = input,
        show: Callable[[str], None] = print) -> int:
    """Label every case this rater hasn't labeled yet. Returns how many were saved."""
    done = load_labels(path, cases)
    todo = [c for c in cases if c.id not in done]
    random.Random(rater).shuffle(todo)   # same order every time for this rater
    show(f"{len(done)} of {len(cases)} cases already labeled; {len(todo)} to go.")

    path.parent.mkdir(parents=True, exist_ok=True)
    saved = 0
    for number, case in enumerate(todo, start=1):
        show(f"\n{'=' * 88}\nCase {number} of {len(todo)}")
        result = label_case(case, ask, show)
        if result == "quit":
            break
        if result == "skip":
            continue
        line = {"case_id": case.id, "rater": rater, "scores": result,
                "labeled_at": datetime.now(UTC).isoformat()}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        saved += 1
    show(f"\nSaved {saved} label(s) to {path}")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rater", required=True, help="your name, lowercase, e.g. charan")
    args = parser.parse_args()
    if not re.fullmatch(RATER_PATTERN, args.rater):
        parser.error("rater: lowercase letters, digits, - and _ only")
    run(load_cases(), args.rater, labels_path(args.rater))


if __name__ == "__main__":
    main()
