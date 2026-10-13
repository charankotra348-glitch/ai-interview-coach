# 003: Evaluation as a release gate

Status: Proposed (thresholds not yet validated)

## Context
Answer grading is the product's core claim. Changes to prompts, models or
evaluation code can silently make grading worse.

## Decision
Maintain a versioned, human-scored golden dataset and a stored baseline.
Measure score error, agreement, rank correlation and run-to-run
consistency. Fail CI when results regress beyond a margin from baseline.

Thresholds start as hypotheses. They become gates only after we measure
human-to-human disagreement on the same dataset and set tolerances from it.

## Rules
- Paid evaluations run separately from unit tests: on changes to prompts,
  model config or evaluation code, and nightly
- Model ID and sampling settings are pinned for every evaluation run
- Every individual run's output is saved, not just averages
- Three runs per answer is the starting experiment; increase it if
  variance estimates are unstable

## Status changes to Accepted when
Human inter-rater agreement is measured and thresholds are set from it.
