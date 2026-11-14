"""Uncertainty for pass counts, and paired comparisons between two agents.

Every function here is exact or closed form, has no dependencies, and is
deterministic. The suite is small, 42 cases and as few as 5 in a tier, so the
intervals are wide; that is the point of printing them.

What the intervals do and do not mean: they treat the cases as a sample from
the kind of case this suite could hold. They say nothing about questions
unlike these, and the cases were written by hand, not drawn at random.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb, sqrt
from statistics import NormalDist

from .types import EvalResult


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _solve(f, target: float) -> float:
    """The p in [0, 1] where the decreasing function f crosses target."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact two-sided interval for a binomial proportion, k passes of n.

    The lower bound is the rate at which seeing k or more passes has
    probability alpha/2; the upper bound is the rate at which seeing k or
    fewer does. Coverage is at least the stated confidence for every true
    rate, which makes the interval conservative, wider than it needs to be.
    """
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n and n > 0, got k={k}, n={n}")
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be between 0 and 1, got {confidence}")
    alpha = 1 - confidence
    # Both binomial tails below fall as p rises, which is what _solve wants.
    lower = 0.0 if k == 0 else _solve(lambda p: _binom_cdf(k - 1, n, p), 1 - alpha / 2)
    upper = 1.0 if k == n else _solve(lambda p: _binom_cdf(k, n, p), alpha / 2)
    return lower, upper


def mcnemar_exact(gained: int, lost: int) -> float:
    """Exact two-sided McNemar p-value for two agents on the same cases.

    Only discordant cases carry information: gained counts cases the second
    agent passes and the first fails, lost the reverse. Under no difference
    each discordant case is a fair coin, so the p-value is a two-sided
    binomial test on gained of gained + lost. With no discordant cases it is 1.
    """
    if gained < 0 or lost < 0:
        raise ValueError("discordant counts cannot be negative")
    n = gained + lost
    if n == 0:
        return 1.0
    return min(1.0, 2 * _binom_cdf(min(gained, lost), n, 0.5))


def paired_difference_ci(
    gained: int, lost: int, n: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Interval for the difference in pass rate between two agents graded on
    the same n cases, (gained - lost) / n.

    Bonett and Price (2012) adjusted Wald interval for paired proportions: add
    one to each discordant count and two to n, then use the Wald formula. It
    is closed form and keeps close to nominal coverage at small n, where the
    plain Wald interval collapses to zero width when there are no discordant
    cases. It is approximate, not exact.
    """
    if n <= 0 or gained < 0 or lost < 0 or gained + lost > n:
        raise ValueError(f"need gained + lost <= n and n > 0, got {gained}, {lost}, {n}")
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p12 = (gained + 1) / (n + 2)
    p21 = (lost + 1) / (n + 2)
    centre = p12 - p21
    half = z * sqrt((p12 + p21 - centre**2) / (n + 2))
    return max(-1.0, centre - half), min(1.0, centre + half)


def holm(p_values: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the order given.

    Controls the chance of any false positive across the family of
    comparisons without assuming they are independent. The smallest p is
    multiplied by m, the next by m - 1, and so on, kept monotone and capped
    at 1.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def pass_rate(results: list[EvalResult], confidence: float = 0.95) -> dict:
    """passed, total, rate, and the exact interval, for any set of results."""
    passed = sum(r.passed for r in results)
    total = len(results)
    lower, upper = clopper_pearson(passed, total, confidence)
    return {"passed": passed, "total": total, "rate": passed / total, "ci95": [lower, upper]}


@dataclass(frozen=True)
class PairedComparison:
    """One agent against a baseline on the same cases."""

    n: int
    gained: tuple[str, ...]  # cases the agent passes and the baseline fails
    lost: tuple[str, ...]  # cases the baseline passes and the agent fails
    difference: float  # agent pass rate minus baseline pass rate
    ci95: tuple[float, float]
    p_value: float  # exact McNemar, unadjusted
    p_holm: float | None = None  # set when this is one of several comparisons


def compare(baseline: list[EvalResult], agent: list[EvalResult]) -> PairedComparison:
    """Paired comparison of two runs. The runs must cover the same cases:
    comparing pass rates from different case sets is not a paired test, so a
    mismatch raises instead of comparing what overlaps."""
    base = {r.case_id: r.passed for r in baseline}
    other = {r.case_id: r.passed for r in agent}
    if len(base) != len(baseline) or len(other) != len(agent):
        raise ValueError("a run holds the same case more than once")
    if set(base) != set(other):
        diff = sorted(set(base) ^ set(other))
        raise ValueError(f"the two runs do not cover the same cases: {diff}")
    gained = tuple(c for c in base if other[c] and not base[c])
    lost = tuple(c for c in base if base[c] and not other[c])
    n = len(base)
    return PairedComparison(
        n=n,
        gained=gained,
        lost=lost,
        difference=(len(gained) - len(lost)) / n,
        ci95=paired_difference_ci(len(gained), len(lost), n),
        p_value=mcnemar_exact(len(gained), len(lost)),
    )


def compare_many(
    baseline: list[EvalResult], agents: dict[str, list[EvalResult]]
) -> dict[str, PairedComparison]:
    """Each agent against the same baseline, with Holm adjusted p-values
    across the whole family."""
    raw = {name: compare(baseline, results) for name, results in agents.items()}
    adjusted = holm([c.p_value for c in raw.values()])
    return {
        name: PairedComparison(c.n, c.gained, c.lost, c.difference, c.ci95, c.p_value, p)
        for (name, c), p in zip(raw.items(), adjusted)
    }


def _cell(text: object) -> str:
    flat = " ".join(str(text).split())
    return flat.replace("\\", "\\\\").replace("|", "\\|")


def render_comparison_markdown(
    baseline_name: str, comparisons: dict[str, PairedComparison]
) -> str:
    lines = [
        f"Paired against {baseline_name} on the same cases. Difference is the agent's pass "
        "rate minus the baseline's, with a 95% Bonett-Price interval. p is the exact "
        f"McNemar test on discordant cases; Holm p corrects for {len(comparisons)} comparisons.",
        "",
        "| agent | gained | lost | difference | 95% interval | p | Holm p |",
        "| ----- | ------ | ---- | ---------- | ------------ | - | ------ |",
    ]
    for name, c in comparisons.items():
        lo, hi = c.ci95
        holm_p = "" if c.p_holm is None else f"{c.p_holm:.3f}"
        lines.append(
            f"| {_cell(name)} | {len(c.gained)} | {len(c.lost)} | {c.difference:+.3f} "
            f"| {lo:+.3f} to {hi:+.3f} | {c.p_value:.3f} | {holm_p} |"
        )
    return "\n".join(lines) + "\n"
