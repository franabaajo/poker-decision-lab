"""M4 tests: standard errors and confidence intervals."""

import math
import random

import pytest

from pokerlab.stats import Z_95, estimate_from_counts, samples_for_margin


def test_mean_counts_ties_as_half():
    est = estimate_from_counts(wins=30, ties=10, losses=60)
    assert est.mean == pytest.approx(0.35)
    assert est.n == 100


def test_std_error_matches_direct_computation():
    scores = [1.0] * 30 + [0.5] * 10 + [0.0] * 60
    n = len(scores)
    mean = sum(scores) / n
    sample_var = sum((x - mean) ** 2 for x in scores) / (n - 1)
    est = estimate_from_counts(30, 10, 60)
    assert est.std_error == pytest.approx(math.sqrt(sample_var / n))


def test_no_uncertainty_when_every_trial_is_identical():
    est = estimate_from_counts(100, 0, 0)
    assert est.mean == 1.0 and est.std_error == 0.0
    assert est.ci95 == (1.0, 1.0)


def test_ci_is_clipped_to_0_1():
    lo, hi = estimate_from_counts(1, 0, 1).ci95
    assert 0.0 <= lo <= hi <= 1.0


def test_no_trials_is_an_error():
    with pytest.raises(ValueError):
        estimate_from_counts(0, 0, 0)


def test_samples_for_margin():
    # Classic result: ~385 samples for ±5 points, ~38,415 for ±0.5 points at p = 0.5.
    assert samples_for_margin(0.05) == 385
    assert samples_for_margin(0.005) == math.ceil((Z_95 / 0.005) ** 2 * 0.25)


def test_ci95_coverage_is_about_95_percent():
    """Simulate trials with a KNOWN equity; ~95% of the CIs must contain it.

    P(win) = 0.4, P(tie) = 0.1 -> true equity 0.45. With 1,000 experiments the
    observed coverage has a standard deviation of ~0.7 points, so [0.93, 0.97]
    is a safe acceptance band.
    """
    gen = random.Random(123)
    true_equity, experiments, n = 0.45, 1_000, 400
    hits = 0
    for _ in range(experiments):
        w = t = losses = 0
        for _ in range(n):
            u = gen.random()
            if u < 0.4:
                w += 1
            elif u < 0.5:
                t += 1
            else:
                losses += 1
        lo, hi = estimate_from_counts(w, t, losses).ci95
        hits += lo <= true_equity <= hi
    assert 0.93 <= hits / experiments <= 0.97
