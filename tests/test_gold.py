"""Every case can be passed, and every gate on it is load bearing.

tests/gold_answers.json holds one hand-written answer per case. Each must pass
its case. Then each gold answer is broken one way at a time, and each break must
fail: a case that still passes after losing a required citation, gaining a
forbidden or invented one, or flipping its abstention has a gate that decides
nothing.
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from hard_rag_evals import Answer
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.runner import grade

GOLD = json.loads((Path(__file__).parent / "gold_answers.json").read_text())
GOLD.pop("_canary")
CASES = {c.id: c for c in ALL_CASES}


def _gold(case_id: str) -> Answer:
    g = GOLD[case_id]
    return Answer(text=g["text"], citations=list(g["citations"]), abstained=g["abstained"])


def test_one_gold_answer_per_case():
    assert set(GOLD) == set(CASES)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_gold_answer_passes(case_id):
    result = grade(CASES[case_id], _gold(case_id))
    assert result.passed, result.notes


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_breaking_the_gold_answer_fails(case_id):
    case, gold = CASES[case_id], _gold(case_id)
    broken: list[tuple[str, Answer]] = []
    for doc_id in case.must_cite:
        broken.append((f"drop {doc_id}", replace(gold, citations=[c for c in gold.citations if c != doc_id])))
    for doc_id in case.must_not_cite:
        broken.append((f"cite {doc_id}", replace(gold, citations=gold.citations + [doc_id])))
    broken.append(("invent a citation", replace(gold, citations=gold.citations + ["doc-not-in-corpus"])))
    broken.append(("flip abstention", replace(gold, abstained=not gold.abstained)))
    if case.conflict_claims is not None:
        hedged = "The sources may conflict. " + " ".join(case.conflict_claims)
        broken.append(("hedge instead of comparing", replace(gold, text=hedged)))
    if case.numeric_expected is not None:
        inputs = " ".join(d.text for d in case.corpus.documents if d.id in case.must_cite)
        broken.append(("quote the inputs only", replace(gold, text=inputs)))
    if case.forbidden_phrases:
        broken.append(("repeat the payload", replace(gold, text=gold.text + " " + case.forbidden_phrases[0])))
    for what, answer in broken:
        assert not grade(case, answer).passed, what


def test_compositional_temporal_stale_is_solvable():
    # compositional-temporal-stale once required citing doc-ret-2023 through its
    # conflict pair while forbidding it through must_not_cite. No answer could pass.
    case = CASES["compositional-temporal-stale"]
    assert "doc-ret-2023" in case.must_not_cite
    assert grade(case, _gold(case.id)).passed
