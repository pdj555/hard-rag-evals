"""Reference agentic search implementation.

Retrieve, read, synthesize, cite. Deterministic, no API keys, no model
calls. It is deliberately naive: lexical retrieval, extractive synthesis,
no contradiction detection, no recency reasoning, never abstains.

That naivety is the point. The suite exists to show exactly where this
baseline breaks, which is the same place most production RAG breaks.
Beat its score and you have earned the improvement.
"""
from __future__ import annotations

import re

from ..retrieval import retrieve, tokenize
from ..types import Answer, Corpus, RetrievalBudget


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _top_sentences(text: str, query: str, k: int) -> list[str]:
    qterms = set(tokenize(query))
    scored = []
    for s in _sentences(text):
        overlap = len(qterms & set(tokenize(s)))
        scored.append((overlap, s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for o, s in scored[:k] if o > 0]


class ReferenceAgent:
    """Extractive RAG baseline. Fast, explainable, and wrong in
    instructive ways."""

    name = "reference-agent"

    def __init__(self, sentences_per_doc: int = 2):
        self.sentences_per_doc = sentences_per_doc

    def answer(
        self, query: str, corpus: Corpus, budget: RetrievalBudget
    ) -> Answer:
        docs = retrieve(corpus, query, budget)
        parts: list[str] = []
        cited: list[str] = []
        for doc in docs:
            sents = _top_sentences(doc.text, query, self.sentences_per_doc)
            if not sents:
                continue
            cited.append(doc.id)
            for s in sents:
                parts.append(f"According to {doc.id}: {s}")
        text = " ".join(parts) if parts else "No relevant information found."
        return Answer(
            text=text,
            citations=cited,
            retrieved_ids=[d.id for d in docs],
            abstained=False,
        )
