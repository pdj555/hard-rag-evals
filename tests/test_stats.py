"""Intervals and paired tests, checked against known values and their definitions."""
import pytest

from hard_rag_evals import run_suite
from hard_rag_evals.gamers import GAMERS, AlwaysAbstain
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import render_markdown
from hard_rag_evals.stats import (
    _binom_cdf,
    clopper_pearson,
    compare,
    compare_many,
    holm,
    mcnemar_exact,
    paired_difference_ci,
    pass_rate,
    render_comparison_markdown,
)


def test_clopper_pearson_closed_forms():
    # 0 of n: upper bound is 1 - (alpha/2)^(1/n). n of n mirrors it.
    lo, hi = clopper_pearson(0, 5)
    assert lo == 0.0
    assert hi == pytest.approx(1 - 0.025 ** (1 / 5), abs=1e-9)
    lo, hi = clopper_pearson(42, 42)
    assert hi == 1.0
    assert lo == pytest.approx(0.025 ** (1 / 42), abs=1e-9)


@pytest.mark.parametrize("k,n", [(9, 42), (6, 12), (1, 13), (3, 39), (30, 42)])
def test_clopper_pearson_bounds_satisfy_their_definition(k, n):
    lo, hi = clopper_pearson(k, n)
    assert lo < k / n < hi
    # at the lower bound, k or more passes has probability 0.025
    assert 1 - _binom_cdf(k - 1, n, lo) == pytest.approx(0.025, abs=1e-9)
    # at the upper bound, k or fewer passes has probability 0.025
    assert _binom_cdf(k, n, hi) == pytest.approx(0.025, abs=1e-9)


def test_clopper_pearson_known_values():
    # cross-checked once against scipy.stats.binomtest(...).proportion_ci("exact")
    assert clopper_pearson(9, 42) == pytest.approx((0.10296, 0.368116), abs=1e-6)
    assert clopper_pearson(6, 12) == pytest.approx((0.210945, 0.789055), abs=1e-6)


def test_clopper_pearson_rejects_impossible_counts():
    for k, n in [(-1, 5), (6, 5), (0, 0)]:
        with pytest.raises(ValueError):
            clopper_pearson(k, n)


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 1) == 1.0
    assert mcnemar_exact(0, 6) == pytest.approx(2 * 0.5**6)
    assert mcnemar_exact(6, 0) == mcnemar_exact(0, 6)
    assert mcnemar_exact(3, 9) == pytest.approx(0.14599609375)


def test_paired_difference_ci_bonett_price():
    # no discordant cases: centred on zero, and not zero width
    lo, hi = paired_difference_ci(0, 0, 42)
    assert lo == pytest.approx(-hi) and hi > 0
    # worked by hand: p12 = 4/44, p21 = 10/44
    lo, hi = paired_difference_ci(3, 9, 42)
    centre = 4 / 44 - 10 / 44
    half = 1.959963984540054 * ((4 / 44 + 10 / 44 - centre**2) / 44) ** 0.5
    assert (lo, hi) == pytest.approx((centre - half, centre + half))
    assert lo < (3 - 9) / 42 < hi
    with pytest.raises(ValueError):
        paired_difference_ci(30, 30, 42)


def test_holm_adjustment():
    assert holm([0.01, 0.04, 0.03, 0.5]) == pytest.approx([0.04, 0.09, 0.09, 0.5])
    assert holm([0.5, 0.5]) == [1.0, 1.0]
    assert holm([]) == []
    # never smaller than the raw p, never above 1
    raw = [0.2, 0.001, 0.9, 0.03]
    assert all(r <= a <= 1 for r, a in zip(raw, holm(raw)))


def test_pass_rate_of_the_reference_agent():
    rate = pass_rate(run_suite(ReferenceAgent()))
    assert (rate["passed"], rate["total"]) == (9, 42)
    assert rate["ci95"] == pytest.approx([0.10296, 0.368116], abs=1e-6)


def test_compare_counts_discordant_cases():
    reference = run_suite(ReferenceAgent())
    c = compare(reference, run_suite(AlwaysAbstain()))
    assert set(c.gained) == {"unanswerable-easy", "unanswerable-medium", "unanswerable-hard"}
    assert len(c.lost) == 9
    assert c.difference == pytest.approx((3 - 9) / 42)
    assert c.p_value == pytest.approx(mcnemar_exact(3, 9))
    same = compare(reference, reference)
    assert same.gained == same.lost == () and same.p_value == 1.0


def test_compare_refuses_runs_over_different_cases():
    reference = run_suite(ReferenceAgent())
    with pytest.raises(ValueError, match="same cases"):
        compare(reference, run_suite(ReferenceAgent(), difficulty="easy"))


def test_no_gamer_differs_from_the_reference_after_correction():
    reference = run_suite(ReferenceAgent())
    table = compare_many(reference, {g.name: run_suite(g()) for g in GAMERS})
    assert len(table) == len(GAMERS)
    for name, c in table.items():
        assert c.p_holm is not None and c.p_holm >= c.p_value, name
        assert c.ci95[0] < 0 < c.ci95[1], name
    assert table["always-abstain"].p_value == pytest.approx(0.14599609375)
    assert table["always-abstain"].p_holm == pytest.approx(min(1.0, len(GAMERS) * 0.14599609375))
    text = render_comparison_markdown("the reference agent", table)
    assert "| always-abstain | 3 | 9 | -0.143 |" in text


def test_the_paired_test_has_little_power_at_this_size():
    # What "no significant difference" can and cannot mean here. Alone, an
    # agent needs 6 discordant cases all in one direction to reach p < 0.05.
    assert mcnemar_exact(5, 0) > 0.05 > mcnemar_exact(6, 0)
    # Across the 8 trick agents, Holm asks the smallest p to beat 0.05 / 8,
    # which takes 9. No trick agent here gains more than 1 case.
    assert mcnemar_exact(8, 0) > 0.05 / len(GAMERS) > mcnemar_exact(9, 0)
    assert len(GAMERS) == 8


def test_report_carries_intervals_per_tier_and_overall():
    report = render_markdown("reference-agent", run_suite(ReferenceAgent()))
    assert "| easy | 6/12 | 0.50 | 0.21 to 0.79 |" in report
    assert "| brutal | 0/5 | 0.00 | 0.00 to 0.52 |" in report
    assert "| all | 9/42 | 0.21 | 0.10 to 0.37 |" in report
