"""Document order must not decide a score. The grader does not read it, runs
shuffle it by default because fixture order leaks, and the suite reports how
much an agent's score moves when only the order changes."""
import json
from pathlib import Path

import pytest

from hard_rag_evals import Answer
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import GAMERS, SURFACE, FirstDocument
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import (
    DEFAULT_SHUFFLE_SEED,
    first_document_is_required,
    grade,
    order_spread,
    permute_documents,
    run_suite,
)

GOLD = json.loads((Path(__file__).parent / "gold_answers.json").read_text())
GOLD.pop("_canary")
SEEDS = tuple(range(10))


def _ids(case):
    return [d.id for d in case.corpus.documents]


def test_permutation_keeps_the_documents_and_changes_their_order():
    moved = 0
    for case in ALL_CASES:
        for seed in SEEDS:
            shuffled = permute_documents(case, seed)
            assert sorted(_ids(shuffled)) == sorted(_ids(case))
            assert shuffled.corpus.ids == case.corpus.ids
            moved += _ids(shuffled) != _ids(case)
    # 41 cases have more than one document; most seeds must really reorder them
    assert moved > 41 * len(SEEDS) // 2


def test_permutation_is_repeatable_and_depends_on_the_seed():
    case = next(c for c in ALL_CASES if len(c.corpus.documents) >= 20)
    assert _ids(permute_documents(case, 3)) == _ids(permute_documents(case, 3))
    assert _ids(permute_documents(case, 3)) != _ids(permute_documents(case, 4))


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_gold_verdict_is_unchanged_under_permutation(case):
    g = GOLD[case.id]
    answer = Answer(text=g["text"], citations=list(g["citations"]), abstained=g["abstained"])
    base = grade(case, answer)
    assert base.passed
    for seed in SEEDS:
        shuffled = grade(permute_documents(case, seed), answer)
        assert shuffled.gates == base.gates, seed
        assert shuffled.scores == base.scores, seed


class Recorder:
    name = "recorder"

    def __init__(self):
        self.seen = {}

    def answer(self, query, corpus, budget):
        self.seen[query] = [d.id for d in corpus.documents]
        return Answer(text="x")


def _seen(**kw):
    recorder = Recorder()
    results = run_suite(recorder, **kw)
    return recorder.seen, results


def test_run_suite_shuffles_by_default_and_records_the_seed():
    default, results = _seen()
    explicit, _ = _seen(shuffle_seed=DEFAULT_SHUFFLE_SEED)
    fixture, fixture_results = _seen(shuffle_seed=None)
    other, other_results = _seen(shuffle_seed=1)
    assert default == explicit
    assert default != fixture and other != fixture and other != default
    assert {q: sorted(v) for q, v in default.items()} == {q: sorted(v) for q, v in fixture.items()}
    assert {r.shuffle_seed for r in results} == {DEFAULT_SHUFFLE_SEED} == {2026}
    assert {r.shuffle_seed for r in fixture_results} == {None}
    assert {r.shuffle_seed for r in other_results} == {1}
    # what the agent is shown in fixture order is the fixture
    assert fixture == {c.query: [d.id for d in c.corpus.documents] for c in ALL_CASES}


def test_an_answer_graded_directly_records_that_no_order_was_presented():
    assert grade(ALL_CASES[0], Answer(text="x")).shuffle_seed == "n/a"


def test_fixture_order_puts_a_required_document_first():
    # The leak. 33 of the 39 cases that require a citation list a required
    # document first. Shuffled, it is first about half as often.
    assert first_document_is_required(None) == (33, 39)
    assert first_document_is_required(DEFAULT_SHUFFLE_SEED) == (22, 39)
    shuffled = [first_document_is_required(seed)[0] for seed in range(20)]
    assert (min(shuffled), max(shuffled)) == (15, 25)
    assert sum(shuffled) / 20 == pytest.approx(18.85)


def test_first_document_agent_wins_on_fixture_order_and_not_when_shuffled():
    spread = order_spread(FirstDocument())
    assert spread["fixture_order"] == 19
    assert (spread["min"], spread["max"]) == (4, 12)
    assert spread["mean"] == pytest.approx(7.0)
    assert len(spread["flipped"]) >= 10
    assert sum(r.passed for r in run_suite(FirstDocument())) == 9  # the default seed


def test_reference_agent_and_its_variants_do_not_move_with_order():
    # True by construction, pinned so a change that lets order leak in shows
    # up: retrieval breaks ties by document id, so order never reaches these
    # agents' answers.
    spread = order_spread(ReferenceAgent())
    assert spread["fixture_order"] == 9
    assert set(spread["by_seed"]) == set(range(20))
    assert (spread["min"], spread["max"], spread["flipped"]) == (9, 9, [])
    for gamer in GAMERS:
        if gamer not in SURFACE:
            assert order_spread(gamer(), seeds=tuple(range(5)))["flipped"] == [], gamer.name
