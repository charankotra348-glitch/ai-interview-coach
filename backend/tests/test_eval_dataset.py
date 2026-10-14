import json

import pytest

from evals.dataset import Expect, criteria, load_cases, load_labels

CASE = {"id": "b-one", "mode": "behavioral", "question": "Tell me about a time.",
        "answer": "An answer."}


def write_lines(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def label(case_id, scores, at="2026-10-14T10:00:00+00:00"):
    return {"case_id": case_id, "rater": "charan", "scores": scores, "labeled_at": at}


def test_the_real_dataset_loads_and_covers_every_mode():
    cases = load_cases()
    assert len(cases) >= 15
    assert {c.mode for c in cases} == {"behavioral", "project", "system_design"}
    assert any(c.expect for c in cases)


def test_duplicate_ids_are_rejected(tmp_path):
    path = write_lines(tmp_path / "cases.jsonl", [CASE, CASE])
    with pytest.raises(ValueError, match="duplicate id"):
        load_cases(path)


def test_expectations_must_name_real_criteria(tmp_path):
    bad = CASE | {"expect": {"max_score": {"Charisma": 2}}}
    with pytest.raises(ValueError, match="unknown criterion"):
        load_cases(write_lines(tmp_path / "cases.jsonl", [bad]))


def test_expect_reports_every_broken_limit():
    expect = Expect(max_overall=4, max_score={"Impact": 2})
    scores = {"Structure": 3, "Specificity": 3, "Ownership": 3, "Impact": 4, "Reflection": 3}
    assert expect.failures(6, scores) == ["overall 6 > 4", "Impact 4 > 2"]
    assert expect.failures(4, scores | {"Impact": 2}) == []


def test_labels_later_wins_and_must_cover_every_criterion(tmp_path):
    cases = load_cases(write_lines(tmp_path / "cases.jsonl", [CASE]))
    names = criteria("behavioral")
    first = {n: 2 for n in names}
    second = {n: 4 for n in names}
    path = write_lines(tmp_path / "charan.jsonl", [label("b-one", first), label("b-one", second),
                                                   label("removed-case", first)])
    labels = load_labels(path, cases)
    assert list(labels) == ["b-one"]
    assert labels["b-one"].scores == second

    write_lines(path, [label("b-one", {"Structure": 3})])
    with pytest.raises(ValueError, match="cover exactly"):
        load_labels(path, cases)


def test_label_scores_must_be_1_to_5(tmp_path):
    cases = load_cases(write_lines(tmp_path / "cases.jsonl", [CASE]))
    scores = {n: 3 for n in criteria("behavioral")} | {"Impact": 6}
    with pytest.raises(ValueError):
        load_labels(write_lines(tmp_path / "charan.jsonl", [label("b-one", scores)]), cases)
