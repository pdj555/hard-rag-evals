"""Long-context needle: the answer is buried in dozens of documents.

Easy: 15 documents, the needle shares query terms, budget covers it.
Medium: 30 documents, the needle uses synonyms for every query term;
lexical retrieval cannot see it.
Hard: 50 documents with near-duplicate distractors that share the
needle's phrasing but carry different numbers. The agent must find the
exact document, not just the right neighborhood.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case

_BUDGETS = {
    "easy": RetrievalBudget(max_docs=5, max_chars=8000),
    "medium": RetrievalBudget(max_docs=5, max_chars=8000),
    "hard": RetrievalBudget(max_docs=8, max_chars=12000),
}


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    return _build_case(
        case_id=f"needle-{difficulty}",
        mode="long_context_needle",
        name=f"long_context_needle{suffix}",
        budget=_BUDGETS[difficulty],
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
