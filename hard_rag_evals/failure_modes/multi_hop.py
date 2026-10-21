"""Multi hop: the answer requires combining two documents.

No single document contains the answer. The agent must retrieve both the
launch date and the warranty terms, then do the arithmetic. Passing
requires citing both source documents.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


_BUDGET = RetrievalBudget(max_docs=5, max_chars=8000)


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    case_id = f"multihop-{difficulty}"
    return _build_case(
        case_id=case_id,
        mode="multi_hop",
        name=f"multi_hop{suffix}",
        budget=_BUDGET,
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
