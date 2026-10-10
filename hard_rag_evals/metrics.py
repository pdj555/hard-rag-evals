"""Grading metrics for RAG answers.

All metrics are heuristic and deterministic. They are intentionally strict:
a citation that exists but supports nothing still fails, and silence on a
contradiction fails even when the cited facts are individually correct.
Production use would swap in model graded checks behind the same names.
"""
from __future__ import annotations

from .retrieval import tokenize
from .types import Answer, Corpus

_CONFLICT_MARKERS = frozenset(
    {
        "conflict",
        "contradict",
        "however",
        "disagree",
        "changed",
        "updated",
        "differs",
        "whereas",
        "although",
        "supersede",
        "replaced",
        "inconsistent",
    }
)


def citation_precision(answer: Answer, corpus: Corpus) -> float:
    """Fraction of citations that name a real document. 1.0 when the answer
    cites nothing."""
    if not answer.citations:
        return 1.0
    good = sum(1 for c in answer.citations if corpus.by_id(c) is not None)
    return good / len(answer.citations)


def citation_recall(answer: Answer, must_cite: tuple[str, ...]) -> float:
    """Fraction of required documents actually cited. 1.0 when none required."""
    if not must_cite:
        return 1.0
    cited = set(answer.citations)
    return sum(1 for d in must_cite if d in cited) / len(must_cite)


def retrieval_recall(answer: Answer, gold_ids: tuple[str, ...]) -> float:
    """Fraction of gold documents the agent retrieved, whether or not it
    cited them. Measures the retriever, not the writer."""
    if not gold_ids:
        return 1.0
    got = set(answer.retrieved_ids)
    return sum(1 for d in gold_ids if d in got) / len(gold_ids)


def faithfulness(answer: Answer, corpus: Corpus) -> float:
    """Heuristic: each cited document must share at least one content word
    with the answer text. Catches citations that are real ids attached to
    unsupported claims."""
    if not answer.citations:
        return 1.0
    answer_terms = set(tokenize(answer.text))
    hits = 0
    for c in answer.citations:
        doc = corpus.by_id(c)
        if doc is None:
            continue
        if answer_terms & set(tokenize(doc.text)):
            hits += 1
    return hits / len(answer.citations)


def conflict_acknowledged(answer: Answer, pair: tuple[str, str]) -> bool:
    """True when the answer cites both sides of a contradiction and its text
    signals the disagreement. Citing both without comment still fails: the
    user cannot tell which claim to trust."""
    a, b = pair
    cited = set(answer.citations)
    if a not in cited or b not in cited:
        return False
    text = answer.text.lower()
    return any(m in text for m in _CONFLICT_MARKERS)


def abstention_correct(answer: Answer, should_abstain: bool) -> bool:
    return answer.abstained == should_abstain
