"""Context overflow: more documents than budget, with keyword-stuffed noise.

The corpus holds far more documents than the retrieval budget allows,
and distractors are stuffed with query terms. Substantive documents must
outrank noise.

Tiers: easy shows the behavior in its simplest form, medium is the
original case, hard pushes it to where production systems break.
"""
from __future__ import annotations

from ..types import EvalCase, RetrievalBudget
from . import _build_case


def _make(difficulty: str) -> EvalCase:
    suffix = "" if difficulty == "medium" else f"_{difficulty}"
    budgets = {
        "easy": RetrievalBudget(max_docs=4, max_chars=8000),
        "medium": RetrievalBudget(max_docs=5, max_chars=8000),
        "hard": RetrievalBudget(max_docs=3, max_chars=8000),
    }
    return _build_case(
        case_id=f"overflow-{difficulty}",
        mode="context_overflow",
        name=f"context_overflow{suffix}",
        budget=budgets[difficulty],
        difficulty=difficulty,
    )


def build() -> EvalCase:
    return _make("medium")


def build_easy() -> EvalCase:
    return _make("easy")


def build_hard() -> EvalCase:
    return _make("hard")
