"""Agreement between two lists of 1-to-5 rubric scores. Pure functions, no dependencies."""
from statistics import fmean as mean

LOW, HIGH = 1, 5


def _check(a: list[int], b: list[int]) -> None:
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty lists of the same length")


def mean_absolute_error(a: list[int], b: list[int]) -> float:
    _check(a, b)
    return mean(abs(x - y) for x, y in zip(a, b))


def exact_agreement(a: list[int], b: list[int]) -> float:
    _check(a, b)
    return mean(1.0 if x == y else 0.0 for x, y in zip(a, b))


def within_one(a: list[int], b: list[int]) -> float:
    _check(a, b)
    return mean(1.0 if abs(x - y) <= 1 else 0.0 for x, y in zip(a, b))


def bias(ai: list[int], human: list[int]) -> float:
    """Positive: the AI scores higher than the human, on average."""
    _check(ai, human)
    return mean(x - y for x, y in zip(ai, human))


def quadratic_weighted_kappa(a: list[int], b: list[int], low: int = LOW, high: int = HIGH) -> float:
    """Cohen's kappa with quadratic weights: the standard agreement measure for ordinal scores.

    1 means perfect agreement, 0 means no better than chance, below 0 worse than chance.
    Being off by 2 costs four times as much as being off by 1.
    """
    _check(a, b)
    n = high - low + 1
    observed = [[0] * n for _ in range(n)]
    for x, y in zip(a, b):
        if not (low <= x <= high and low <= y <= high):
            raise ValueError(f"scores must be between {low} and {high}")
        observed[x - low][y - low] += 1
    total = len(a)
    row = [sum(observed[i]) for i in range(n)]
    col = [sum(observed[i][j] for i in range(n)) for j in range(n)]

    disagreement = expected = 0.0
    for i in range(n):
        for j in range(n):
            weight = (i - j) ** 2 / (n - 1) ** 2
            disagreement += weight * observed[i][j]
            expected += weight * row[i] * col[j] / total
    if expected == 0:   # both raters used one and the same score throughout
        return 1.0
    return 1 - disagreement / expected


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):   # ties share the average of their ranks
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rank correlation: do both raters put the answers in the same order? None if one never varies."""
    _check(a, b)
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = mean(ra), mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    var_a = sum((x - ma) ** 2 for x in ra)
    var_b = sum((y - mb) ** 2 for y in rb)
    if var_a == 0 or var_b == 0:
        return None
    return cov / (var_a * var_b) ** 0.5
