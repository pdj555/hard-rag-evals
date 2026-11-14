"""Pin down which checks the gaming agents beat and which hold.

If a check is hardened, the matching test here should fail: update it and
docs/research.md together.
"""

from hard_rag_evals import run_suite
from hard_rag_evals import metrics as M
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import (
    AlwaysAbstain,
    CiteEverything,
    Hedger,
    NumberSpray,
    QueryEcho,
    TotalGuess,
)
from hard_rag_evals.reference_agent import ReferenceAgent


def _gained(agent):
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    return {r.case_id for r in run_suite(agent) if r.passed and not honest[r.case_id]}


def test_hedger_no_longer_games_the_contradiction_check():
    # Before the check required both claims in one sentence, the hedge sentence
    # turned contradiction-medium and contradiction-hard into passes.
    assert _gained(Hedger()) == set()


def test_query_echo_no_longer_games_the_order_check():
    # Before the check required each event in one sentence, restating the
    # question turned temporal-easy and temporal-hard into passes.
    assert _gained(QueryEcho()) == set()


def test_number_spray_no_longer_games_the_numeric_check():
    # Before the check asked the answer to commit to one figure, the spray
    # turned numeric-easy into a pass.
    assert _gained(NumberSpray()) == set()


def test_spray_contains_the_expected_number_and_still_fails_the_gate():
    # numeric-hard: 10,000,000 is in the spray, next to six rival figures.
    case = next(c for c in ALL_CASES if c.id == "numeric-hard")
    text = NumberSpray().answer(case.query, case.corpus, case.budget).text
    assert any(
        abs(n - case.numeric_expected) <= case.numeric_tolerance for n in M.extract_numbers(text)
    )
    result = {r.case_id: r for r in run_suite(NumberSpray())}["numeric-hard"]
    assert any("did not commit to the expected number" in n for n in result.notes)


def test_one_guessed_total_gains_nothing():
    assert _gained(TotalGuess()) == set()


def test_gamer_scores():
    scores = {
        cls.name: sum(r.passed for r in run_suite(cls()))
        for cls in (Hedger, CiteEverything, AlwaysAbstain, NumberSpray, TotalGuess, QueryEcho)
    }
    assert scores == {
        "hedger": 8,
        "cite-everything": 8,
        "always-abstain": 3,
        "number-spray": 9,
        "total-guess": 9,
        "query-echo": 9,
    }


def test_citing_everything_gains_nothing():
    assert _gained(CiteEverything()) == set()


def test_abstaining_everywhere_loses():
    results = run_suite(AlwaysAbstain())
    passed = {r.case_id for r in results if r.passed}
    assert passed == {"unanswerable-easy", "unanswerable-medium", "unanswerable-hard"}
