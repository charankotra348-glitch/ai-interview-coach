"""Grade every case with the real model several times, save every run, report, and gate.

    python -m evals.run --rater charan --repeats 3
    python -m evals.run --provider ollama --model llama3.2 --limit 5
    python -m evals.run --rater charan --gate --baseline evals/reports/<earlier run>.json

Exit code 1 when --gate is set and any check fails.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.interview.evaluation import build_eval_system, evaluate_answer
from app.interview.rubrics import MODES
from app.llm.client import LLMClient
from app.llm.errors import LLMCallFailed, ProviderAuthError
from app.llm.structured import StructuredOutputError
from evals.dataset import CASES_FILE, EVALS, Case, labels_path, load_cases, load_labels
from evals.report import check_gate, render_markdown, summarize

RUNS_DIR = EVALS / "runs"
REPORTS_DIR = EVALS / "reports"
THRESHOLDS_FILE = EVALS / "thresholds.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        commit = out.stdout.strip() or "unknown"
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def grade_once(client: LLMClient, case: Case, repeat: int) -> dict:
    record = {"type": "grade", "case_id": case.id, "repeat": repeat}
    started = time.perf_counter()
    try:
        result = evaluate_answer(client, mode=case.mode, question=case.question,
                                 answer=case.answer)
    except (StructuredOutputError, LLMCallFailed) as exc:
        if getattr(exc, "error_type", "") == ProviderAuthError.error_type:
            raise                   # a bad API key would fail every case: stop now
        return record | {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                         "latency_ms": round((time.perf_counter() - started) * 1000)}
    value = result.value
    costs = [c.cost.usd for c in result.calls]
    return record | {
        "ok": True,
        "scores": {item.name: item.score for item in value.rubric},
        "overall": value.overall,
        "ungrounded_evidence": value.ungrounded_evidence,
        "attempts": result.attempts,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "cost_usd": None if None in costs else str(sum(costs, Decimal(0))),
        "error": None,
    }


def grade_all(client: LLMClient, cases: list[Case], repeats: int, out: Path, meta: dict,
              pause_s: float = 0.0, show: Callable[[str], None] = print) -> list[dict]:
    """Grade case by case, appending each result to `out` as soon as it exists."""
    out.parent.mkdir(parents=True, exist_ok=True)
    grades = []
    with out.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "meta", **meta}) + "\n")
        for i, case in enumerate(cases, start=1):
            for repeat in range(1, repeats + 1):
                grade = grade_once(client, case, repeat)
                f.write(json.dumps(grade) + "\n")
                f.flush()
                grades.append(grade)
                result = f"overall {grade['overall']}" if grade["ok"] else grade["error"]
                show(f"[{i}/{len(cases)}] {case.id} #{repeat}: {result}")
                if pause_s:
                    time.sleep(pause_s)
    return grades


def build_meta(client: LLMClient, *, rater: str | None, repeats: int,
               cases_file: Path) -> dict:
    started = datetime.now(UTC)
    model_slug = "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in client.model)
    return {
        "run_id": f"{started:%Y%m%d-%H%M%S}_{model_slug}",
        "started_at": started.isoformat(timespec="seconds"),
        "provider": client.provider.name,
        "model": client.model,
        "temperature": 0.0,                 # fixed in complete_json
        "repeats": repeats,
        "rater": rater,
        "git_commit": _git_commit(),
        "cases_sha": _sha(cases_file.read_text(encoding="utf-8")),
        "prompt_hashes": {mode: _sha(build_eval_system(mode)) for mode in MODES},
        "price_table": client.prices.version,
    }


def main(argv: list[str] | None = None, client: LLMClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rater", help="compare with this person's labels")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, help="only the first N cases (a quick check)")
    parser.add_argument("--provider", choices=["gemini", "ollama"])
    parser.add_argument("--model", help="override the model from .env")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between calls")
    parser.add_argument("--gate", action="store_true", help="exit 1 if any check fails")
    parser.add_argument("--baseline", type=Path, help="an earlier report .json to compare")
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    cases = load_cases(args.cases)[: args.limit]
    labels = load_labels(labels_path(args.rater), cases) if args.rater else {}
    if args.rater and not labels:
        parser.error(f"no labels found for {args.rater}: run python -m evals.label first")
    thresholds = json.loads(THRESHOLDS_FILE.read_text())
    baseline = json.loads(args.baseline.read_text())["report"] if args.baseline else None

    if client is None:
        from app.llm.factory import build_llm_client
        client = build_llm_client(provider=args.provider, model=args.model, record=False)
    meta = build_meta(client, rater=args.rater, repeats=args.repeats, cases_file=args.cases)
    print(f"Grading {len(cases)} cases x {args.repeats} with {meta['provider']} {meta['model']}")

    run_file = RUNS_DIR / f"{meta['run_id']}.jsonl"
    try:
        grades = grade_all(client, cases, args.repeats, run_file, meta, args.pause)
    except LLMCallFailed as exc:
        print(f"Stopped: the provider rejected the API key ({exc}).", file=sys.stderr)
        return 2

    report = summarize(cases, grades, labels)
    checks = check_gate(report, thresholds, baseline)
    markdown = render_markdown(meta, report, checks, thresholds["status"])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{meta['run_id']}.md").write_text(markdown, encoding="utf-8")
    (REPORTS_DIR / f"{meta['run_id']}.json").write_text(
        json.dumps({"meta": meta, "report": report, "checks": checks}, indent=2),
        encoding="utf-8")
    print("\n" + markdown)
    print(f"Saved {run_file} and {REPORTS_DIR / meta['run_id']}.md")
    passed = all(c["passed"] for c in checks)
    return 1 if args.gate and not passed else 0


if __name__ == "__main__":
    sys.exit(main())
