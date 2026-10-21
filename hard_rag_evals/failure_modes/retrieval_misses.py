"""Retrieval misses: the answer exists but vocabulary mismatch hides it.

The document says "automobiles", the user asks about "cars", and a
lexical retriever returns nothing useful. This case isolates retriever
recall from answer quality: the gold document is scored purely on
whether it was retrieved at all.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


# Tight budget on purpose: the gold document ranks below the two
# distractors on lexical overlap, so it is never retrieved at all.
_BUDGET = RetrievalBudget(max_docs=2, max_chars=8000)


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    case_id = f"retrieval-miss-{difficulty}"
    return _build_case(
        case_id=case_id,
        mode="retrieval_misses",
        name=f"retrieval_misses{suffix}",
        budget=_BUDGET,
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
