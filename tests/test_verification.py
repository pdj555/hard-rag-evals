"""Tests for independent verification of the retrieval report.

The grader used to score the ids an agent reported about itself without
checking them. These tests pin the verification: reported ids are checked
against the corpus and the case budget before scoring, retrieval recall
counts verified ids only, and a citation must name a document in the
verified retrieved set.
"""
from hard_rag_evals import Answer, Corpus, Document, EvalCase, RetrievalBudget
from hard_rag_evals import metrics as M
from hard_rag_evals.failure_modes import ALL_CASES
from hard_rag_evals.gamers import CorpusSmuggler, RetrievalFabricator
from hard_rag_evals.reference_agent import ReferenceAgent
from hard_rag_evals.runner import DIFFICULTY_ORDER, grade, run_suite


def _doc(id, text):
    return Document(id=id, text=text, source="test", published="2025-01-01")


def _corpus():
    return Corpus(
        documents=(
            _doc("a", "alpha beta"),
            _doc("b", "gamma delta"),
            _doc("c", "epsilon zeta"),
        )
    )


def _case(**kw):
    base = dict(
        id="t1",
        mode="test",
        query="q",
        corpus=_corpus(),
        budget=RetrievalBudget(max_docs=5, max_chars=8000),
    )
    base.update(kw)
    return EvalCase(**base)


# ---- verify_retrieved_ids ----


def test_verify_accepts_real_ids_inside_budget():
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["a", "b"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), RetrievalBudget())
    assert verified == ["a", "b"]
    assert problems == []


def test_verify_rejects_unknown_id():
    ans = Answer(text="alpha", retrieved_ids=["a", "ghost"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), RetrievalBudget())
    assert verified == ["a"]
    assert any("not in the corpus" in p and "ghost" in p for p in problems)


def test_verify_rejects_duplicate_id():
    ans = Answer(text="alpha", retrieved_ids=["a", "a"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), RetrievalBudget())
    assert verified == ["a"]
    assert any("more than once" in p for p in problems)


def test_verify_rejects_ids_past_max_docs():
    budget = RetrievalBudget(max_docs=2, max_chars=8000)
    ans = Answer(text="alpha", retrieved_ids=["a", "b", "c"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), budget)
    assert verified == ["a", "b"]
    assert any("budget allows" in p and "c" in p for p in problems)


def test_verify_rejects_ids_past_max_chars():
    budget = RetrievalBudget(max_docs=5, max_chars=20)
    ans = Answer(text="alpha", retrieved_ids=["a", "b", "c"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), budget)
    # "alpha beta" is 10 chars and "gamma delta" is 11: together 21 > 20.
    assert verified == ["a"]
    assert any("character budget" in p for p in problems)


def test_verify_allows_one_document_past_max_chars():
    # Mirrors retrieve(): a first document is returned even when it alone
    # passes the character cap.
    budget = RetrievalBudget(max_docs=5, max_chars=5)
    ans = Answer(text="alpha", retrieved_ids=["a"])
    verified, problems = M.verify_retrieved_ids(ans, _corpus(), budget)
    assert verified == ["a"]
    assert problems == []


def test_verified_recall_ignores_unverified_gold():
    budget = RetrievalBudget(max_docs=1, max_chars=8000)
    ans = Answer(text="alpha", retrieved_ids=["b", "a"])
    # "a" is gold but reported past the budget, so it does not count.
    assert M.verified_retrieval_recall(ans, _corpus(), budget, ("a",)) == 0.0
    assert M.retrieval_recall(ans, ("a",)) == 1.0


# ---- grade wiring ----


def test_grade_fails_unknown_retrieved_id():
    case = _case(must_cite=("a",))
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["a", "ghost"])
    result = grade(case, ans)
    assert not result.passed
    assert any("not in the corpus" in n for n in result.notes)


def test_grade_fails_citation_that_was_not_retrieved():
    case = _case(must_cite=("a",))
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["b"])
    result = grade(case, ans)
    assert not result.passed
    assert any("not verifiably retrieved" in n for n in result.notes)


def test_grade_passes_citation_backed_by_verified_retrieval():
    case = _case(must_cite=("a",))
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["a", "b"])
    assert grade(case, ans).passed


def test_grade_fails_report_past_the_budget():
    case = _case(budget=RetrievalBudget(max_docs=1, max_chars=8000))
    ans = Answer(text="alpha", citations=["a"], retrieved_ids=["a", "b"])
    result = grade(case, ans)
    assert not result.passed
    assert any("budget allows" in n for n in result.notes)


def test_grade_retrieval_recall_score_uses_verified_ids():
    case = _case(gold_doc_ids=("a",), budget=RetrievalBudget(max_docs=1, max_chars=8000))
    ans = Answer(text="gamma", citations=["b"], retrieved_ids=["b", "a"])
    result = grade(case, ans)
    assert result.scores["retrieval_recall"] == 0.0


# ---- the two report gaming agents ----


def _gained(agent):
    honest = {r.case_id: r.passed for r in run_suite(ReferenceAgent())}
    return {r.case_id for r in run_suite(agent) if r.passed and not honest[r.case_id]}


def test_corpus_smuggler_gains_nothing():
    assert _gained(CorpusSmuggler()) == set()


def test_retrieval_fabricator_gains_nothing():
    assert _gained(RetrievalFabricator()) == set()


def test_self_report_cases_fail_for_honest_and_smuggling_agents():
    for agent in (ReferenceAgent(), CorpusSmuggler(), RetrievalFabricator()):
        results = run_suite(agent, modes="retrieval_self_report")
        assert len(results) == 3
        assert not any(r.passed for r in results)


# ---- suite shape ----


def test_suite_counts_after_self_report_mode():
    assert len(ALL_CASES) == 45
    assert len({c.mode for c in ALL_CASES}) == 15
    tiers = {t: 0 for t in DIFFICULTY_ORDER}
    for c in ALL_CASES:
        tiers[c.difficulty] += 1
    assert tiers == {"easy": 13, "medium": 13, "hard": 14, "brutal": 5}
