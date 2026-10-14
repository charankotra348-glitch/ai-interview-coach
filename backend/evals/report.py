"""Turn saved gradings into numbers, a pass/fail gate, and a Markdown report. No model calls."""
from collections import defaultdict
from decimal import Decimal
from statistics import fmean as mean, median_low

from app.interview.rubrics import overall_score
from evals import metrics
from evals.dataset import Case, Label, criteria


def agreement(ai: list[int], human: list[int]) -> dict:
    return {
        "n": len(ai),
        "mae": metrics.mean_absolute_error(ai, human),
        "exact": metrics.exact_agreement(ai, human),
        "within_one": metrics.within_one(ai, human),
        "bias": metrics.bias(ai, human),
        "qwk": metrics.quadratic_weighted_kappa(ai, human),
        "spearman": metrics.spearman(ai, human),
    }


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]


def summarize(cases: list[Case], grades: list[dict], labels: dict[str, Label]) -> dict:
    ok = [g for g in grades if g["ok"]]
    by_case: dict[str, list[dict]] = defaultdict(list)
    for g in ok:
        by_case[g["case_id"]].append(g)

    # Agreement with the human: the AI's median score over its repeats, per criterion.
    ai, human = [], []
    per_criterion: dict[str, tuple[list[int], list[int]]] = defaultdict(lambda: ([], []))
    ai_overall, human_overall = [], []
    for case in cases:
        label, runs = labels.get(case.id), by_case.get(case.id)
        if not label or not runs:
            continue
        for name in criteria(case.mode):
            a = median_low(r["scores"][name] for r in runs)
            h = label.scores[name]
            ai.append(a)
            human.append(h)
            per_criterion[f"{case.mode}: {name}"][0].append(a)
            per_criterion[f"{case.mode}: {name}"][1].append(h)
        ai_overall.append(median_low(r["overall"] for r in runs))
        human_overall.append(overall_score([label.scores[n] for n in criteria(case.mode)]))

    # Consistency: does the same answer get the same score every time?
    same, spreads = [], []
    for case in cases:
        runs = by_case.get(case.id, [])
        if len(runs) < 2:
            continue
        for name in criteria(case.mode):
            same.append(len({r["scores"][name] for r in runs}) == 1)
        overalls = [r["overall"] for r in runs]
        spreads.append(max(overalls) - min(overalls))

    # Expectations: hard limits that must hold on every single run.
    expect_failures, checked = [], 0
    by_id = {c.id: c for c in cases}
    for g in ok:
        case = by_id[g["case_id"]]
        if case.expect:
            checked += 1
            problems = case.expect.failures(g["overall"], g["scores"])
            if problems:
                expect_failures.append({"case_id": case.id, "repeat": g["repeat"],
                                        "problems": problems})

    priced = [Decimal(g["cost_usd"]) for g in grades if g.get("cost_usd") is not None]
    latencies = [g["latency_ms"] for g in ok]
    return {
        "cases": len(cases),
        "gradings": len(grades),
        "failed": len(grades) - len(ok),
        "failure_rate": (len(grades) - len(ok)) / len(grades) if grades else 0.0,
        "labeled_cases": len(ai_overall),
        "agreement": agreement(ai, human) if ai else None,
        "by_criterion": {k: agreement(*v) for k, v in sorted(per_criterion.items())},
        "overall_spearman": metrics.spearman(ai_overall, human_overall) if ai_overall else None,
        "consistency": {
            "pairs": len(same),
            "identical_rate": mean(same) if same else None,
            "mean_overall_spread": mean(spreads) if spreads else None,
        },
        "expectations": {"checked": checked, "failures": expect_failures},
        "ungrounded_per_grading": mean(g["ungrounded_evidence"] for g in ok) if ok else None,
        "latency_ms": {"p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
        "cost_usd": str(sum(priced, Decimal(0))),
        "unpriced_gradings": len(grades) - len(priced),
    }


def check_gate(report: dict, thresholds: dict, baseline: dict | None = None) -> list[dict]:
    """Every check, passed or not. The gate passes only if all of them pass."""
    checks = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    agree = report["agreement"]
    if agree is None:
        if thresholds["require_human_labels"]:
            check("human agreement", False, "no human labels: run python -m evals.label first")
    else:
        check("QWK", agree["qwk"] >= thresholds["min_qwk"],
              f"{agree['qwk']:.3f} (min {thresholds['min_qwk']})")
        check("MAE", agree["mae"] <= thresholds["max_mae"],
              f"{agree['mae']:.3f} (max {thresholds['max_mae']})")
        check("bias", abs(agree["bias"]) <= thresholds["max_abs_bias"],
              f"{agree['bias']:+.3f} (max ±{thresholds['max_abs_bias']})")
        check("within one", agree["within_one"] >= thresholds["min_within_one"],
              f"{agree['within_one']:.3f} (min {thresholds['min_within_one']})")

    identical = report["consistency"]["identical_rate"]
    if identical is None:
        check("consistency", False, "needs --repeats 2 or more")
    else:
        check("consistency", identical >= thresholds["min_identical_rate"],
              f"{identical:.3f} identical across repeats (min {thresholds['min_identical_rate']})")

    failures = report["expectations"]["failures"]
    check("expectations", not failures, f"{len(failures)} failed of "
          f"{report['expectations']['checked']} checked")
    check("failures", report["failure_rate"] <= thresholds["max_failure_rate"],
          f"{report['failed']} of {report['gradings']} gradings failed")

    # Regression: no worse than the stored baseline, beyond a small margin.
    base = (baseline or {}).get("agreement")
    if base and agree:
        margin = thresholds["regression"]
        check("QWK vs baseline", agree["qwk"] >= base["qwk"] - margin["qwk"],
              f"{agree['qwk']:.3f} vs {base['qwk']:.3f} (margin {margin['qwk']})")
        check("MAE vs baseline", agree["mae"] <= base["mae"] + margin["mae"],
              f"{agree['mae']:.3f} vs {base['mae']:.3f} (margin {margin['mae']})")
    return checks


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(meta: dict, report: dict, checks: list[dict], status: str) -> str:
    gate = "PASS" if all(c["passed"] for c in checks) else "FAIL"
    priced = report["unpriced_gradings"] < report["gradings"]
    cost = f"${report['cost_usd']}" if priced else "not priced"
    lines = [
        f"# Grading evaluation: {meta['provider']} {meta['model']}",
        "",
        f"- Run: `{meta['run_id']}`, commit `{meta['git_commit']}`, {meta['started_at']}",
        f"- {report['cases']} cases x {meta['repeats']} repeats = {report['gradings']} gradings, "
        f"{report['failed']} failed",
        f"- Human labels: {meta['rater'] or 'none'} ({report['labeled_cases']} cases)",
        f"- Cost: {cost} ({report['unpriced_gradings']} without a price), "
        f"latency p50 {_fmt(report['latency_ms']['p50'], 0)} ms, "
        f"p95 {_fmt(report['latency_ms']['p95'], 0)} ms",
        "- Prompt hashes: " + ", ".join(f"{m} `{h}`" for m, h in meta["prompt_hashes"].items()),
        "",
        f"## Gate: {gate} (thresholds are a {status})",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
        *[f"| {c['name']} | {'pass' if c['passed'] else 'FAIL'} | {c['detail']} |" for c in checks],
    ]
    agree = report["agreement"]
    if agree:
        lines += [
            "", "## Agreement with the human, per criterion score", "",
            "| n | MAE | exact | within one | bias (AI - human) | QWK | Spearman |",
            "|---|---|---|---|---|---|---|",
            f"| {agree['n']} | {_fmt(agree['mae'])} | {_fmt(agree['exact'])} | "
            f"{_fmt(agree['within_one'])} | {agree['bias']:+.3f} | {_fmt(agree['qwk'])} | "
            f"{_fmt(agree['spearman'])} |",
            "",
            f"Ranking whole answers (Spearman on overall): {_fmt(report['overall_spearman'])}"
            + (" (needs answers of different quality)" if report["overall_spearman"] is None else ""),
            "", "| Criterion | n | MAE | bias | exact |", "|---|---|---|---|---|",
            *[f"| {name} | {a['n']} | {_fmt(a['mae'])} | {a['bias']:+.2f} | {_fmt(a['exact'])} |"
              for name, a in report["by_criterion"].items()],
        ]
    else:
        lines += ["", "## Agreement with a human", "",
                  "Not measured: no human labels were given for this run."]    
    consistency = report["consistency"]
    lines += [
        "", "## Consistency", "",
        f"- Same score on every repeat: {_fmt(consistency['identical_rate'])} "
        f"of {consistency['pairs']} criterion scores",
        f"- Mean spread of the overall score across repeats: "
        f"{_fmt(consistency['mean_overall_spread'], 2)}",
        f"- Evidence quotes not found in the answer, per grading: "
        f"{_fmt(report['ungrounded_per_grading'], 2)}",
        "", "## Expectations", "",
    ]
    failures = report["expectations"]["failures"]
    lines += [f"- {f['case_id']} (repeat {f['repeat']}): {'; '.join(f['problems'])}"
              for f in failures] or ["- All passed."]
    return "\n".join(lines) + "\n"
