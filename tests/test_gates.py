"""Each case result names the atomic gates that applied and the ones that failed."""
import json
from dataclasses import replace
from pathlib import Path

from hard_rag_evals import Answer, Corpus, Document, EvalCase, RetrievalBudget
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import (
    GATES,
    gate_breakdown,
    grade,
    render_markdown,
    run_suite,
    summary_by_mode,
)

REFERENCE_FAILED_BY_GATE = {
    "budget": 0,
    "abstention": 3,
    "required_citation": 6,
    "forbidden_citation": 15,
    "unknown_citation": 0,
    "contradiction": 5,
    "numeric": 4,
    "order": 2,
    "forbidden_phrase": 1,
}
GOLD = json.loads((Path(__file__).parent / "gold_answers.json").read_text())
GOLD.pop("_canary")


def _case(**kw):
    corpus = Corpus(
        documents=(
            Document(id="a", text="alpha beta", source="t", published="2025-01-01"),
            Document(id="b", text="gamma delta", source="t", published="2025-01-01"),
        )
    )
    base = dict(id="t1", mode="test", query="q", corpus=corpus, budget=RetrievalBudget())
    base.update(kw)
    return EvalCase(**base)


def test_each_gate_fails_alone():
    everything = _case(
        query="Is it 30 or 14?",
        budget=RetrievalBudget(max_docs=1, max_chars=100),
        must_cite=("a",),
        must_not_cite=("b",),
        conflict_claims=("30", "14"),
        numeric_expected=10.0,
        order_check=(("alpha",), ("gamma",)),
        forbidden_phrases=("hunter2",),
    )
    good = Answer(text="It changed from 30 to 14. The total is 10. alpha then gamma.", citations=["a"])
    result = grade(everything, good)
    assert result.passed and result.failed_gates == []
    assert set(result.gates) == set(GATES)

    breaks = {
        "budget": replace(good, retrieved_ids=["a", "b"]),
        "abstention": replace(good, abstained=True),
        "required_citation": replace(good, citations=[]),
        "forbidden_citation": replace(good, citations=["a", "b"]),
        "unknown_citation": replace(good, citations=["a", "ghost"]),
        "contradiction": replace(good, text="It is 14. The total is 10. alpha then gamma."),
        "numeric": replace(good, text="It changed from 30 to 14. alpha then gamma."),
        "order": replace(good, text="It changed from 30 to 14. The total is 10. gamma then alpha."),
        "forbidden_phrase": replace(good, text=good.text + " hunter2"),
    }
    assert set(breaks) == set(GATES)
    for gate, answer in breaks.items():
        broken = grade(everything, answer)
        assert not broken.passed
        assert broken.failed_gates == [gate], gate


def test_gates_that_a_case_does_not_set_are_not_recorded():
    result = grade(_case(), Answer(text="x"))
    assert result.gates == {"budget": True, "abstention": True, "unknown_citation": True}


def test_passed_is_exactly_all_gates_held():
    for r in run_suite(ReferenceAgent()):
        assert r.passed == (not r.failed_gates)


def test_gate_coverage_matches_the_fixtures():
    cases = {c.id: c for c in ALL_CASES}
    results = [
        grade(cases[i], Answer(text=g["text"], citations=g["citations"], abstained=g["abstained"]))
        for i, g in GOLD.items()
        if i in cases
    ]
    applied = {gate: n for gate, (_, n) in gate_breakdown(results).items()}
    assert applied == {
        "budget": 42,
        "abstention": 42,
        "required_citation": 39,
        "forbidden_citation": 16,
        "unknown_citation": 42,
        "contradiction": 5,
        "numeric": 4,
        "order": 3,
        "forbidden_phrase": 2,
    }
    assert all(failed == 0 for failed, _ in gate_breakdown(results).values())


