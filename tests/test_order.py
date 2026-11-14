"""Document order carries no meaning: the grader must not read it, and the
suite reports how much an agent's score moves when only the order changes."""
import json
from pathlib import Path

import pytest

from hard_rag_evals import Answer
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import GAMERS
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import grade, order_spread, permute_documents, run_suite

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


def test_run_suite_shuffle_seed_permutes_what_the_agent_sees():
    seen = {}

    class Recorder:
        name = "recorder"

        def answer(self, query, corpus, budget):
            seen[query] = [d.id for d in corpus.documents]
            return Answer(text="x")

    run_suite(Recorder(), shuffle_seed=1)
    shuffled = dict(seen)
    run_suite(Recorder())
    assert shuffled != seen
    assert {q: sorted(v) for q, v in shuffled.items()} == {q: sorted(v) for q, v in seen.items()}


def test_reference_agent_and_gamers_are_order_invariant_on_twenty_seeds():
    # Reported, not assumed: retrieval breaks ties by document id, so the
    # order in the fixture never reaches the answer. Pinned here so a change
    # that lets order leak in shows up.
    spread = order_spread(ReferenceAgent())
    assert spread["fixture_order"] == 9
    assert set(spread["by_seed"]) == set(range(20))
    assert (spread["min"], spread["max"], spread["flipped"]) == (9, 9, [])
    for gamer in GAMERS:
        assert order_spread(gamer(), seeds=tuple(range(5)))["flipped"] == [], gamer.name


def test_order_spread_reports_an_order_sensitive_agent():
    class FirstDocument:
        """Cites whatever document comes first. Its score is an accident of order."""

        name = "first-document"

        def answer(self, query, corpus, budget):
            first = corpus.documents[0]
            return Answer(text=first.text, citations=[first.id], retrieved_ids=[first.id])

    spread = order_spread(FirstDocument())
    assert spread["flipped"]
    assert spread["min"] < spread["max"]
