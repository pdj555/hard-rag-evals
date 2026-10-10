"""Unit tests for retrieval and metrics."""
from hard_rag_evals import Corpus, Document
from hard_rag_evals import metrics as M
from hard_rag_evals import Answer, RetrievalBudget
from hard_rag_evals.retrieval import retrieve, score, tokenize, _idf


def _doc(id, text):
    return Document(id=id, text=text, source="test", published="2025-01-01")


def test_tokenize_drops_stopwords():
    assert "the" not in tokenize("the quick brown fox")
    assert "quick" in tokenize("the quick brown fox")


def test_retrieve_respects_max_docs():
    corpus = Corpus(documents=tuple(_doc(f"d{i}", f"alpha beta gamma {i}") for i in range(10)))
    got = retrieve(corpus, "alpha beta", RetrievalBudget(max_docs=3, max_chars=10**6))
    assert len(got) == 3


def test_retrieve_respects_max_chars():
    corpus = Corpus(documents=tuple(_doc(f"d{i}", "x " * 1000) for i in range(5)))
    got = retrieve(corpus, "x", RetrievalBudget(max_docs=5, max_chars=1500))
    assert sum(len(d.text) for d in got) <= 1500 + 2000  # one doc may exceed alone


def test_retrieve_ranks_relevant_first():
    corpus = Corpus(
        documents=(
            _doc("irrelevant", "nothing to see here at all"),
            _doc("relevant", "refund window policy thirty days"),
        )
    )
    got = retrieve(corpus, "refund window", RetrievalBudget())
    assert got[0].id == "relevant"


def test_citation_precision_all_real():
    corpus = Corpus(documents=(_doc("a", "hello world"),))
    ans = Answer(text="hello", citations=["a"])
    assert M.citation_precision(ans, corpus) == 1.0


def test_citation_precision_catches_fabrication():
    corpus = Corpus(documents=(_doc("a", "hello world"),))
    ans = Answer(text="hello", citations=["a", "ghost-doc"])
    assert M.citation_precision(ans, corpus) == 0.5


def test_citation_precision_empty_is_one():
    corpus = Corpus(documents=(_doc("a", "hello world"),))
    assert M.citation_precision(Answer(text="x"), corpus) == 1.0


def test_conflict_acknowledged_needs_both_and_marker():
    corpus = Corpus(
        documents=(_doc("a", "policy is thirty days"), _doc("b", "policy is fourteen days"))
    )
    both_no_marker = Answer(text="it is thirty days", citations=["a", "b"])
    assert not M.conflict_acknowledged(both_no_marker, ("a", "b"))
    both_marker = Answer(
        text="however the policy changed from thirty to fourteen days",
        citations=["a", "b"],
    )
    assert M.conflict_acknowledged(both_marker, ("a", "b"))
    one_side = Answer(text="however it changed", citations=["a"])
    assert not M.conflict_acknowledged(one_side, ("a", "b"))
