"""The golden dataset (answers to grade) and human labels (scores a person gave them)."""
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.interview.rubrics import RUBRICS

EVALS = Path(__file__).parent
CASES_FILE = EVALS / "data" / "cases.jsonl"
LABELS_DIR = EVALS / "labels"
RATER_PATTERN = r"^[a-z0-9_-]{1,30}$"   # also a file name, so keep it plain


def criteria(mode: str) -> list[str]:
    return [c.name for c in RUBRICS[mode]]


class Expect(BaseModel):
    """Hard limits a case must meet on every run, whatever the human scores say."""
    model_config = ConfigDict(extra="forbid")
    max_overall: int | None = Field(default=None, ge=1, le=10)
    min_overall: int | None = Field(default=None, ge=1, le=10)
    max_score: dict[str, int] = {}   # criterion -> highest acceptable score
    min_score: dict[str, int] = {}   # criterion -> lowest acceptable score

    def failures(self, overall: int, scores: dict[str, int]) -> list[str]:
        out = []
        if self.max_overall is not None and overall > self.max_overall:
            out.append(f"overall {overall} > {self.max_overall}")
        if self.min_overall is not None and overall < self.min_overall:
            out.append(f"overall {overall} < {self.min_overall}")
        for name, limit in self.max_score.items():
            if scores[name] > limit:
                out.append(f"{name} {scores[name]} > {limit}")
        for name, limit in self.min_score.items():
            if scores[name] < limit:
                out.append(f"{name} {scores[name]} < {limit}")
        return out


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9-]{3,60}$")
    mode: Literal["behavioral", "project", "system_design"]
    question: str = Field(min_length=10)
    answer: str = Field(min_length=1)
    note: str = ""                  # what the case tests; never shown while labeling
    expect: Expect | None = None

    @model_validator(mode="after")
    def _known_criteria(self):
        if self.expect:
            names = set(criteria(self.mode))
            for name in [*self.expect.max_score, *self.expect.min_score]:
                if name not in names:
                    raise ValueError(f"{self.id}: unknown criterion {name!r} for {self.mode}")
        return self


class Label(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    rater: str = Field(pattern=RATER_PATTERN)
    scores: dict[str, int]
    labeled_at: datetime

    @model_validator(mode="after")
    def _scores_in_range(self):
        for name, score in self.scores.items():
            if not 1 <= score <= 5:
                raise ValueError(f"{self.case_id}: {name} must be 1 to 5, got {score}")
        return self


def _lines(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            yield number, line


def load_cases(path: Path = CASES_FILE) -> list[Case]:
    cases, seen = [], set()
    for number, line in _lines(path):
        try:
            case = Case.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"{path.name} line {number}: {exc}") from exc
        if case.id in seen:
            raise ValueError(f"{path.name} line {number}: duplicate id {case.id}")
        seen.add(case.id)
        cases.append(case)
    return cases


def labels_path(rater: str) -> Path:
    return LABELS_DIR / f"{rater}.jsonl"


def load_labels(path: Path, cases: list[Case]) -> dict[str, Label]:
    """One label per case. If a case was labeled twice, the later label wins."""
    if not path.exists():
        return {}
    by_id = {c.id: c for c in cases}
    labels = {}
    for number, line in _lines(path):
        label = Label.model_validate_json(line)
        case = by_id.get(label.case_id)
        if case is None:
            continue                     # the case was removed from the dataset
        if set(label.scores) != set(criteria(case.mode)):
            raise ValueError(f"{path.name} line {number}: scores must cover exactly "
                             f"{criteria(case.mode)}")
        labels[label.case_id] = label
    return labels
