"""Pin down which checks the gaming agents beat and which hold.

If a check is hardened, the matching test here should fail: update it and
docs/research.md together.
"""

from hard_rag_evals import run_suite
from hard_rag_evals.gamers import AlwaysAbstain, CiteEverything, Hedger, NumberSpray
from hard_rag_evals.reference_agent import ReferenceAgent


def _gained(agent):
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    return {r.case_id for r in run_suite(agent) if r.passed and not honest[r.case_id]}


def test_hedger_games_the_contradiction_check():
    assert _gained(Hedger()) == {"contradiction-medium", "contradiction-hard"}


def test_number_spray_games_the_numeric_check():
    assert _gained(NumberSpray()) == {"numeric-easy"}


def test_citing_everything_gains_nothing():
    assert _gained(CiteEverything()) == set()


def test_abstaining_everywhere_loses():
    results = run_suite(AlwaysAbstain())
    passed = {r.case_id for r in results if r.passed}
    assert passed == {"unanswerable-easy", "unanswerable-medium", "unanswerable-hard"}
