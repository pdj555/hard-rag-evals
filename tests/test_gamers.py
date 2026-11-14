"""Pin down which checks the gaming agents beat and which hold.

If a check is hardened, the matching test here should fail: update it and
docs/research.md together.
"""

from hard_rag_evals import run_suite
from hard_rag_evals.gamers import (
    GAMERS,
    AlwaysAbstain,
    CiteEverything,
    Hedger,
    MeanGuess,
    NumberSpray,
    QueryEcho,
    SumMinusLargest,
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


def test_number_spray_still_wins_numeric_easy_and_nothing_else():
    # numeric-easy has two inputs, so the spray is the inputs and their sum:
    # the same text as a correct answer that shows its working. See
    # tests/test_numeric_rule.py for where the rule does stop the spray.
    assert _gained(NumberSpray()) == {"numeric-easy"}


def test_one_guessed_figure_can_win_a_numeric_case():
    # Each of these appends a single figure. Where the question happens to ask
    # for that operation the guess is right, and one committed figure passes.
    assert _gained(TotalGuess()) == {"numeric-easy"}
    assert _gained(MeanGuess()) == {"numeric-medium"}
    assert _gained(SumMinusLargest()) == set()


def test_gamer_scores():
    scores = {cls.name: sum(r.passed for r in run_suite(cls())) for cls in GAMERS}
    assert scores == {
        "hedger": 8,
        "cite-everything": 8,
        "always-abstain": 3,
        "number-spray": 10,
        "total-guess": 10,
        "mean-guess": 10,
        "sum-minus-largest": 9,
        "query-echo": 9,
    }


def test_citing_everything_gains_nothing():
    assert _gained(CiteEverything()) == set()


def test_abstaining_everywhere_loses():
    results = run_suite(AlwaysAbstain())
    passed = {r.case_id for r in results if r.passed}
    assert passed == {"unanswerable-easy", "unanswerable-medium", "unanswerable-hard"}
