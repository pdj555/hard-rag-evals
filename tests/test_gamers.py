"""Pin down which checks the gaming agents beat and which hold.

If a check is hardened, the matching test here should fail: update it and
docs/research.md together.
"""

from hard_rag_evals import run_suite
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import (
    GAMERS,
    SURFACE,
    AlwaysAbstain,
    CiteEverything,
    Fabricator,
    Hedger,
    MeanGuess,
    NumberSpray,
    QueryEcho,
    SumMinusLargest,
    TotalGuess,
    single_document_passes,
)
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import order_spread


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


def test_number_spray_games_the_numeric_check():
    assert _gained(NumberSpray()) == {"numeric-easy"}


def test_spray_also_hits_numeric_hard_and_is_stopped_by_another_gate():
    result = {r.case_id: r for r in run_suite(NumberSpray())}["numeric-hard"]
    assert result.gates["numeric"] is True
    assert result.failed_gates == ["forbidden_citation"]


def test_one_guessed_figure_can_win_a_numeric_case():
    # Each of these appends a single figure. Where the question happens to ask
    # for that operation the guess is right.
    assert _gained(TotalGuess()) == {"numeric-easy"}
    assert _gained(MeanGuess()) == {"numeric-medium"}
    assert _gained(SumMinusLargest()) == set()


SCORES = {
    "hedger": 8,
    "cite-everything": 8,
    "always-abstain": 3,
    "number-spray": 10,
    "total-guess": 10,
    "mean-guess": 10,
    "sum-minus-largest": 9,
    "query-echo": 9,
}


def test_gamer_scores_under_the_default_shuffle():
    scores = {cls.name: sum(r.passed for r in run_suite(cls())) for cls in GAMERS}
    assert scores == {
        **SCORES,
        "first-document": 9,
        "overlap-document": 14,
        "greatest-id-document": 13,
        "newest-document": 11,
        "shortest-document": 10,
    }


def test_gamer_scores_in_fixture_order():
    scores = {
        cls.name: sum(r.passed for r in run_suite(cls(), shuffle_seed=None)) for cls in GAMERS
    }
    assert scores == {
        **SCORES,
        "first-document": 19,
        "overlap-document": 17,
        "greatest-id-document": 13,
        "newest-document": 21,
        "shortest-document": 10,
    }


def test_surface_heuristics_read_nothing_and_beat_the_reference():
    # Each copies one document picked by a surface feature. At the default
    # seed four of the five score above the reference agent's 9.
    reference = sum(r.passed for r in run_suite(ReferenceAgent()))
    assert reference == 9
    for cls in SURFACE:
        for case in ALL_CASES[:5]:
            ans = cls().answer(case.query, case.corpus, case.budget)
            assert len(ans.citations) == 1
            assert ans.text == case.corpus.by_id(ans.citations[0]).text
    best = max(sum(r.passed for r in run_suite(cls())) for cls in SURFACE)
    assert best - reference == 5
    assert len(SURFACE) == 5


def test_surface_heuristics_over_twenty_seeds():
    spreads = {cls.name: order_spread(cls()) for cls in SURFACE}
    summary = {n: (round(s["mean"], 2), s["min"], s["max"]) for n, s in spreads.items()}
    assert summary == {
        "first-document": (7.0, 4, 12),
        "overlap-document": (13.85, 12, 16),
        "greatest-id-document": (13.0, 13, 13),
        "newest-document": (9.55, 6, 13),
        "shortest-document": (10.0, 10, 10),
    }


def test_more_than_half_the_cases_pass_by_copying_one_document():
    passing = [c.id for c in ALL_CASES if single_document_passes(c)]
    assert len(passing) == 23
    # none of them can be a case that needs two citations or a refusal
    assert not any(c.should_abstain or len(c.must_cite) > 1 for c in ALL_CASES if c.id in passing)


def test_cases_some_cheap_agent_turns_into_a_pass_at_the_default_seed():
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    gained = set()
    for cls in GAMERS:
        gained |= {r.case_id for r in run_suite(cls()) if r.passed and not honest[r.case_id]}
    assert len(gained) == 21
    assert sum(not ok for ok in honest.values()) == 33


def test_fabricator_scores_zero():
    assert sum(r.passed for r in run_suite(Fabricator())) == 0


def test_citing_everything_gains_nothing():
    assert _gained(CiteEverything()) == set()


def test_abstaining_everywhere_loses():
    results = run_suite(AlwaysAbstain())
    passed = {r.case_id for r in results if r.passed}
    assert passed == {"unanswerable-easy", "unanswerable-medium", "unanswerable-hard"}


def test_hero_figure_matches_the_gamer_table_at_the_default_seed():
    import re
    from pathlib import Path

    from hard_rag_evals.runner import DIFFICULTY_ORDER

    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    gained = set()
    for cls in GAMERS:
        gained |= {r.case_id for r in run_suite(cls()) if r.passed and not honest[r.case_id]}
    expected = []
    for tier in DIFFICULTY_ORDER:
        for case in ALL_CASES:
            if case.difficulty == tier:
                expected.append("pass" if honest[case.id] else "trick" if case.id in gained else "fail")
    assets = Path(__file__).parent.parent / "docs" / "assets"
    for name in ("hero-light.svg", "hero-dark.svg"):
        svg = (assets / name).read_text()
        legend = dict(
            (label, colour)
            for colour, label in re.findall(r'<circle [^>]*fill="(#\w+)"/><text [^>]*>([^<]+)</text>', svg)
        )
        colour_of = {
            "pass": legend["passed"],
            "trick": legend["passed by a cheap trick"],
            "fail": legend["failed"],
        }
        cells = re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="44" height="44" rx="7" fill="(#\w+)"/>', svg)
        assert cells == [colour_of[s] for s in expected], name
        assert "21 of the 33 failed cases are passed by at least one" in svg
    readme = (assets.parent.parent / "README.md").read_text()
    assert "21 of the 33 cases the reference agent fails" in readme
