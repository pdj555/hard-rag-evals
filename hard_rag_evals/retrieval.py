"""Deterministic keyword retrieval with a hard budget.

Deliberately simple: TF-IDF weighted term overlap, no embeddings, no API.
The reference agent uses this, which is exactly why it fails the harder
evals. A better retriever is the most direct way to move the numbers.
"""
from __future__ import annotations

import math
import re

from .types import Corpus, Document, RetrievalBudget

_STOPWORDS = frozenset(
    """
    a an the and or but if then else when at by for with about into through
    during before after above below to from up down in out on off over under
    again further once here there all any both each few more most other some
    such no nor not only own same so than too very can will just don should
    now is are was were be been being have has had having do does did doing
    would could ought i you he she it we they them his her its our their this
    that these those am as of what which who whom how why where
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]


def _idf(corpus: Corpus) -> dict[str, float]:
    n = len(corpus.documents)
    df: dict[str, int] = {}
    for d in corpus.documents:
        for term in set(tokenize(d.text)):
            df[term] = df.get(term, 0) + 1
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def score(query: str, doc: Document, idf: dict[str, float]) -> float:
    """IDF weighted count of query term matches in the document."""
    counts: dict[str, int] = {}
    for t in tokenize(doc.text):
        counts[t] = counts.get(t, 0) + 1
    return sum(idf.get(t, 0.0) * counts.get(t, 0) for t in tokenize(query))


def retrieve(corpus: Corpus, query: str, budget: RetrievalBudget) -> list[Document]:
    """Top scoring documents, truncated to the budget. Ties broken by
    document id for determinism."""
    idf = _idf(corpus)
    ranked = sorted(
        corpus.documents,
        key=lambda d: (score(query, d, idf), d.id),
        reverse=True,
    )
    out: list[Document] = []
    chars = 0
    for d in ranked:
        if len(out) >= budget.max_docs:
            break
        if chars + len(d.text) > budget.max_chars and out:
            break
        out.append(d)
        chars += len(d.text)
    return out
