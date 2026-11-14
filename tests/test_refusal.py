"""Over-refusal is measured apart from correct abstention."""
import pytest

from hard_rag_evals import Answer, Corpus, Document, EvalCase, RetrievalBudget
from hard_rag_evals.gamers import AlwaysAbstain
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import grade, refusal_summary, render_markdown, run_suite


def _case(case_id, should_abstain):
    corpus = Corpus(documents=(Document(id="a", text="alpha", source="t", published="2025-01-01"),))
    return EvalCase(
        id=case_id, mode="test", query="q", corpus=corpus, budget=RetrievalBudget(),
        should_abstain=should_abstain,
    )


def test_result_records_what_the_agent_did_and_what_the_case_wanted():
    refused = grade(_case("answerable", False), Answer(text="no", abstained=True))
    assert (refused.abstained, refused.should_abstain, refused.passed) == (True, False, False)
    assert refused.failed_gates == ["abstention"]
    answered = grade(_case("unanswerable", True), Answer(text="a guess"))
    assert (answered.abstained, answered.should_abstain, answered.passed) == (False, True, False)


def test_the_two_rates_use_separate_denominators():
    results = [
        grade(_case("a1", False), Answer(text="x")),
        grade(_case("a2", False), Answer(text="no", abstained=True)),
        grade(_case("a3", False), Answer(text="x")),
        grade(_case("a4", False), Answer(text="x")),
        grade(_case("u1", True), Answer(text="no", abstained=True)),
        grade(_case("u2", True), Answer(text="a guess")),
    ]
    summary = refusal_summary(results)
    over, correct = summary["over_refusal"], summary["correct_abstention"]
    assert (over["abstained"], over["total"], over["rate"]) == (1, 4, 0.25)
    assert (correct["abstained"], correct["total"], correct["rate"]) == (1, 2, 0.5)
    assert over["ci95"][0] < 0.25 < over["ci95"][1]


def test_no_cases_of_a_kind_is_none_not_zero():
    summary = refusal_summary([grade(_case("a1", False), Answer(text="x"))])
    assert summary["correct_abstention"] is None
    assert summary["over_refusal"]["total"] == 1


def test_always_abstain_is_perfect_on_one_rate_and_worst_on_the_other():
    summary = refusal_summary(run_suite(AlwaysAbstain()))
    assert summary["correct_abstention"]["abstained"] == 3
    assert summary["correct_abstention"]["total"] == 3
    assert summary["over_refusal"]["abstained"] == 39
    assert summary["over_refusal"]["total"] == 39
    assert summary["over_refusal"]["ci95"] == pytest.approx([0.025 ** (1 / 39), 1.0], abs=1e-9)


def test_reference_agent_never_refuses():
    results = run_suite(ReferenceAgent())
    summary = refusal_summary(results)
    assert (summary["over_refusal"]["abstained"], summary["over_refusal"]["total"]) == (0, 39)
    assert (summary["correct_abstention"]["abstained"], summary["correct_abstention"]["total"]) == (0, 3)
    report = render_markdown("reference-agent", results)
    assert "| over-refusal (answerable cases refused) | 0/39 | 0.00 | 0.00 to 0.09 |" in report
    assert "| correct abstention (unanswerable cases refused) | 0/3 | 0.00 | 0.00 to 0.71 |" in report
