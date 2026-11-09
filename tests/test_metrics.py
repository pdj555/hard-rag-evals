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


def test_conflict_acknowledged_needs_both_claims_and_a_marker_in_one_sentence():
    claims = ("30", "14")
    no_marker = Answer(text="The window is 14 days, and it was 30 days.")
    assert not M.conflict_acknowledged(no_marker, claims)
    side_by_side = Answer(text="The window changed from 30 to 14 days.")
    assert M.conflict_acknowledged(side_by_side, claims)
    one_claim = Answer(text="The window is 14 days. However, it changed.")
    assert not M.conflict_acknowledged(one_claim, claims)
    split = Answer(text="It was 30 days. However, it is 14 days now.")
    assert not M.conflict_acknowledged(split, claims)


def test_conflict_acknowledged_rejects_a_bare_hedge():
    hedge = Answer(text="It is 14 days. It is 30 days. However, the sources may conflict.")
    assert not M.conflict_acknowledged(hedge, ("30", "14"))


def test_conflict_claims_match_whole_tokens():
    assert not M.conflict_acknowledged(Answer(text="It changed from 300 to 140 days."), ("30", "14"))