def test_reference_agent_failures_by_gate():
    results = run_suite(ReferenceAgent())
    failed = {gate: n for gate, (n, _) in gate_breakdown(results).items()}
    assert failed == REFERENCE_FAILED_BY_GATE
    # every failed case is counted under at least one gate
    assert sum(1 for r in results if r.failed_gates) == sum(not r.passed for r in results)


def test_summary_by_mode_adds_up():
    results = run_suite(ReferenceAgent())
    by_mode = summary_by_mode(results)
    assert len(by_mode) == 14
    assert sum(row["total"] for row in by_mode.values()) == 42
    assert sum(row["passed"] for row in by_mode.values()) == sum(r.passed for r in results)
    assert by_mode["unanswerable"] == {"passed": 0, "total": 3, "failed_gates": {"abstention": 3}}


def test_report_breaks_failures_out_by_gate_and_mode():
    report = render_markdown("reference-agent", run_suite(ReferenceAgent()))
    assert "| abstention | 3 | 42 |" in report
    assert "| unanswerable | 0/3 | abstention 3 |" in report
    assert "| unanswerable-easy | easy | unanswerable | no | abstention |" in report


# ---- the budget gate ----


def test_budget_gate_counts_the_documents_an_answer_says_it_retrieved():
    case = _case(budget=RetrievalBudget(max_docs=1, max_chars=1000))
    assert grade(case, Answer(text="x", retrieved_ids=["a"])).passed
    assert grade(case, Answer(text="x", retrieved_ids=["a", "a"])).passed  # one document, listed twice
    over = grade(case, Answer(text="x", retrieved_ids=["a", "b"]))
    assert not over.passed and over.failed_gates == ["budget"]
    assert any("the budget is 1 documents and 1000 characters" in n for n in over.notes)
    # ids the corpus does not hold still count toward the number retrieved
    assert grade(case, Answer(text="x", retrieved_ids=["a", "ghost"])).failed_gates == ["budget"]


def test_budget_gate_counts_characters_and_allows_one_oversized_document():
    # "alpha beta" and "gamma delta" are 10 and 11 characters
    tight = _case(budget=RetrievalBudget(max_docs=5, max_chars=15))
    assert grade(tight, Answer(text="x", retrieved_ids=["a"])).passed
    assert grade(tight, Answer(text="x", retrieved_ids=["a", "b"])).failed_gates == ["budget"]
    tiny = _case(budget=RetrievalBudget(max_docs=5, max_chars=5))
    assert grade(tiny, Answer(text="x", retrieved_ids=["b"])).passed  # as retrieve() allows


def test_budget_gate_cannot_see_what_an_answer_does_not_report():
    # The stated limit: no retrieved_ids, no evidence, pass.
    case = _case(budget=RetrievalBudget(max_docs=1, max_chars=5))
    assert grade(case, Answer(text="x", citations=["a", "b"])).gates["budget"] is True


def test_budget_binds_on_eleven_cases_and_reading_everything_fails_exactly_those():
    cases = {c.id: c for c in ALL_CASES}
    binding = [
        c.id
        for c in ALL_CASES
        if len(c.corpus.documents) > c.budget.max_docs
        or sum(len(d.text) for d in c.corpus.documents) > c.budget.max_chars
    ]
    assert len(binding) == 11
    failed = []
    for cid, g in GOLD.items():
        everything = [d.id for d in cases[cid].corpus.documents]
        result = grade(
            cases[cid],
            Answer(text=g["text"], citations=g["citations"], abstained=g["abstained"], retrieved_ids=everything),
        )
        assert result.failed_gates in ([], ["budget"])
        if result.failed_gates:
            failed.append(cid)
    assert sorted(failed) == sorted(binding)


def test_built_in_agents_stay_inside_the_budget():
    from hard_rag_evals.gamers import GAMERS, Fabricator

    for cls in (ReferenceAgent, Fabricator, *GAMERS):
        for seed in (None, 2026):
            assert all(r.gates["budget"] for r in run_suite(cls(), shuffle_seed=seed)), cls.name
