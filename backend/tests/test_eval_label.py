from evals.dataset import Case, load_labels
from evals.label import run

CASES = [
    Case(id="b-one", mode="behavioral", question="Tell me about a time.", answer="One.",
         note="SECRET NOTE"),
    Case(id="b-two", mode="behavioral", question="Tell me about another time.", answer="Two."),
]


def scripted(replies):
    replies = iter(replies)
    return lambda prompt: next(replies)


def test_labels_are_saved_one_case_at_a_time_and_resume(tmp_path):
    path = tmp_path / "labels" / "charan.jsonl"
    shown = []
    # First session: one full case (with one invalid reply that is asked again), then quit.
    saved = run(CASES, "charan", path, ask=scripted(["3", "9", "4", "2", "2", "5", "q"]),
                show=shown.append)
    assert saved == 1
    first = load_labels(path, CASES)
    assert len(first) == 1
    assert list(first.values())[0].scores == {"Structure": 3, "Specificity": 4, "Ownership": 2,
                                              "Impact": 2, "Reflection": 5}
    assert not any("SECRET NOTE" in s for s in shown)   # labeling is blind

    # Second session: only the remaining case is asked.
    saved = run(CASES, "charan", path, ask=scripted(["1"] * 5), show=shown.append)
    assert saved == 1
    assert set(load_labels(path, CASES)) == {"b-one", "b-two"}


def test_skip_moves_on_without_saving(tmp_path):
    path = tmp_path / "charan.jsonl"
    assert run(CASES, "charan", path, ask=scripted(["s", "s"]), show=lambda s: None) == 0
    assert load_labels(path, CASES) == {}
