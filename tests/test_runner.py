"""Tests for the runner grading logic."""
from hard_rag_evals import Answer, Corpus, Document, EvalCase, RetrievalBudget
from hard_rag_evals.runner import grade


def _case(**kw):
    corpus = Corpus(
        documents=(
            Document(id="a", text="alpha beta", source="t", published="2025-01-01"),
            Document(id="b", text="gamma delta", source="t", published="2025-01-01"),
        )
    )
    base = dict(
        id="t1",
        mode="test",
        query="q",
        corpus=corpus,
        budget=RetrievalBudget(),
    )
    base.update(kw)
    return EvalCase(**base)


def test_passes_clean_case():
    case = _case(must_cite=("a",))
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["a", "b"])
    assert grade(case, ans).passed


def test_fails_missing_citation():
    case = _case(must_cite=("a", "b"))
    ans = Answer(text="alpha", citations=["a"])
    assert not grade(case, ans).passed


def test_fails_forbidden_citation():
    case = _case(must_not_cite=("b",))
    ans = Answer(text="gamma", citations=["b"])
    assert not grade(case, ans).passed


def test_fails_unknown_citation():
    case = _case()
    ans = Answer(text="x", citations=["ghost"])
    assert not grade(case, ans).passed


def test_unanswerable_requires_abstain():
    case = _case(should_abstain=True)
    assert not grade(case, Answer(text="guess")).passed
    assert grade(case, Answer(text="", abstained=True)).passed
