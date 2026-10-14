import pytest

from evals.metrics import (
    bias,
    exact_agreement,
    mean_absolute_error,
    quadratic_weighted_kappa,
    spearman,
    within_one,
)

# Expected values computed independently with scikit-learn's cohen_kappa_score
# (weights="quadratic", labels=[1..5]) and scipy.stats.spearmanr.
REFERENCE = [
    ([1, 2, 3, 4, 5], [1, 2, 3, 4, 4], 0.941176, 0.974679),
    ([3, 3, 4, 2, 5, 1, 4], [3, 4, 4, 2, 4, 2, 3], 0.745455, 0.769800),
    ([1, 1, 5, 5], [5, 5, 1, 1], -1.0, -1.0),
    ([2, 3, 3, 4, 4, 5], [2, 2, 3, 3, 5, 5], 0.8, 0.861640),
]


@pytest.mark.parametrize("a, b, qwk, rho", REFERENCE)
def test_matches_scikit_learn_and_scipy(a, b, qwk, rho):
    assert quadratic_weighted_kappa(a, b) == pytest.approx(qwk, abs=1e-6)
    assert spearman(a, b) == pytest.approx(rho, abs=1e-5)


def test_simple_measures():
    ai, human = [4, 3, 5, 2], [3, 3, 3, 2]
    assert mean_absolute_error(ai, human) == 0.75     # (1 + 0 + 2 + 0) / 4
    assert exact_agreement(ai, human) == 0.5
    assert within_one(ai, human) == 0.75
    assert bias(ai, human) == 0.75                    # positive: the AI is more generous


def test_perfect_and_constant_agreement():
    assert quadratic_weighted_kappa([2, 4], [2, 4]) == 1.0
    assert quadratic_weighted_kappa([3, 3], [3, 3]) == 1.0   # no chance disagreement possible
    assert spearman([3, 3, 3], [1, 2, 3]) is None             # one rater never varies


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        mean_absolute_error([1, 2], [1])
    with pytest.raises(ValueError):
        exact_agreement([], [])
    with pytest.raises(ValueError):
        quadratic_weighted_kappa([0, 3], [1, 3])
