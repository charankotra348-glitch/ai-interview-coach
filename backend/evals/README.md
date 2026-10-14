# Grading evaluation

Measures how closely the AI grader agrees with a person scoring the same answers
(decision 003). Paid model calls: run it by hand, never inside `pytest`.

1. Label the cases yourself, blind: `python -m evals.label --rater <name>`
2. Grade them with the model: `python -m evals.run --rater <name> --repeats 3`
3. Compare two people: `python -m evals.agreement <name> <other>`

| File | What it holds |
|---|---|
| `data/cases.jsonl` | Answers to grade. `note` says what a case tests; `expect` sets hard limits |
| `labels/<rater>.jsonl` | One person's scores, one line per case |
| `runs/<run>.jsonl` | Every single grading of a run, with model, commit and prompt hashes |
| `reports/<run>.md`, `.json` | The numbers and the gate result |
| `thresholds.json` | Gate limits. Hypotheses until human-to-human agreement is measured |

Metrics: MAE, exact agreement, within one, bias (AI minus human), quadratic weighted
kappa, Spearman; consistency across repeats; expectations that must hold on every run.
