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
    assert result.gates == {"abstention": True, "unknown_citation": True}


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
