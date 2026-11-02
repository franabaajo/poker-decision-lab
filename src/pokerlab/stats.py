"""Statistics for Monte Carlo estimates.

Each simulated trial scores the hero 1 (win), 0.5 (split pot) or 0 (loss).
Equity is the mean score. Trials are independent and identically distributed, so
by the central limit theorem the sample mean is approximately normal with

    standard error  SE = s / sqrt(n)

where ``s`` is the sample standard deviation of the per-trial scores. A 95%
confidence interval is ``mean ± 1.96 · SE``.

Interpretation: if we repeated the whole simulation many times, about 95% of the
intervals built this way would contain the true equity. The coverage test in
``tests/test_stats.py`` checks exactly that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Z_95 = 1.959963984540054  # 97.5th percentile of the standard normal distribution


@dataclass(frozen=True)
class Estimate:
    mean: float
    std_error: float
    n: int

    @property
    def ci95(self) -> tuple[float, float]:
        half = Z_95 * self.std_error
        return max(0.0, self.mean - half), min(1.0, self.mean + half)


def estimate_from_counts(wins: int, ties: int, losses: int) -> Estimate:
    """Mean and standard error of the per-trial score from outcome counts.

    With scores 1, 0.5, 0: mean = (W + T/2) / n and
    E[X^2] = (W + T/4) / n, so the sample variance is
    n / (n - 1) * (E[X^2] - mean^2).
    """
    n = wins + ties + losses
    if n == 0:
        raise ValueError("No trials.")
    mean = (wins + 0.5 * ties) / n
    if n == 1:
        return Estimate(mean, math.inf, 1)
    second_moment = (wins + 0.25 * ties) / n
    variance = max(0.0, (second_moment - mean * mean) * n / (n - 1))
    return Estimate(mean, math.sqrt(variance / n), n)


def samples_for_margin(margin: float, p: float = 0.5) -> int:
    """Trials needed for a 95% CI half-width of ``margin`` (worst case p = 0.5).

    ``samples_for_margin(0.005)`` ~ 38,415: about 40k trials give ±0.5 points.
    """
    return math.ceil((Z_95 / margin) ** 2 * p * (1 - p))
