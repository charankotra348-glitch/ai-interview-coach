"""How much do two people agree? This sets how close the AI can fairly be asked to get.

    python -m evals.agreement charan friend
"""
import argparse

from evals.dataset import criteria, labels_path, load_cases, load_labels
from evals.report import agreement


def compare(cases, first: dict, second: dict) -> dict | None:
    a, b = [], []
    for case in cases:
        if case.id in first and case.id in second:
            for name in criteria(case.mode):
                a.append(first[case.id].scores[name])
                b.append(second[case.id].scores[name])
    return agreement(a, b) if a else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args()
    cases = load_cases()
    first = load_labels(labels_path(args.first), cases)
    second = load_labels(labels_path(args.second), cases)
    result = compare(cases, first, second)
    if result is None:
        parser.error("these two raters have no labeled cases in common")
    shared = len(first.keys() & second.keys())
    print(f"{args.first} vs {args.second}: {shared} shared cases, {result['n']} criterion scores")
    for key in ("mae", "exact", "within_one", "bias", "qwk", "spearman"):
        value = result[key]
        print(f"  {key:<11} {'n/a' if value is None else f'{value:+.3f}' if key == 'bias' else f'{value:.3f}'}")


if __name__ == "__main__":
    main()
